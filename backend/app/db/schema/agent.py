"""Agent runs, artifacts, usage (tech.md §5.5)."""

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.schema.base import Base, IdentityPk, Json, Now, UuidPk

Zero = text("0")


class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint(
            "status in ('queued','running','done','partial','cancelled','failed','interrupted')",
            name="status",
        ),
        CheckConstraint("model_family in ('lite','pro','max','ultra')", name="model_family"),
    )

    id: Mapped[UuidPk]
    thread_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("threads.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    user_message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE")
    )
    assistant_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(server_default="queued")
    cancel_requested: Mapped[bool] = mapped_column(server_default=text("false"))
    profile: Mapped[Json | None]  # TaskProfile (§9.3)
    routing: Mapped[Json | None]  # RoutingDecision (§9.4)
    model_family: Mapped[str | None]
    model_id: Mapped[str | None]
    steps: Mapped[int] = mapped_column(server_default=Zero)
    tokens_billable: Mapped[int] = mapped_column(server_default=Zero)
    tokens_precached: Mapped[int] = mapped_column(server_default=Zero)
    web_credits: Mapped[int] = mapped_column(server_default=Zero)
    error_code: Mapped[str | None]
    created_at: Mapped[Now]
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]


# One active run per user: a second POST /api/chat/messages gets 409 run_active (§3.4).
Index(
    "agent_runs_one_active_idx",
    AgentRun.user_id,
    unique=True,
    postgresql_where=AgentRun.status.in_(["queued", "running"]),
)
Index("agent_runs_thread_idx", AgentRun.thread_id, AgentRun.created_at)


class ToolCall(Base):
    __tablename__ = "tool_calls"

    id: Mapped[IdentityPk]
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"))
    step: Mapped[int]
    tool: Mapped[str]  # ToolName (§12)
    args: Mapped[Json]
    ok: Mapped[bool]
    error_code: Mapped[str | None]
    duration_ms: Mapped[int]
    result_summary: Mapped[str]  # exactly what went to the LLM
    created_at: Mapped[Now]


Index("tool_calls_run_idx", ToolCall.run_id, ToolCall.step)


class LlmCall(Base):
    __tablename__ = "llm_calls"
    __table_args__ = (
        CheckConstraint(
            "purpose in "
            "('classify','agent_step','synthesize','title','summarize','ifrs_extract','other')",
            name="purpose",
        ),
        CheckConstraint("priority in ('interactive','background')", name="priority"),
        CheckConstraint("family in ('lite','pro','max','ultra')", name="family"),
        CheckConstraint(
            "status in ('ok','error','timeout','rate_limited','cancelled')", name="status"
        ),
    )

    id: Mapped[IdentityPk]
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL")
    )
    job_id: Mapped[int | None] = mapped_column(BigInteger)  # procrastinate job id
    purpose: Mapped[str]
    priority: Mapped[str]
    family: Mapped[str]
    model_id: Mapped[str]
    prompt_tokens: Mapped[int] = mapped_column(server_default=Zero)  # without cached tokens
    completion_tokens: Mapped[int] = mapped_column(server_default=Zero)
    precached_tokens: Mapped[int] = mapped_column(server_default=Zero)
    billable_tokens: Mapped[int] = mapped_column(server_default=Zero)  # total_tokens
    wait_ms: Mapped[int] = mapped_column(server_default=Zero)
    duration_ms: Mapped[int] = mapped_column(server_default=Zero)
    status: Mapped[str]
    error_code: Mapped[str | None]
    created_at: Mapped[Now]


Index("llm_calls_created_idx", LlmCall.created_at)
Index("llm_calls_family_idx", LlmCall.family, LlmCall.created_at)
Index("llm_calls_user_idx", LlmCall.user_id, LlmCall.created_at)


class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        CheckConstraint("local_id ~ '^[cti][0-9]+$'", name="local_id"),
        CheckConstraint("kind in ('chart','table','image')", name="kind"),
        UniqueConstraint("run_id", "local_id"),
    )

    id: Mapped[UuidPk]
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE")
    )
    local_id: Mapped[str]
    kind: Mapped[str]
    spec: Mapped[Json]  # ChartSpec | TableSpec | ImageSpec (§9.9)
    created_at: Mapped[Now]


Index("artifacts_message_idx", Artifact.message_id)


class Source(Base):
    __tablename__ = "sources"
    __table_args__ = (
        CheckConstraint("local_id ~ '^s[0-9]+$'", name="local_id"),
        CheckConstraint("kind in ('web','document','tinvest','edisclosure')", name="kind"),
        UniqueConstraint("run_id", "local_id"),
    )

    id: Mapped[UuidPk]
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"))
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE")
    )
    local_id: Mapped[str]
    kind: Mapped[str]
    title: Mapped[str]
    url: Mapped[str | None]
    publisher: Mapped[str | None]
    published_at: Mapped[date | None]
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("disclosure_documents.id", ondelete="SET NULL")
    )
    page: Mapped[int | None]
    snippet: Mapped[str | None]
    created_at: Mapped[Now]


Index("sources_message_idx", Source.message_id)


class UsageDaily(Base):
    __tablename__ = "usage_daily"
    __table_args__ = (
        CheckConstraint(
            "resource in ('llm:lite','llm:pro','llm:max','llm:ultra','web:credits')",
            name="resource",
        ),
        # A null user_id is the whole service: its row must stay unique too.
        UniqueConstraint("day", "user_id", "resource", postgresql_nulls_not_distinct=True),
    )

    day: Mapped[date] = mapped_column()  # Europe/Moscow
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    resource: Mapped[str] = mapped_column()
    amount: Mapped[int] = mapped_column(BigInteger, server_default=Zero)  # tokens or credits
    calls: Mapped[int] = mapped_column(server_default=Zero)

    # The table has no primary key: the ORM identifies rows by the unique key.
    __mapper_args__ = {  # noqa: RUF012
        "primary_key": [day, user_id, resource],
        "eager_defaults": True,
    }


Index("usage_daily_resource_idx", UsageDaily.resource, UsageDaily.day)
