"""Web search through the budget and web_cache (tech.md §8.4).

Order of a call: estimate, the monthly and the daily budget, the cache (a hit costs nothing),
the call, the credits it really cost into usage_daily.
"""

import hashlib
import json
import typing
from collections.abc import Awaitable, Callable
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.config import Settings
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
from app.core import time
from app.db.base import UnitOfWork
from app.db.schema.system import WebCache
from app.gateways.usage import Bind, add_usage
from app.gateways.web.credits import WebQuery, acting_user, check_budget, estimate
from app.gateways.web.port import WebSearchPort

type WebResult = WebSearchResult | WebExtractResult | WebCrawlResult | WebMapResult


def cache_key(kind: str, q: WebQuery) -> bytes:
    """sha256 of the kind and the query; a search ignores case and runs of spaces."""
    request = q.model_dump(mode="json")
    if isinstance(q, WebSearchQuery):
        request["query"] = " ".join(q.query.casefold().split())
    return hashlib.sha256(
        (kind + json.dumps(request, sort_keys=True, ensure_ascii=False)).encode()
    ).digest()


class MeteredWebSearch:
    """WebSearchPort around the adapter or the fake: budgets, cache, usage."""

    def __init__(self, inner: WebSearchPort, bind: Bind, settings: Settings) -> None:
        self.inner = inner
        self._bind = bind
        self._settings = settings

    async def search(self, q: WebSearchQuery) -> WebSearchResult:
        ttl = self._settings.WEB_CACHE_TTL_SEARCH_S
        return await self._call("search", q, self.inner.search, WebSearchResult, ttl)

    async def extract(self, q: WebExtractQuery) -> WebExtractResult:
        ttl = self._settings.WEB_CACHE_TTL_EXTRACT_S
        return await self._call("extract", q, self.inner.extract, WebExtractResult, ttl)

    async def crawl(self, q: WebCrawlQuery) -> WebCrawlResult:
        ttl = self._settings.WEB_CACHE_TTL_EXTRACT_S
        return await self._call("crawl", q, self.inner.crawl, WebCrawlResult, ttl)

    async def map(self, q: WebMapQuery) -> WebMapResult:
        ttl = self._settings.WEB_CACHE_TTL_EXTRACT_S
        return await self._call("map", q, self.inner.map, WebMapResult, ttl)

    async def _call[Q: WebQuery, R: WebResult](
        self,
        kind: str,
        q: Q,
        call: Callable[[Q], Awaitable[R]],
        result: type[R],
        ttl_s: int,
    ) -> R:
        user_id, today, key = acting_user.get(), time.msk_day(), cache_key(kind, q)
        async with UnitOfWork(self._bind()) as session:
            await check_budget(
                session,
                need=estimate(q),
                user_id=user_id,
                today=today,
                monthly=self._settings.TAVILY_MONTHLY_CREDITS,
                daily=self._settings.TAVILY_USER_DAILY_CREDITS,
            )
            hit = await session.scalar(
                select(WebCache.response).where(
                    WebCache.key_hash == key, WebCache.expires_at > time.now()
                )
            )
        if hit is not None:
            # A hit costs nothing (§8.4).
            return typing.cast(R, result.model_validate({**hit, "credits": 0, "cached": True}))

        answer = await call(q)
        row = insert(WebCache).values(
            key_hash=key,
            kind=kind,
            request=q.model_dump(mode="json"),
            response=answer.model_dump(mode="json"),
            credits=answer.credits,
            created_at=time.now(),
            expires_at=time.now() + timedelta(seconds=ttl_s),
        )
        async with UnitOfWork(self._bind()) as session:
            # An expired row of the same request gets the new answer.
            await session.execute(
                row.on_conflict_do_update(
                    index_elements=[WebCache.key_hash],
                    set_={
                        name: row.excluded[name]
                        for name in ("response", "credits", "created_at", "expires_at")
                    },
                )
            )
            if answer.credits:
                await add_usage(
                    session,
                    day=today,
                    user_id=user_id,
                    resource="web:credits",
                    amount=answer.credits,
                )
        return answer
