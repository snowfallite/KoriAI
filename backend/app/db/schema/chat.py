"""Chat and answers (tech.md §5.3)."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Computed, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.db.schema.base import Base, Json, Now, UpdatedAt, UuidPk


class Thread(Base):
    __tablename__ = "threads"
    __table_args__ = (CheckConstraint("title_source in ('auto','user')", name="title_source"),)

    id: Mapped[UuidPk]
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str | None]
    title_source: Mapped[str] = mapped_column(server_default="auto")
    summary: Mapped[str | None]  # compressed history for the context (§9.12)
    summary_upto_id: Mapped[uuid.UUID | None]  # last message folded into summary
    message_count: Mapped[int] = mapped_column(server_default=text("0"))
    last_message_at: Mapped[datetime | None]
    archived_at: Mapped[datetime | None]
    created_at: Mapped[Now]
    updated_at: Mapped[UpdatedAt]


Index(
    "threads_user_recent_idx",
    Thread.user_id,
    Thread.last_message_at.desc().nulls_last(),
    postgresql_where=Thread.archived_at.is_(None),
)
Index(
    "threads_title_trgm",
    Thread.title,
    postgresql_using="gin",
    postgresql_ops={"title": "gin_trgm_ops"},
)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("role in ('user','assistant')", name="role"),
        CheckConstraint("status in ('complete','partial','failed')", name="status"),
    )

    id: Mapped[UuidPk]
    thread_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("threads.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[str]
    content: Mapped[str]  # markdown with placeholders (§9.9)
    status: Mapped[str] = mapped_column(server_default="complete")
    # agent_runs points back at messages: the key is added after both tables exist.
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", name="messages_run_fk", ondelete="SET NULL", use_alter=True)
    )
    meta: Mapped[Json] = mapped_column(server_default=text("'{}'"))  # MessageMeta (§6.6)
    created_at: Mapped[Now]
    search_tsv: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed("to_tsvector('russian', content)", persisted=True)
    )


Index("messages_thread_idx", Message.thread_id, Message.created_at)
Index("messages_user_search_idx", Message.search_tsv, postgresql_using="gin")
Index("messages_user_idx", Message.user_id, Message.created_at.desc())
