"""Shared contract types (tech.md §6.1, §6.7, §12)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, JsonValue

ErrorCode = Literal[
    "unauthorized",
    "invalid_credentials",
    "forbidden",
    "registration_closed",
    "not_found",
    "conflict",
    "run_active",
    "email_taken",
    "broker_not_connected",
    "gone",
    "validation_error",
    "invite_required",
    "invite_invalid",
    "token_invalid",
    "token_not_read_only",
    "rate_limited",
    "user_budget_exhausted",
    "llm_busy",
    "llm_quota_exhausted",
    "tinvest_unavailable",
    "tinvest_rate_limited",
    "web_unavailable",
    "web_credits_exhausted",
    "disclosure_unavailable",
    "internal",
]


class ErrorOut(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: ErrorCode
    message: str
    details: dict[str, JsonValue] | None = None
    request_id: str
