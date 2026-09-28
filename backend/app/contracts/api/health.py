"""Health DTOs (tech.md §6.7)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthOut(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["ok"]


class LlmGateOut(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capacity: int
    in_use: int
    waiting: int


class ReadyOut(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    db: bool
    qdrant: bool
    queue: bool
    llm_gate: LlmGateOut
