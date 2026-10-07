"""Queries of the broker connection and its accounts (tech.md §5.2)."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.schema.broker import BrokerAccount, BrokerConnection

# acc2 before acc10
ALIAS_ORDER = (func.length(BrokerAccount.alias), BrokerAccount.alias)


async def connection(session: AsyncSession, user_id: UUID) -> BrokerConnection | None:
    return await session.scalar(select(BrokerConnection).where(BrokerConnection.user_id == user_id))


async def accounts(session: AsyncSession, connection_id: UUID) -> Sequence[BrokerAccount]:
    query = (
        select(BrokerAccount)
        .where(BrokerAccount.connection_id == connection_id)
        .order_by(*ALIAS_ORDER)
    )
    return (await session.scalars(query)).all()


async def visible_accounts(session: AsyncSession, user_id: UUID) -> Sequence[BrokerAccount]:
    query = (
        select(BrokerAccount)
        .join(BrokerConnection, BrokerConnection.id == BrokerAccount.connection_id)
        .where(BrokerConnection.user_id == user_id, BrokerAccount.is_hidden.is_(False))
        .order_by(*ALIAS_ORDER)
    )
    return (await session.scalars(query)).all()
