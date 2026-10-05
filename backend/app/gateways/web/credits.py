"""Tavily credits (tech.md §8.4): the price formula, the monthly and the daily budgets."""

import math
from contextvars import ContextVar
from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.web import (
    WebCrawlQuery,
    WebDepth,
    WebExtractQuery,
    WebMapQuery,
    WebSearchQuery,
)
from app.core.errors import QuotaExhaustedError
from app.db.schema.agent import UsageDaily

type WebQuery = WebSearchQuery | WebExtractQuery | WebCrawlQuery | WebMapQuery

# The user whose day budget a call spends; the agent sets it for its run, jobs leave it empty.
acting_user: ContextVar[UUID | None] = ContextVar("web_acting_user", default=None)


def _depth(depth: WebDepth) -> int:
    return 2 if depth == "advanced" else 1


def search_credits(depth: WebDepth) -> int:
    return _depth(depth)


def extract_credits(pages: int, depth: WebDepth) -> int:
    """Per 5 extracted pages, rounded up; failed URLs are free."""
    return math.ceil(pages / 5) * _depth(depth)


def map_credits(pages: int, instructions: str | None) -> int:
    return math.ceil(pages / 10) * (2 if instructions else 1)


def crawl_credits(pages: int, instructions: str | None) -> int:
    """A crawl maps the site and extracts what it found."""
    return map_credits(pages, instructions) + extract_credits(pages, "basic")


def estimate(q: WebQuery) -> int:
    """The most a call costs: every URL extracted, every page of the limit crawled."""
    match q:
        case WebSearchQuery():
            return search_credits(q.depth)
        case WebExtractQuery():
            return extract_credits(len(q.urls), q.depth)
        case WebCrawlQuery():
            return crawl_credits(q.limit, q.instructions)
        case WebMapQuery():
            return map_credits(q.limit, q.instructions)


async def check_budget(
    session: AsyncSession,
    *,
    need: int,
    user_id: UUID | None,
    today: date,
    monthly: int,
    daily: int,
) -> None:
    """QuotaExhaustedError when the call would pass the monthly budget of the service
    (calendar month, Moscow) or the day limit of the user."""
    spent = select(func.coalesce(func.sum(UsageDaily.amount), 0)).where(
        UsageDaily.resource == "web:credits"
    )
    month = spent.where(UsageDaily.user_id.is_(None), UsageDaily.day >= today.replace(day=1))
    if (await session.scalar(month) or 0) + need > monthly:
        raise QuotaExhaustedError("web_credits_exhausted")
    if user_id is not None:
        mine = spent.where(UsageDaily.user_id == user_id, UsageDaily.day == today)
        if (await session.scalar(mine) or 0) + need > daily:
            raise QuotaExhaustedError("web_credits_exhausted")
