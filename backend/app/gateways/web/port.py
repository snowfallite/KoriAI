"""Web search port, Tavily (tech.md §8.4)."""

from typing import Protocol

from app.contracts.web import (
    WebCrawlQuery,
    WebCrawlResult,
    WebExtractQuery,
    WebExtractResult,
    WebMapQuery,
    WebMapResult,
    WebSearchQuery,
    WebSearchResult,
)


class WebSearchPort(Protocol):
    async def search(self, q: WebSearchQuery) -> WebSearchResult: ...
    async def extract(self, q: WebExtractQuery) -> WebExtractResult: ...
    async def crawl(self, q: WebCrawlQuery) -> WebCrawlResult: ...
    async def map(self, q: WebMapQuery) -> WebMapResult: ...
