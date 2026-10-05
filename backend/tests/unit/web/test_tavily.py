"""Tavily behind WebSearchPort (S1-09; tech.md §8.4) on recorded answers through a mock
transport: the request it sends, the DTO it makes, the credits, the errors."""

# ruff: noqa: RUF001  (Russian test data)

import json
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from app.config import Settings
from app.contracts.web import (
    WebCrawlQuery,
    WebExtractQuery,
    WebHit,
    WebImage,
    WebMapQuery,
    WebSearchQuery,
)
from app.core.errors import (
    GatewayError,
    PermanentGatewayError,
    QuotaExhaustedError,
    TransientGatewayError,
)
from app.gateways.web.tavily import TavilyWebSearch, published

FIXTURES = Path(__file__).parents[2] / "fixtures" / "tavily"
KEY = "tvly-test-key"

type Handler = Callable[[httpx.Request], httpx.Response]


def recorded(name: str) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    return loaded


def adapter(handler: Handler) -> TavilyWebSearch:
    settings = Settings.model_construct(TAVILY_API_KEY=SecretStr(KEY))
    return TavilyWebSearch(settings, transport=httpx.MockTransport(handler))


def search(depth: str = "basic") -> WebSearchQuery:
    return WebSearchQuery.model_validate(
        {
            "query": "сбербанк новости",
            "topic": "news",
            "depth": depth,
            "time_range": "week",
            "max_results": 5,
            "include_domains": ["example.com"],
            "exclude_domains": [],
            "include_images": True,
        }
    )


async def test_a_search_sends_the_query_and_maps_the_answer() -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json=recorded("search"))

    found = await adapter(handler).search(search(depth="advanced"))

    [request] = sent
    body = json.loads(request.content)
    assert (request.method, request.url.path) == ("POST", "/search")
    assert request.headers["authorization"] == f"Bearer {KEY}"
    assert body == {
        "query": "сбербанк новости",
        "search_depth": "advanced",
        "topic": "news",
        "time_range": "week",
        "max_results": 5,
        "include_domains": ["example.com"],
        "include_images": True,
        "include_image_descriptions": True,
    }
    assert found.hits == [
        WebHit(
            url="https://news.example.com/2026/09/sber-rsbu-8m",
            title="Сбербанк раскрыл прибыль по РСБУ за восемь месяцев",
            content="Сбербанк сообщил о чистой прибыли по РСБУ за январь–август 2026 года.",
            score=0.91234,
            published_date=date(2026, 9, 10),
        ),
        WebHit(
            url="https://markets.example.org/sber-q2-2026-ifrs",
            title="Сбербанк отчитался по МСФО за второй квартал",
            content="Чистая прибыль группы по МСФО во втором квартале выросла год к году.",
            score=0.77,
            published_date=date(2026, 7, 29),
        ),
        WebHit(
            url="https://wiki.example.net/sber",
            title="Сбербанк",
            content="Крупнейший банк России.",
            score=0.5,
            published_date=None,
        ),
    ]
    assert found.images == [
        WebImage(
            url="https://news.example.com/img/sber-office.png",
            description="Головной офис Сбербанка",
        ),
        WebImage(url="https://markets.example.org/img/chart.png", description=None),
    ]
    assert (found.credits, found.cached) == (2, False)


async def test_an_extract_counts_only_the_pages_it_got() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["format"] == "markdown"
        return httpx.Response(200, json=recorded("extract"))

    query = WebExtractQuery.model_validate(
        {
            "urls": [
                "https://news.example.com/2026/09/sber-rsbu-8m",
                "https://nowhere.example.org/page",
            ],
            "depth": "advanced",
        }
    )
    found = await adapter(handler).extract(query)

    assert [page.url for page in found.pages] == ["https://news.example.com/2026/09/sber-rsbu-8m"]
    assert found.pages[0].content.startswith("# Сбербанк раскрыл прибыль")
    assert [(f.url, f.error) for f in found.failed] == [
        ("https://nowhere.example.org/page", "Failed to fetch url")
    ]
    assert found.credits == 2  # one page extracted, advanced


async def test_a_crawl_and_a_map() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=recorded(request.url.path.strip("/")))

    web = adapter(handler)
    crawl = await web.crawl(
        WebCrawlQuery.model_validate(
            {
                "url": "https://news.example.com",
                "instructions": "только про Сбербанк",
                "max_depth": 1,
                "limit": 5,
                "select_paths": [],
            }
        )
    )
    mapped = await web.map(
        WebMapQuery.model_validate(
            {"url": "https://news.example.com", "instructions": None, "max_depth": 2, "limit": 20}
        )
    )

    assert [p.url for p in crawl.pages] == [
        "https://news.example.com/2026/09/sber-rsbu-8m",
        "https://news.example.com/2026/09/sber-dividends",
    ]
    assert (crawl.base_url, crawl.credits) == ("https://news.example.com", 3)  # map 2 + extract 1
    assert (len(mapped.urls), mapped.credits) == (3, 1)


async def test_a_429_is_retried_and_keeps_its_retry_after() -> None:
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(429, headers={"Retry-After": "0.01"}, json={"detail": {"error": "x"}})

    with pytest.raises(TransientGatewayError) as limited:
        await adapter(handler).search(search())

    assert (limited.value.code, limited.value.retry_after_s) == ("web_unavailable", 0.01)
    assert len(attempts) == 3  # the call and two retries (§8.1)


@pytest.mark.parametrize(
    ("status", "error", "code", "attempts"),
    [
        (432, QuotaExhaustedError, "web_credits_exhausted", 1),
        (401, PermanentGatewayError, "web_unavailable", 1),
        (400, PermanentGatewayError, "validation_error", 1),
        (502, TransientGatewayError, "web_unavailable", 3),
    ],
)
async def test_errors_of_the_api(
    status: int,
    error: type[GatewayError],
    code: str,
    attempts: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[int] = []
    monkeypatch.setattr("app.gateways.retry.backoff", lambda attempt, retry_after, base: 0)

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(1)
        return httpx.Response(status, json={"detail": {"error": "refused"}})

    with pytest.raises(error) as raised:
        await adapter(handler).search(search())

    assert raised.value.code == code
    assert len(sent) == attempts


@pytest.mark.parametrize(
    ("raw", "day"),
    [
        ("Thu, 10 Sep 2026 08:00:00 GMT", date(2026, 9, 10)),
        ("2026-07-29", date(2026, 7, 29)),
        ("2026-07-29T10:00:00Z", date(2026, 7, 29)),
        ("", None),
        (None, None),
        ("вчера", None),
    ],
)
def test_published_dates(raw: str | None, day: date | None) -> None:
    assert published(raw) == day
