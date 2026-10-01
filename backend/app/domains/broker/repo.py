"""Queries of the broker connection and its accounts (tech.md §5.2)."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.schema.broker import BrokerAccount, BrokerConnection


async def connection(session: AsyncSession, user_id: UUID) -> BrokerConnection | None:
    return await session.scalar(select(BrokerConnection).where(BrokerConnection.user_id == user_id))


async def accounts(session: AsyncSession, connection_id: UUID) -> Sequence[BrokerAccount]:
    query = (
        select(BrokerAccount)
        .where(BrokerAccount.connection_id == connection_id)
        .order_by(func.length(BrokerAccount.alias), BrokerAccount.alias)  # acc2 before acc10
    )
    return (await session.scalars(query)).all()
