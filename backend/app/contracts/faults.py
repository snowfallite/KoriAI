"""Fault plans the fakes execute (tech.md §8.1)."""

from typing import Literal

from app.contracts.common import Contract, ErrorCode


class FaultRule(Contract):
    method: str  # a port method name
    mode: Literal["error", "timeout", "rate_limit", "latency", "empty"]
    error_code: ErrorCode | None = None
    times: int = 1  # how many calls in a row fail
    after_calls: int = 0  # how many calls pass before the fault
    latency_ms: int = 0
    match: dict[str, str] = {}  # argument filter, compared as strings


class FaultPlan(Contract):
    rules: list[FaultRule] = []
