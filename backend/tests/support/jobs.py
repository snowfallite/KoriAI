"""Idempotency harness of queue tasks (tech.md §10.1, §14.2)."""

from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from sqlalchemy import Row, select, table, text
from sqlalchemy.ext.asyncio import AsyncEngine

type Snapshot = dict[str, list[Row[Any]]]


async def snapshot(engine: AsyncEngine, tables: Sequence[str]) -> Snapshot:
    async with engine.connect() as conn:
        return {
            name: sorted(
                (await conn.execute(select(text("*")).select_from(table(name)))).all(), key=repr
            )
            for name in tables
        }


async def run_twice(
    run: Callable[[], Awaitable[object]], engine: AsyncEngine, *tables: str
) -> Snapshot:
    """Runs a handler twice with the same payload: the second run must leave the tables it
    touches as the first run left them. Returns their rows after the first run."""
    await run()
    first = await snapshot(engine, tables)
    await run()
    assert await snapshot(engine, tables) == first, "the second run changed the tables"
    return first
