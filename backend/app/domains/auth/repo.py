"""Queries of users, sessions, invites and the audit (tech.md §5.1)."""

from datetime import timedelta
from ipaddress import IPv4Address, IPv6Address
from typing import Literal
from uuid import UUID

from sqlalchemy import Row, delete, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.schema.users import AuditEvent, Invite, User, UserSession

type Ip = IPv4Address | IPv6Address | None
type AuditKind = Literal[
    "register", "login", "login_failed", "logout", "logout_all", "password_changed"
]


async def user(session: AsyncSession, user_id: UUID) -> User | None:
    return await session.get(User, user_id)


async def user_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(User.email == email))


async def add_user(
    session: AsyncSession, email: str, password_hash: str, display_name: str | None
) -> User | None:
    """None when the email is taken."""
    row = {"email": email, "password_hash": password_hash, "display_name": display_name}
    added = pg_insert(User).values(row).on_conflict_do_nothing(index_elements=[User.email])
    return await session.scalar(added.returning(User))


async def upsert_owner(session: AsyncSession, email: str, password_hash: str) -> None:
    row = pg_insert(User).values(email=email, password_hash=password_hash, role="owner")
    await session.execute(
        row.on_conflict_do_update(
            index_elements=[User.email],
            set_={"role": "owner", "password_hash": password_hash, "updated_at": func.now()},
        )
    )


async def set_password(session: AsyncSession, user_id: UUID, password_hash: str) -> None:
    await session.execute(
        update(User).where(User.id == user_id).values(password_hash=password_hash)
    )


async def set_last_login(session: AsyncSession, user_id: UUID) -> None:
    await session.execute(update(User).where(User.id == user_id).values(last_login_at=func.now()))


async def add_invites(session: AsyncSession, code_hashes: list[bytes], ttl: timedelta) -> None:
    expires_at = func.now() + ttl
    rows = [{"code_hash": code_hash, "expires_at": expires_at} for code_hash in code_hashes]
    await session.execute(insert(Invite).values(rows))


async def claim_invite(session: AsyncSession, code_hash: bytes) -> UUID | None:
    """Marks a live invite used; None when it is unknown, used or expired."""
    # A concurrent claim waits for the row lock, then fails the used_at filter.
    claimed = (
        update(Invite)
        .where(
            Invite.code_hash == code_hash,
            Invite.used_at.is_(None),
            Invite.expires_at > func.now(),
        )
        .values(used_at=func.now())
        .returning(Invite.id)
    )
    return await session.scalar(claimed)


async def bind_invite(session: AsyncSession, invite_id: UUID, user_id: UUID) -> None:
    await session.execute(update(Invite).where(Invite.id == invite_id).values(used_by=user_id))


async def add_session(
    session: AsyncSession,
    user_id: UUID,
    token_hash: bytes,
    ttl: timedelta,
    ip: Ip,
    user_agent: str | None,
) -> None:
    row = {
        "user_id": user_id,
        "token_hash": token_hash,
        "expires_at": func.now() + ttl,
        "ip": ip,
        "user_agent": user_agent,
    }
    await session.execute(insert(UserSession).values(row))


async def touch_session(
    session: AsyncSession, token_hash: bytes, ttl: timedelta
) -> Row[UUID, UUID, str] | None:
    """Checks a live session of an active user and slides its expiry, in one round trip."""
    touched = (
        update(UserSession)
        .where(
            UserSession.token_hash == token_hash,
            UserSession.expires_at > func.now(),
            UserSession.user_id == User.id,
            User.status == "active",
        )
        .values(last_seen_at=func.now(), expires_at=func.now() + ttl)
        .returning(UserSession.id, UserSession.user_id, User.role)
        .execution_options(synchronize_session=False)
    )
    return (await session.execute(touched)).one_or_none()


async def delete_sessions(
    session: AsyncSession, user_id: UUID, *, only: UUID | None = None, keep: UUID | None = None
) -> None:
    deleted = delete(UserSession).where(UserSession.user_id == user_id)
    if only is not None:
        deleted = deleted.where(UserSession.id == only)
    if keep is not None:
        deleted = deleted.where(UserSession.id != keep)
    await session.execute(deleted)


async def add_audit(session: AsyncSession, kind: AuditKind, user_id: UUID | None, ip: Ip) -> None:
    await session.execute(insert(AuditEvent).values(kind=kind, user_id=user_id, ip=ip))
