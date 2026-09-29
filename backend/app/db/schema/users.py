"""Users and access (tech.md §5.1)."""

import uuid
from datetime import datetime
from ipaddress import IPv4Address, IPv6Address

from sqlalchemy import CheckConstraint, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from app.db.schema.base import Base, IdentityPk, Json, Now, UpdatedAt, UuidPk


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("email = lower(email)", name="email"),
        CheckConstraint("role in ('user','owner')", name="role"),
        CheckConstraint("status in ('active','disabled')", name="status"),
    )

    id: Mapped[UuidPk]
    email: Mapped[str] = mapped_column(unique=True)
    password_hash: Mapped[str]
    display_name: Mapped[str | None]
    role: Mapped[str] = mapped_column(server_default="user")
    status: Mapped[str] = mapped_column(server_default="active")
    created_at: Mapped[Now]
    updated_at: Mapped[UpdatedAt]
    last_login_at: Mapped[datetime | None]


class UserSession(Base):
    __tablename__ = "sessions"

    id: Mapped[UuidPk]
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[bytes] = mapped_column(unique=True)  # sha256(token)
    created_at: Mapped[Now]
    last_seen_at: Mapped[Now]
    expires_at: Mapped[datetime]
    ip: Mapped[IPv4Address | IPv6Address | None] = mapped_column(INET)
    user_agent: Mapped[str | None]


Index("sessions_user_idx", UserSession.user_id)
Index("sessions_expires_idx", UserSession.expires_at)


class Invite(Base):
    __tablename__ = "invites"

    id: Mapped[UuidPk]
    code_hash: Mapped[bytes] = mapped_column(unique=True)  # sha256(code)
    note: Mapped[str | None]
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    expires_at: Mapped[datetime]
    used_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True
    )
    used_at: Mapped[datetime | None]
    created_at: Mapped[Now]


class UserSettings(Base):
    __tablename__ = "user_settings"
    __table_args__ = (
        CheckConstraint("model_mode in ('auto','lite','pro','max','ultra')", name="model_mode"),
        CheckConstraint("answer_style in ('concise','detailed')", name="answer_style"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    model_mode: Mapped[str] = mapped_column(server_default="auto")
    answer_style: Mapped[str] = mapped_column(server_default="concise")
    default_account: Mapped[str | None]  # alias acc1..; null means all accounts
    updated_at: Mapped[UpdatedAt]


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint(
            "kind in ('register','login','login_failed','logout','logout_all',"
            "'password_changed','broker_connected','broker_disconnected','broker_verify_failed')",
            name="kind",
        ),
    )

    id: Mapped[IdentityPk]
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    kind: Mapped[str]
    ip: Mapped[IPv4Address | IPv6Address | None] = mapped_column(INET)
    meta: Mapped[Json] = mapped_column(server_default=text("'{}'"))
    created_at: Mapped[Now]


Index("audit_events_user_idx", AuditEvent.user_id, AuditEvent.created_at.desc())
