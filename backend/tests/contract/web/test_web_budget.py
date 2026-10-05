"""Tavily calls through budgets and web_cache (S1-09; tech.md §8.4): estimate, the monthly budget
and the day limit of the user, the cache (a hit costs nothing), the call, the credits it cost."""

import uuid
from datetime import timedelta
from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from sqlalchemy import insert, select
from sqlalchemy.dialects.postgresql import insert as upsert

from app.contracts.web import WebMapQuery, WebSearchQuery
from app.core import time
from app.core.errors import QuotaExhaustedError
from app.db.schema.agent import UsageDaily
from app.db.schema.users import User
from app.gateways.web.cache import MeteredWebSearch
from app.gateways.web.credits import acting_user
from app.gateways.web.fake import FakeWebSearch

SEED_QUERY = "сбербанк новости"  # seed/web/sber.yaml
MONTHLY, DAILY = 10, 4


def search(query: str = SEED_QUERY, depth: str = "basic") -> WebSearchQuery:
    return WebSearchQuery.model_validate(
        {
            "query": query,
            "topic": "news",
            "depth": depth,
            "time_range": None,
            "max_results": 5,
            "include_domains": [],
            "exclude_domains": [],
            "include_images": False,
        }
    )


@pytest.fixture
def fake() -> FakeWebSearch:
    return FakeWebSearch()


@pytest.fixture
def web(app: FastAPI, fake: FakeWebSearch) -> MeteredWebSearch:
    settings = app.state.settings.model_copy(
        update={"TAVILY_MONTHLY_CREDITS": MONTHLY, "TAVILY_USER_DAILY_CREDITS": DAILY}
    )
    return MeteredWebSearch(fake, lambda: app.state.engine, settings)


async def new_user(app: FastAPI) -> UUID:
    row = insert(User).values(email=f"{uuid.uuid4().hex}@example.test", password_hash="x")
    user_id: UUID = (await app.state.engine.execute(row.returning(User.id))).scalar_one()
    return user_id


async def spend(app: FastAPI, amount: int, user_id: UUID | None, days_ago: int = 0) -> None:
    """Credits already spent by the user or, with None, by the service."""
    row = upsert(UsageDaily).values(
        day=time.msk_day() - timedelta(days=days_ago),
        user_id=user_id,
        resource="web:credits",
        amount=amount,
        calls=1,
    )
    await app.state.engine.execute(
        row.on_conflict_do_update(
            index_elements=["day", "user_id", "resource"],
            set_={"amount": UsageDaily.amount + row.excluded.amount},
        )
    )


async def usage(app: FastAPI) -> set[tuple[Any, ...]]:
    rows = await app.state.engine.execute(
        select(UsageDaily.user_id, UsageDaily.amount, UsageDaily.calls).where(
            UsageDaily.resource == "web:credits"
        )
    )
    return {tuple(row) for row in rows.all()}


async def test_a_repeat_comes_from_the_cache_for_nothing(
    app: FastAPI, web: MeteredWebSearch, fake: FakeWebSearch
) -> None:
    first = await web.search(search())
    again = await web.search(search("  Сбербанк   НОВОСТИ "))  # case and spaces do not matter

    assert (first.credits, first.cached) == (1, False)
    assert (again.credits, again.cached) == (0, True)
    assert again.hits == first.hits
    assert len(fake.calls) == 1
    assert await usage(app) == {(None, 1, 1)}  # the service pays once


async def test_the_calls_of_a_user_count_for_the_user_and_the_service(
    app: FastAPI, web: MeteredWebSearch
) -> None:
    user_id = await new_user(app)
    token = acting_user.set(user_id)
    try:
        await web.search(search(depth="advanced"))
    finally:
        acting_user.reset(token)

    assert await usage(app) == {(user_id, 2, 1), (None, 2, 1)}


async def test_the_monthly_budget_stops_calls_before_they_go_out(
    app: FastAPI, web: MeteredWebSearch, fake: FakeWebSearch
) -> None:
    await spend(app, MONTHLY, None)

    with pytest.raises(QuotaExhaustedError) as exhausted:
        await web.search(search())

    assert exhausted.value.code == "web_credits_exhausted"
    assert fake.calls == []


async def test_credits_of_an_earlier_month_do_not_count(
    app: FastAPI, web: MeteredWebSearch
) -> None:
    await spend(app, MONTHLY, None, days_ago=40)

    assert (await web.search(search())).credits == 1


async def test_the_day_limit_stops_one_user_only(
    app: FastAPI, web: MeteredWebSearch, fake: FakeWebSearch
) -> None:
    tired, fresh = await new_user(app), await new_user(app)
    await spend(app, DAILY - 1, tired)
    await spend(app, DAILY - 1, None)

    token = acting_user.set(tired)
    try:
        with pytest.raises(QuotaExhaustedError):
            await web.search(search(depth="advanced"))  # 2 more credits pass the limit of 4
    finally:
        acting_user.reset(token)
    token = acting_user.set(fresh)
    try:
        assert (await web.search(search(depth="advanced"))).credits == 2
    finally:
        acting_user.reset(token)
    assert len(fake.calls) == 1


async def test_the_budget_goes_before_the_cache(app: FastAPI, web: MeteredWebSearch) -> None:
    await web.search(search())
    await spend(app, MONTHLY, None)

    # The order of §8.4: a cached answer waits for the budget too.
    with pytest.raises(QuotaExhaustedError):
        await web.search(search())


async def test_an_expired_answer_is_fetched_again(
    app: FastAPI, web: MeteredWebSearch, fake: FakeWebSearch, monkeypatch: pytest.MonkeyPatch
) -> None:
    await web.search(search())
    later = time.now() + timedelta(seconds=app.state.settings.WEB_CACHE_TTL_SEARCH_S + 1)
    monkeypatch.setattr(time, "now", lambda: later)

    again = await web.search(search())

    assert (again.credits, again.cached) == (1, False)
    assert len(fake.calls) == 2


async def test_a_map_costs_what_its_answer_holds(app: FastAPI, web: MeteredWebSearch) -> None:
    query = WebMapQuery.model_validate(
        {"url": "https://news.example.com", "instructions": None, "max_depth": 1, "limit": 50}
    )

    found = await web.map(query)

    # Three URLs in seed/web/sber.yaml: one credit per ten pages, rounded up.
    assert (len(found.urls), found.credits) == (3, 1)
    assert await usage(app) == {(None, 1, 1)}
