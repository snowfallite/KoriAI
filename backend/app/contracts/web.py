"""DTOs of the web search port, Tavily (tech.md §8.4)."""

from datetime import date
from typing import Literal

from pydantic import Field, HttpUrl

from app.contracts.common import Contract

type WebTopic = Literal["general", "news", "finance"]
type WebDepth = Literal["basic", "advanced"]
type TimeRange = Literal["day", "week", "month", "year"]


class WebSearchQuery(Contract):
    query: str = Field(min_length=1, max_length=400)
    topic: WebTopic
    depth: WebDepth
    time_range: TimeRange | None
    max_results: int = Field(ge=1, le=10)
    include_domains: list[str]
    exclude_domains: list[str]
    include_images: bool


class WebHit(Contract):
    url: str
    title: str
    content: str
    score: float
    published_date: date | None


class WebImage(Contract):
    url: str
    description: str | None


class WebSearchResult(Contract):
    hits: list[WebHit]
    images: list[WebImage]
    credits: int
    cached: bool


class WebExtractQuery(Contract):
    urls: list[HttpUrl] = Field(min_length=1, max_length=20)
    depth: WebDepth


class WebPage(Contract):
    url: str
    content: str  # markdown


class WebExtractFailure(Contract):
    url: str
    error: str


class WebExtractResult(Contract):
    pages: list[WebPage]
    failed: list[WebExtractFailure]
    credits: int
    cached: bool


class WebCrawlQuery(Contract):
    url: HttpUrl
    instructions: str | None
    max_depth: int = Field(ge=1, le=2)
    limit: int = Field(ge=1, le=10)
    select_paths: list[str]


class WebCrawlResult(Contract):
    base_url: str
    pages: list[WebPage]
    credits: int
    cached: bool


class WebMapQuery(Contract):
    url: HttpUrl
    instructions: str | None
    max_depth: int = Field(ge=1, le=2)
    limit: int = Field(ge=1, le=50)


class WebMapResult(Contract):
    base_url: str
    urls: list[str]
    credits: int
    cached: bool
