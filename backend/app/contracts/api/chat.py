"""Chat DTOs: threads, messages, runs (tech.md §6.5, §6.6)."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints

from app.contracts.artifacts import ArtifactOut, SourceRef
from app.contracts.common import (
    Contract,
    ErrorOut,
    MessageRole,
    MessageStatus,
    RunStatus,
    UtcDatetime,
    WarningCode,
)
from app.contracts.llm import ModelFamily


class ThreadOut(Contract):
    id: UUID
    title: str | None
    title_source: Literal["auto", "user"]
    message_count: int
    last_message_at: UtcDatetime | None
    archived: bool
    created_at: UtcDatetime
    snippet: str | None  # the match of a q search


class ThreadPatchIn(Contract):
    title: Annotated[str, StringConstraints(min_length=1, max_length=120)] | None = None
    archived: bool | None = None


class MessageIn(Contract):
    thread_id: UUID | None = None  # null starts a new thread
    text: str = Field(min_length=1, max_length=4000)


class MessageAcceptedOut(Contract):
    thread_id: UUID
    message_id: UUID
    run_id: UUID


class RunOut(Contract):
    id: UUID
    thread_id: UUID
    status: RunStatus
    model_family: ModelFamily | None
    model_id: str | None
    steps: int
    error: ErrorOut | None
    created_at: UtcDatetime
    finished_at: UtcDatetime | None


class MarkdownBlock(Contract):
    type: Literal["markdown"] = "markdown"
    text: str


class ArtifactBlock(Contract):
    type: Literal["artifact"] = "artifact"
    artifact_id: UUID


type MessageBlock = Annotated[MarkdownBlock | ArtifactBlock, Field(discriminator="type")]


class WarningOut(Contract):
    code: WarningCode
    message: str


class MessageMeta(Contract):
    # A user message stores {} (tech.md §5.3), so every field has a default.
    model_family: ModelFamily | None = None
    model_id: str | None = None
    routing_reason: str | None = None
    warnings: list[WarningOut] = []
    ungrounded_numbers: list[str] = []
    disclaimer: bool = False
    tokens_billable: int | None = None
    web_credits: int | None = None


class MessageOut(Contract):
    id: UUID
    role: MessageRole
    status: MessageStatus
    content: str
    blocks: list[MessageBlock]
    artifacts: list[ArtifactOut]
    sources: list[SourceRef]
    meta: MessageMeta
    created_at: UtcDatetime


class ThreadDetailOut(Contract):
    thread: ThreadOut
    messages: list[MessageOut]
    active_run: RunOut | None
