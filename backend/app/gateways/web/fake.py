"""Web search fake (tech.md §8.1, §8.4): answers from backend/fixtures/seed/web/*.yaml.

A search matches the fixture by its query without case or extra spaces; extract, crawl and map
match by URL. A URL without a fixture fails to extract, as a dead page fails at Tavily.
"""

import functools
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, InstanceOf, TypeAdapter

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
from app.gateways.fakes import Fake, port_method
from app.gateways.fixtures import SEED, load
from app.gateways.web.credits import (
    crawl_credits,
    extract_credits,
    map_credits,
    search_credits,
)


class _Fixture(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SearchFixture(_Fixture):
    query: str
    hits: list[WebHit]
    images: list[WebImage] = []


class CrawlFixture(_Fixture):
    url: str
    pages: list[WebPage]


class MapFixture(_Fixture):
    url: str
    urls: list[str]


class WebFixtures(_Fixture):
    """The layout of a file in seed/web."""

    search: list[SearchFixture] = []
    extract: list[WebPage] = []
    crawl: list[CrawlFixture] = []
    map: list[MapFixture] = []


def normalized(query: str) -> str:
    return " ".join(query.casefold().split())


def _url(url: object) -> str:
    return str(url).rstrip("/")


@functools.cache
def seed() -> WebFixtures:
    adapter = TypeAdapter(WebFixtures)
    files = [load(path, adapter) for path in sorted((SEED / "web").glob("*.yaml"))]
    return WebFixtures(
        search=[item for f in files for item in f.search],
        extract=[item for f in files for item in f.extract],
        crawl=[item for f in files for item in f.crawl],
        map=[item for f in files for item in f.map],
    )


def _site_allowed(url: str, q: WebSearchQuery) -> bool:
    host = urlsplit(url).hostname or ""

    def within(domain: str) -> bool:
        return host == domain or host.endswith(f".{domain}")

    if q.include_domains and not any(within(d) for d in q.include_domains):
        return False
    return not any(within(d) for d in q.exclude_domains)


def _no_hits(arguments: dict[str, Any]) -> WebSearchResult:
    q: WebSearchQuery = arguments["q"]
    return WebSearchResult(hits=[], images=[], credits=search_credits(q.depth), cached=False)


class FakeWebSearch(Fake):
    port = "web"
    unavailable = "web_unavailable"
    rate_limited = "web_unavailable"  # Tavily's 429 turns into web_unavailable (§8.4)

    def __init__(self, **options: Any) -> None:
        super().__init__(**options)
        fixtures = seed()
        self._searches = {normalized(s.query): s for s in fixtures.search}
        self._pages = {_url(p.url): p for p in fixtures.extract}
        self._crawls = {_url(c.url): c for c in fixtures.crawl}
        self._maps = {_url(m.url): m for m in fixtures.map}

    @port_method(empty=_no_hits)
    async def search(self, q: InstanceOf[WebSearchQuery]) -> WebSearchResult:
        found = self._searches.get(normalized(q.query))
        if found is None:
            self.no_fixture(f"search {q.query!r}")
            return _no_hits({"q": q})
        hits = [hit for hit in found.hits if _site_allowed(hit.url, q)][: q.max_results]
        return WebSearchResult(
            hits=hits,
            images=found.images if q.include_images else [],
            credits=search_credits(q.depth),
            cached=False,
        )

    @port_method(empty=lambda a: WebExtractResult(pages=[], failed=[], credits=0, cached=False))
    async def extract(self, q: InstanceOf[WebExtractQuery]) -> WebExtractResult:
        pages, failed = [], []
        for url in map(_url, q.urls):
            if url in self._pages:
                pages.append(self._pages[url])
            else:
                failed.append(WebExtractFailure(url=url, error="Страница недоступна"))
        return WebExtractResult(
            pages=pages,
            failed=failed,
            credits=extract_credits(len(pages), q.depth),
            cached=False,
        )

    @port_method(
        empty=lambda a: WebCrawlResult(base_url=str(a["q"].url), pages=[], credits=0, cached=False)
    )
    async def crawl(self, q: InstanceOf[WebCrawlQuery]) -> WebCrawlResult:
        found = self._crawls.get(_url(q.url))
        if found is None:
            self.no_fixture(f"crawl {q.url}")
        pages = found.pages[: q.limit] if found else []
        return WebCrawlResult(
            base_url=str(q.url),
            pages=pages,
            credits=crawl_credits(len(pages), q.instructions),
            cached=False,
        )

    @port_method(
        empty=lambda a: WebMapResult(base_url=str(a["q"].url), urls=[], credits=0, cached=False)
    )
    async def map(self, q: InstanceOf[WebMapQuery]) -> WebMapResult:
        found = self._maps.get(_url(q.url))
        if found is None:
            self.no_fixture(f"map {q.url}")
        urls = found.urls[: q.limit] if found else []
        return WebMapResult(
            base_url=str(q.url),
            urls=urls,
            credits=map_credits(len(urls), q.instructions),
            cached=False,
        )
