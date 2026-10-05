"""What every fake shares (tech.md §8.1): recorded calls, input checked against the port contract,
the fault plan."""

import asyncio
import functools
import inspect
import typing
from collections import Counter
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from pydantic import ConfigDict, ValidationError, validate_call

from app.contracts.common import ErrorCode
from app.contracts.faults import FaultPlan, FaultRule
from app.core.errors import (
    ContractViolation,
    GatewayError,
    PermanentGatewayError,
    QuotaExhaustedError,
    TransientGatewayError,
)

# Port arguments come typed: no str for a UUID, no naive datetime, no float for an int.
STRICT = ConfigDict(strict=True, arbitrary_types_allowed=True)
# Failures that pass with time (§6.7: 500 and 503), and budgets that wait for a new period.
TRANSIENT: frozenset[ErrorCode] = frozenset(
    {
        "internal",
        "llm_busy",
        "tinvest_unavailable",
        "tinvest_rate_limited",
        "web_unavailable",
        "disclosure_unavailable",
    }
)
QUOTA: frozenset[ErrorCode] = frozenset(
    {"llm_quota_exhausted", "user_budget_exhausted", "web_credits_exhausted"}
)


@dataclass(frozen=True, slots=True)
class RecordedCall:
    method: str
    args: dict[str, Any]


def gateway_error(code: ErrorCode, retry_after_s: float | None = None) -> GatewayError:
    """The error a real adapter raises with this code."""
    if code in QUOTA:
        return QuotaExhaustedError(code)
    if code in TRANSIENT:
        return TransientGatewayError(code, retry_after_s)
    return PermanentGatewayError(code)


class Fake:
    """Base of the fakes: records each call, refuses input the port forbids, runs the plan.

    A rule names a method as `get_portfolio` or, where two ports share a name, `web.search`.
    Modes: error raises its code; timeout and rate_limit raise what the real adapter raises,
    rate_limit with latency_ms as Retry-After; latency waits; empty answers with nothing.
    """

    port: str
    unavailable: ErrorCode  # what a timeout of the port turns into
    rate_limited: ErrorCode  # what its 429 turns into

    def __init__(self, *, plan: FaultPlan | None = None, strict: bool = True) -> None:
        self.calls: list[RecordedCall] = []
        # FAKE_STRICT: a request without a fixture fails the test instead of a stand-in answer.
        self.strict = strict
        self.plan = plan or FaultPlan()

    @property
    def plan(self) -> FaultPlan:
        return self._plan

    @plan.setter
    def plan(self, plan: FaultPlan) -> None:
        self._plan = plan
        self._seen: Counter[int] = Counter()  # matching calls per rule

    def no_fixture(self, what: str) -> None:
        """A request the seed has no answer for: a ContractViolation in tests (FAKE_STRICT)."""
        if self.strict:
            raise ContractViolation(f"{type(self).__name__}: no fixture for {what}")

    async def enter(self, method: str, args: dict[str, Any]) -> bool:
        """Records the call and runs the plan; True means answer empty."""
        self.calls.append(RecordedCall(method, args))
        empty = False
        for index, rule in enumerate(self.plan.rules):
            if not self._matches(rule, method, args):
                continue
            seen = self._seen[index]
            self._seen[index] += 1
            if not rule.after_calls <= seen < rule.after_calls + rule.times:
                continue
            match rule.mode:
                case "latency":
                    await asyncio.sleep(rule.latency_ms / 1000)
                case "empty":
                    empty = True
                case _:
                    raise self.failure(rule)
        return empty

    def failure(self, rule: FaultRule) -> Exception:
        """What the real adapter raises for a timeout, a 429 or an error of this rule."""
        match rule.mode:
            case "timeout":
                return TransientGatewayError(self.unavailable)
            case "rate_limit":
                return TransientGatewayError(self.rate_limited, rule.latency_ms / 1000 or None)
            case _:
                return gateway_error(rule.error_code or self.unavailable)

    def _matches(self, rule: FaultRule, method: str, args: dict[str, Any]) -> bool:
        if rule.method not in {method, f"{self.port}.{method}"}:
            return False
        return all(str(args.get(name)) == value for name, value in rule.match.items())


def port_method[**P, R](
    *, empty: Callable[[dict[str, Any]], Any] | None = None
) -> Callable[[Callable[P, Coroutine[Any, Any, R]]], Callable[P, Coroutine[Any, Any, R]]]:
    """A method of a fake port: checks its input, records the call, runs the fault plan.

    `empty(arguments)` gives the answer of the empty mode; without it empty means not found.
    """

    def decorate(
        method: Callable[P, Coroutine[Any, Any, R]],
    ) -> Callable[P, Coroutine[Any, Any, R]]:
        signature = inspect.signature(method)

        def arguments(*args: Any, **kwargs: Any) -> None:
            pass

        # validate_call reads the signature and type hints of the method from this stand-in,
        # so a ValidationError of the method body is never taken for bad input.
        arguments.__signature__ = signature  # type: ignore[attr-defined]
        arguments.__annotations__ = typing.get_type_hints(method, include_extras=True)
        arguments.__qualname__ = method.__qualname__  # names the method in the error
        check = validate_call(config=STRICT)(arguments)

        @functools.wraps(method)
        async def call(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                check(*args, **kwargs)
            except ValidationError as error:
                raise ContractViolation(f"{method.__qualname__}: {error}") from None
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            fake: Fake = bound.arguments.pop("self")
            arguments = dict(bound.arguments)
            if await fake.enter(method.__name__, arguments):
                if empty is None:
                    raise PermanentGatewayError("not_found")
                return typing.cast(R, empty(arguments))
            return await method(*args, **kwargs)

        return call

    return decorate
