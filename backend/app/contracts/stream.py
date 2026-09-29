"""Run events of the SSE stream (tech.md §7)."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, JsonValue

from app.contracts.agent import Intent
from app.contracts.artifacts import ArtifactOut, SourceRef
from app.contracts.common import (
    Contract,
    ErrorCode,
    ErrorOut,
    RunStatus,
    ToolName,
    UtcDatetime,
    WarningCode,
)
from app.contracts.llm import ModelFamily


class _Event(Contract):
    seq: int = Field(ge=1)  # grows by 1 within a stream
    run_id: UUID
    ts: UtcDatetime


class RunQueuedEvent(_Event):
    type: Literal["run.queued"] = "run.queued"
    position: int


class RunStartedEvent(_Event):
    type: Literal["run.started"] = "run.started"


class RunRoutedEvent(_Event):
    type: Literal["run.routed"] = "run.routed"
    intent: Intent
    family: ModelFamily
    model_id: str
    reason: str


class StepStartedEvent(_Event):
    type: Literal["step.started"] = "step.started"
    step: int


class ToolStartedEvent(_Event):
    type: Literal["tool.started"] = "tool.started"
    step: int
    call_id: str
    tool: ToolName
    title: str  # for people, e.g. «Загружаю портфель»


class ToolFinishedEvent(_Event):
    type: Literal["tool.finished"] = "tool.finished"
    step: int
    call_id: str
    tool: ToolName
    ok: bool
    summary: str = Field(max_length=200)
    error_code: ErrorCode | None
    duration_ms: int


class ArtifactCreatedEvent(_Event):
    type: Literal["artifact.created"] = "artifact.created"
    artifact: ArtifactOut


class SourceAddedEvent(_Event):
    type: Literal["source.added"] = "source.added"
    source: SourceRef


class TextDeltaEvent(_Event):
    type: Literal["text.delta"] = "text.delta"
    delta: str


class TextResetEvent(_Event):
    """The model called a function after some text: the client drops the text so far."""

    type: Literal["text.reset"] = "text.reset"


class RunWarningEvent(_Event):
    type: Literal["run.warning"] = "run.warning"
    code: WarningCode
    message: str


class RunFinishedEvent(_Event):
    """Always the last event; the client then takes the answer from REST."""

    type: Literal["run.finished"] = "run.finished"
    status: RunStatus
    message_id: UUID | None
    error: ErrorOut | None


class DevEchoEvent(_Event):
    """Only in dev and ci (POST /api/dev/echo)."""

    type: Literal["dev.echo"] = "dev.echo"
    payload: dict[str, JsonValue]


type StreamEvent = Annotated[
    RunQueuedEvent
    | RunStartedEvent
    | RunRoutedEvent
    | StepStartedEvent
    | ToolStartedEvent
    | ToolFinishedEvent
    | ArtifactCreatedEvent
    | SourceAddedEvent
    | TextDeltaEvent
    | TextResetEvent
    | RunWarningEvent
    | RunFinishedEvent
    | DevEchoEvent,
    Field(discriminator="type"),
]
