"""Spend of the models (tech.md §5.5, §9.5): the service since the start of the quota period, a
user on a Moscow day, the background jobs on a Moscow day."""

import uuid
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from fastapi import FastAPI
from sqlalchemy import insert

from app.db.base import UnitOfWork
from app.db.schema.agent import LlmCall, UsageDaily
from app.db.schema.users import User
from app.domains.usage.service import UsageService

START = date(2026, 9, 26)
TODAY = date(2026, 10, 23)


async def new_user(app: FastAPI) -> UUID:
    row = insert(User).values(email=f"{uuid.uuid4().hex}@example.test", password_hash="x")
    user_id: UUID = (await app.state.engine.execute(row.returning(User.id))).scalar_one()
    return user_id


async def usage(app: FastAPI, day: date, user_id: UUID | None, resource: str, amount: int) -> None:
    row = insert(UsageDaily).values(
        day=day, user_id=user_id, resource=resource, amount=amount, calls=1
    )
    await app.state.engine.execute(row)


async def call(app: FastAPI, **values: Any) -> None:
    row = {
        "purpose": "title",
        "priority": "background",
        "family": "lite",
        "model_id": "GigaChat-2",
        "status": "ok",
        **values,
    }
    await app.state.engine.execute(insert(LlmCall).values(**row))


def service(app: FastAPI) -> UsageService:
    return UsageService(UnitOfWork(app.state.engine))


async def test_the_service_spend_sums_its_rows_of_each_family_since_the_start(
    app: FastAPI,
) -> None:
    user = await new_user(app)
    await usage(app, START, None, "llm:pro", 1_000)
    await usage(app, TODAY, None, "llm:pro", 250)
    await usage(app, TODAY, None, "llm:max", 70)
    await usage(app, date(2026, 9, 25), None, "llm:pro", 9_999)  # the period before
    await usage(app, TODAY, user, "llm:pro", 1_250)  # a user's row repeats the service's
    await usage(app, TODAY, None, "web:credits", 3)

    spend = await service(app).service_period(START)

    assert spend == {"pro": 1_250, "max": 70}


async def test_a_user_spend_reads_the_rows_of_that_user_and_day(app: FastAPI) -> None:
    user, other = await new_user(app), await new_user(app)
    await usage(app, TODAY, user, "llm:lite", 500)
    await usage(app, TODAY, user, "llm:ultra", 40)
    await usage(app, TODAY, user, "web:credits", 2)
    await usage(app, date(2026, 10, 22), user, "llm:lite", 7_000)  # yesterday
    await usage(app, TODAY, other, "llm:lite", 8_000)
    await usage(app, TODAY, None, "llm:lite", 8_500)

    spend = await service(app).user_day(user, TODAY)

    assert spend == {"lite": 500, "ultra": 40}


async def test_the_background_spend_counts_its_calls_since_moscow_midnight(app: FastAPI) -> None:
    # 23.10 starts in Moscow at 21:00 UTC of 22.10.
    await call(app, billable_tokens=300, created_at=datetime(2026, 10, 22, 21, 30, tzinfo=UTC))
    await call(
        app, billable_tokens=45, family="max", created_at=datetime(2026, 10, 23, 9, 0, tzinfo=UTC)
    )
    await call(app, billable_tokens=900, created_at=datetime(2026, 10, 22, 20, 50, tzinfo=UTC))
    await call(
        app,
        billable_tokens=5_000,
        priority="interactive",
        purpose="agent_step",
        created_at=datetime(2026, 10, 23, 9, 0, tzinfo=UTC),
    )

    spend = await service(app).background_day(TODAY)

    assert spend == {"lite": 300, "max": 45}
