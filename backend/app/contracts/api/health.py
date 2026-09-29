"""Service DTOs: health and the dev endpoints (tech.md §6.7)."""

from typing import Literal
from uuid import UUID

from pydantic import JsonValue

from app.contracts.common import Contract


class HealthOut(Contract):
    status: Literal["ok"]


class LlmGateOut(Contract):
    capacity: int
    in_use: int
    waiting: int


class ReadyOut(Contract):
    db: bool
    qdrant: bool
    queue: bool
    llm_gate: LlmGateOut


class EchoIn(Contract):
    payload: dict[str, JsonValue]


class EchoOut(Contract):
    stream_id: UUID


class DemoJobIn(Contract):
    key: str
    value: str


class DemoJobOut(Contract):
    job_id: int
