"""Queries of the broker connection and its accounts (tech.md §5.1, §5.2)."""

from collections.abc import Collection, Sequence
from datetime import datetime
from ipaddress import IPv4Address, IPv6Address
from typing import Literal
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.common import ErrorCode
from app.core.crypto import SealedToken
from app.db.schema.broker import BrokerAccount, BrokerConnection
from app.db.schema.users import AuditEvent

type Ip = IPv4Address | IPv6Address | None
type AuditKind = Literal["broker_connected", "broker_disconnected", "broker_verify_failed"]

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


async def save_connection(
    session: AsyncSession, user_id: UUID, sealed: SealedToken, hint: str, checked_at: datetime
) -> UUID:
    """Stores the token of the user in place of an older one; the connection turns active.

    The upsert locks the row, so a second connect of the user waits for this transaction.
    """
    values = {
        "token_ciphertext": sealed.ciphertext,
        "token_nonce": sealed.nonce,
        "token_key_id": sealed.key_id,
        "token_hint": hint,
        "status": "active",
        "last_verified_at": checked_at,
        "last_error_code": None,
    }
    saved = (
        insert(BrokerConnection)
        .values(user_id=user_id, broker="tinvest", **values)
        .on_conflict_do_update(
            index_elements=[BrokerConnection.user_id, BrokerConnection.broker],
            set_={**values, "updated_at": func.now()},
        )
        .returning(BrokerConnection.id)
    )
    return (await session.execute(saved)).scalar_one()


async def set_check(
    session: AsyncSession,
    connection_id: UUID,
    nonce: bytes,
    status: Literal["active", "invalid"],
    error_code: ErrorCode | None,
    checked_at: datetime,
) -> bool:
    """Records the verdict on the token sealed with `nonce`; False when a new token has taken
    its place meanwhile: that one was checked on its own."""
    checked = (
        update(BrokerConnection)
        .where(BrokerConnection.id == connection_id, BrokerConnection.token_nonce == nonce)
        .values(status=status, last_error_code=error_code, last_verified_at=checked_at)
        .returning(BrokerConnection.id)
    )
    return await session.scalar(checked) is not None


async def delete_connection(session: AsyncSession, user_id: UUID) -> bool:
    """Drops the connection of the user and, by cascade, its accounts; False without one."""
    deleted = (
        delete(BrokerConnection)
        .where(BrokerConnection.user_id == user_id)
        .returning(BrokerConnection.id)
    )
    return await session.scalar(deleted) is not None


async def add_account(
    session: AsyncSession,
    connection_id: UUID,
    external_id: str,
    alias: str,
    values: dict[str, object],
) -> None:
    row = {"connection_id": connection_id, "external_id": external_id, "alias": alias, **values}
    await session.execute(insert(BrokerAccount).values(row))


async def update_account(
    session: AsyncSession, account_id: UUID, values: dict[str, object]
) -> None:
    await session.execute(
        update(BrokerAccount).where(BrokerAccount.id == account_id).values(values)
    )


async def hide_accounts(session: AsyncSession, account_ids: Collection[UUID]) -> None:
    if account_ids:
        await session.execute(
            update(BrokerAccount).where(BrokerAccount.id.in_(account_ids)).values(is_hidden=True)
        )


async def set_hidden(
    session: AsyncSession, user_id: UUID, alias: str, hidden: bool
) -> BrokerAccount | None:
    """The account `alias` of the user after the change; None when the user has no such one."""
    changed = (
        update(BrokerAccount)
        .where(
            BrokerAccount.alias == alias,
            BrokerAccount.connection_id == BrokerConnection.id,
            BrokerConnection.user_id == user_id,
        )
        .values(is_hidden=hidden)
        .returning(BrokerAccount)
        .execution_options(synchronize_session=False)
    )
    return await session.scalar(changed)


async def add_audit(
    session: AsyncSession, kind: AuditKind, user_id: UUID, ip: Ip, meta: dict[str, object]
) -> None:
    await session.execute(insert(AuditEvent).values(kind=kind, user_id=user_id, ip=ip, meta=meta))
