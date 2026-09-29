"""LLM contract types (tech.md §8.3)."""

from typing import Literal
from uuid import UUID

from app.contracts.common import Contract

type ModelFamily = Literal["lite", "pro", "max", "ultra"]
type Priority = Literal["interactive", "background"]
type LlmPurpose = Literal[
    "classify", "agent_step", "synthesize", "title", "summarize", "ifrs_extract", "other"
]


class LlmCallCtx(Contract):
    purpose: LlmPurpose
    priority: Priority
    family: ModelFamily
    model_id: str
    user_id: UUID | None = None
    run_id: UUID | None = None
    job_id: int | None = None
    session_id: str | None = None  # goes to X-Session-ID
