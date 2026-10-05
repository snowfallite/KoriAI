"""usage_daily (tech.md §5.5): a call of the LLM or Tavily adds to the user's row and the
service's row (user_id null) of its Moscow day."""

from collections.abc import Callable
from datetime import date
from typing import Literal
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession

from app.db.schema.agent import UsageDaily

type Resource = Literal["llm:lite", "llm:pro", "llm:max", "llm:ultra", "web:credits"]
# The database as the app state holds it now: contract tests swap the engine for a connection.
type Bind = Callable[[], AsyncEngine | AsyncConnection]


async def add_usage(
    session: AsyncSession, *, day: date, user_id: UUID | None, resource: Resource, amount: int
) -> None:
    # The user's row first, then the service's: every writer locks them in this order.
    for owner in [user_id, None] if user_id is not None else [None]:
        row = insert(UsageDaily).values(
            day=day, user_id=owner, resource=resource, amount=amount, calls=1
        )
        await session.execute(
            row.on_conflict_do_update(
                index_elements=["day", "user_id", "resource"],
                set_={
                    "amount": UsageDaily.amount + row.excluded.amount,
                    "calls": UsageDaily.calls + row.excluded.calls,
                },
            )
        )
