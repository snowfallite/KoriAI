"""Queries of the model spend (tech.md §5.5): sums of usage_daily and of llm_calls."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.llm import ModelFamily
from app.db.schema.agent import LlmCall, UsageDaily

FAMILY_OF: dict[str, ModelFamily] = {
    "llm:lite": "lite",
    "llm:pro": "pro",
    "llm:max": "max",
    "llm:ultra": "ultra",
}


async def service_since(session: AsyncSession, start: date) -> dict[ModelFamily, int]:
    query = (
        select(UsageDaily.resource, func.sum(UsageDaily.amount))
        .where(
            UsageDaily.user_id.is_(None),
            UsageDaily.day >= start,
            UsageDaily.resource.in_(FAMILY_OF),
        )
        .group_by(UsageDaily.resource)
    )
    return {FAMILY_OF[resource]: int(total) for resource, total in await session.execute(query)}


async def user_day(session: AsyncSession, user_id: UUID, day: date) -> dict[ModelFamily, int]:
    query = select(UsageDaily.resource, UsageDaily.amount).where(
        UsageDaily.user_id == user_id,
        UsageDaily.day == day,
        UsageDaily.resource.in_(FAMILY_OF),
    )
    return {FAMILY_OF[resource]: amount for resource, amount in await session.execute(query)}


async def background_since(session: AsyncSession, start: datetime) -> dict[ModelFamily, int]:
    """§9.5: the background spend of a day comes from llm_calls, usage_daily has no priority."""
    query = (
        select(LlmCall.family, func.sum(LlmCall.billable_tokens))
        .where(LlmCall.priority == "background", LlmCall.created_at >= start)
        .group_by(LlmCall.family)
    )
    rows = await session.execute(query)
    return {FAMILY_OF[f"llm:{family}"]: int(total) for family, total in rows}
