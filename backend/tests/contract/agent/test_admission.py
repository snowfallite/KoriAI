"""A question over the budget gets no run (F-05 AC 4, 5; tech.md §6.5, §6.7, §9.5): 503
llm_quota_exhausted when no family is allowed, 429 user_budget_exhausted when the user spent the
day in tokens of lite; the owner has no daily cap. A refused question leaves no thread, message
or run behind."""

from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import insert, select

from app.contracts.common import ErrorOut
from app.contracts.llm import ModelFamily
from app.core import time
from app.db.schema.agent import AgentRun, UsageDaily
from app.db.schema.chat import Message, Thread
from tests.support.chat import settle, user_id_of
from tests.support.seed import seed_user, sign_in

QUESTION = "Что такое дюрация облигации?"
FAMILIES: tuple[ModelFamily, ...] = ("lite", "pro", "max", "ultra")


async def spend(app: FastAPI, user_id: UUID | None, family: ModelFamily, amount: int) -> None:
    row = insert(UsageDaily).values(
        day=time.msk_day(), user_id=user_id, resource=f"llm:{family}", amount=amount
    )
    await app.state.engine.execute(row)


async def count(app: FastAPI, model: Any) -> int:
    return len((await app.state.engine.execute(select(model))).all())


async def post(api: httpx.AsyncClient) -> httpx.Response:
    return await api.post("/api/chat/messages", json={"thread_id": None, "text": QUESTION})


async def nothing_written(app: FastAPI) -> bool:
    return [await count(app, model) for model in (Thread, Message, AgentRun)] == [0, 0, 0]


@pytest.fixture
async def owner_api(api: httpx.AsyncClient, seeded: None) -> httpx.AsyncClient:
    await sign_in(api, seed_user("owner").email)
    return api


async def test_a_question_without_an_allowed_family_is_refused_before_its_run(
    app: FastAPI, user_api: httpx.AsyncClient
) -> None:
    for family in FAMILIES:  # the whole quota: the reserve refuses every family any day
        await spend(app, None, family, app.state.settings.LLM_QUOTAS[family])

    reply = await post(user_api)

    assert reply.status_code == 503
    error = ErrorOut.model_validate(reply.json())
    assert (error.code, error.message) == ("llm_quota_exhausted", "Квота модели исчерпана")
    assert await nothing_written(app)


@pytest.mark.parametrize(
    "spent",
    [
        {"lite": 600_000},
        {"pro": 96_000},  # 96k x 6.25 = 600k tokens of lite
        {"lite": 100_000, "max": 50_000},  # 100k + 50k x 10
    ],
)
async def test_a_user_who_spent_the_day_is_refused_before_the_run(
    app: FastAPI, user_api: httpx.AsyncClient, spent: dict[ModelFamily, int]
) -> None:
    user = await user_id_of(user_api)
    for family, amount in spent.items():
        await spend(app, user, family, amount)

    reply = await post(user_api)

    assert reply.status_code == 429
    error = ErrorOut.model_validate(reply.json())
    assert error.code == "user_budget_exhausted"
    assert error.message and error.request_id
    assert await nothing_written(app)


async def test_a_day_short_of_the_cap_lets_the_question_in(
    app: FastAPI, user_api: httpx.AsyncClient
) -> None:
    await spend(app, await user_id_of(user_api), "lite", 599_999)

    reply = await post(user_api)
    await settle(app)

    assert reply.status_code == 202
    assert await count(app, AgentRun) == 1


async def test_the_owner_has_no_daily_cap(app: FastAPI, owner_api: httpx.AsyncClient) -> None:
    await spend(app, await user_id_of(owner_api), "lite", 5_000_000)

    reply = await post(owner_api)
    await settle(app)

    assert reply.status_code == 202
    assert await count(app, AgentRun) == 1
