"""Tavily behind WebSearchPort (tech.md §8.4): AsyncTavilyClient on our own httpx client.

Credits come from the formula of credits.py on what the answer holds; MeteredWebSearch around
this adapter checks the budgets and keeps web_cache.
"""

import email.utils
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from datetime import date
from typing import Any

import httpx
from tavily import AsyncTavilyClient
from tavily.errors import (
    BadRequestError,
    ForbiddenError,
    InvalidAPIKeyError,
    UsageLimitExceededError,
)
from tavily.errors import TimeoutError as TavilyTimeout

from app.config import Settings
from app.contracts.web import (
    WebCrawlQuery,
    WebCrawlResult,
    WebExtractFailure,
    WebExtractQuery,
    WebExtractResult,
    WebHit,
    WebImage,
    WebMapQuery,
    WebMapResult,
    WebPage,
    WebSearchQuery,
    WebSearchResult,
)
from app.core.errors import (
    GatewayError,
    PermanentGatewayError,
    QuotaExhaustedError,
    TransientGatewayError,
)
from app.gateways.retry import with_retries
from app.gateways.web.credits import (
    crawl_credits,
    extract_credits,
    map_credits,
    search_credits,
)

API = "https://api.tavily.com"
TIMEOUT_S = 60.0
# The SDK drops the headers of a 429; this hook keeps Retry-After for the error.
_retry_after: ContextVar[float | None] = ContextVar("tavily_retry_after", default=None)


async def _note_retry_after(response: httpx.Response) -> None:
    if response.status_code == 429:
        try:
            _retry_after.set(float(response.headers.get("retry-after", "")))
        except ValueError:
            _retry_after.set(None)


def published(value: object) -> date | None:
    """news hits carry RFC 2822 dates, other topics ISO dates or nothing."""
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        pass
    try:
        return email.utils.parsedate_to_datetime(value).date()
    except (TypeError, ValueError):
        return None


def _error(exc: Exception) -> GatewayError | None:
    match exc:
        case UsageLimitExceededError():
            return TransientGatewayError("web_unavailable", _retry_after.get())
        case ForbiddenError():  # 432 and 433: the plan or the pay-as-you-go limit ran out
            return QuotaExhaustedError("web_credits_exhausted")
        case InvalidAPIKeyError():
            return PermanentGatewayError("web_unavailable")
        case BadRequestError():
            return PermanentGatewayError("validation_error")
        case TavilyTimeout() | httpx.TransportError():
            return TransientGatewayError("web_unavailable")
        case httpx.HTTPStatusError() if exc.response.status_code >= 500:
            return TransientGatewayError("web_unavailable")
        case httpx.HTTPStatusError():
            return PermanentGatewayError("web_unavailable")
    return None


class TavilyWebSearch:
    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None):
        self._http = httpx.AsyncClient(
            base_url=API,
            timeout=TIMEOUT_S,
            transport=transport,
            event_hooks={"response": [_note_retry_after]},
        )
        self._client = AsyncTavilyClient(
            api_key=settings.TAVILY_API_KEY.get_secret_value(), client=self._http
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _call(self, call: Callable[[], Awaitable[dict[str, Any]]]) -> dict[str, Any]:
        async def attempt() -> dict[str, Any]:
            _retry_after.set(None)
            try:
                return await call()
            except Exception as exc:
                error = _error(exc)
                if error is None:
                    raise
                raise error from exc

        return await with_retries(attempt)

    async def search(self, q: WebSearchQuery) -> WebSearchResult:
        answer = await self._call(
            lambda: self._client.search(
                query=q.query,
                search_depth=q.depth,
                topic=q.topic,
                time_range=q.time_range,
                max_results=q.max_results,
                include_domains=q.include_domains or None,
                exclude_domains=q.exclude_domains or None,
                include_images=q.include_images,
                include_image_descriptions=q.include_images or None,
            )
        )
        return WebSearchResult(
            hits=[
                WebHit(
                    url=hit["url"],
                    title=hit.get("title") or hit["url"],
                    content=hit.get("content") or "",
                    score=float(hit.get("score") or 0),
                    published_date=published(hit.get("published_date")),
                )
                for hit in answer.get("results", [])
            ],
            images=[
                WebImage(url=image, description=None)
                if isinstance(image, str)
                else WebImage(url=image["url"], description=image.get("description"))
                for image in answer.get("images") or []
            ],
            credits=search_credits(q.depth),
            cached=False,
        )

    async def extract(self, q: WebExtractQuery) -> WebExtractResult:
        answer = await self._call(
            lambda: self._client.extract(
                urls=[str(url) for url in q.urls], extract_depth=q.depth, format="markdown"
            )
        )
        pages = [
            WebPage(url=page["url"], content=page.get("raw_content") or "")
            for page in answer.get("results", [])
        ]
        return WebExtractResult(
            pages=pages,
            failed=[
                WebExtractFailure(url=item["url"], error=str(item.get("error") or ""))
                for item in answer.get("failed_results", [])
            ],
            credits=extract_credits(len(pages), q.depth),
            cached=False,
        )

    async def crawl(self, q: WebCrawlQuery) -> WebCrawlResult:
        answer = await self._call(
            lambda: self._client.crawl(
                url=str(q.url),
                max_depth=q.max_depth,
                limit=q.limit,
                instructions=q.instructions,
                select_paths=q.select_paths or None,
                format="markdown",
            )
        )
        pages = [
            WebPage(url=page["url"], content=page.get("raw_content") or "")
            for page in answer.get("results", [])
        ]
        return WebCrawlResult(
            base_url=answer.get("base_url") or str(q.url),
            pages=pages,
            credits=crawl_credits(len(pages), q.instructions),
            cached=False,
        )

    async def map(self, q: WebMapQuery) -> WebMapResult:
        answer = await self._call(
            lambda: self._client.map(
                url=str(q.url), max_depth=q.max_depth, limit=q.limit, instructions=q.instructions
            )
        )
        urls = [str(url) for url in answer.get("results", [])]
        return WebMapResult(
            base_url=answer.get("base_url") or str(q.url),
            urls=urls,
            credits=map_credits(len(urls), q.instructions),
            cached=False,
        )
