"""Queries of the instrument reference (tech.md §5.2)."""

from collections.abc import Collection, Sequence
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.schema.broker import Instrument


async def by_uids(session: AsyncSession, uids: Collection[UUID]) -> Sequence[Instrument]:
    return (await session.scalars(select(Instrument).where(Instrument.uid.in_(uids)))).all()


async def by_ticker(session: AsyncSession, ticker: str, class_code: str) -> Instrument | None:
    query = select(Instrument).where(
        Instrument.ticker == ticker, Instrument.class_code == class_code
    )
    return await session.scalar(query)


async def add_missing(session: AsyncSession, rows: Sequence[dict[str, object]]) -> None:
    """Adds new instruments. A row whose uid, or ticker and class code, is taken stays out:
    instruments.refresh (F-08) brings the stored ones up to date."""
    if rows:
        await session.execute(insert(Instrument).values(list(rows)).on_conflict_do_nothing())


async def has_logo(session: AsyncSession, logo_base: str) -> bool:
    found = await session.scalar(select(exists().where(Instrument.logo_base == logo_base)))
    return bool(found)
