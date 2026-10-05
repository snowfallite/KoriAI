"""The LLM gate (tech.md §3.3, AD-05): LLM_MAX_CONCURRENCY slots for calls of the model.

Interactive callers go before background ones, first come first served within a class. A slot
covers one call of /chat/completions: tools run with the slot free.
"""

import asyncio
import time
from collections import deque
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from typing import Protocol

import structlog

from app.contracts.api.health import LlmGateOut
from app.contracts.llm import Priority
from app.core.errors import TransientGatewayError

log = structlog.get_logger(__name__)

# Gets the 1-based place in the queue each time it changes; run.queued carries it (§7).
type OnQueue = Callable[[int], None]


@dataclass(frozen=True, slots=True)
class Ticket:
    owner: str
    priority: Priority
    wait_ms: int  # llm_calls.wait_ms


class LlmGate(Protocol):
    def slot(
        self, priority: Priority, owner: str, *, on_queue: OnQueue | None = None
    ) -> AbstractAsyncContextManager[Ticket]: ...
    def stats(self) -> LlmGateOut: ...


@dataclass(eq=False, slots=True)
class _Waiter:
    owner: str
    on_queue: OnQueue | None
    # The releaser resolves it to hand its slot over.
    granted: asyncio.Future[None] = field(
        default_factory=lambda: asyncio.get_running_loop().create_future()
    )
    position: int = 0


class InProcessPriorityGate:
    """The gate of the one API process (AD-02); an advisory lock of Postgres can replace it."""

    def __init__(self, capacity: int, timeout_s: float) -> None:
        self._capacity = capacity
        self._timeout_s = timeout_s
        self._in_use = 0
        self._queues: dict[Priority, deque[_Waiter]] = {
            "interactive": deque(),
            "background": deque(),
        }

    @asynccontextmanager
    async def slot(
        self, priority: Priority, owner: str, *, on_queue: OnQueue | None = None
    ) -> AsyncIterator[Ticket]:
        started = time.monotonic()
        await self._acquire(priority, owner, on_queue)
        try:
            yield Ticket(owner, priority, round((time.monotonic() - started) * 1000))
        finally:
            self._release()

    def stats(self) -> LlmGateOut:
        waiting = sum(not w.granted.done() for queue in self._queues.values() for w in queue)
        return LlmGateOut(capacity=self._capacity, in_use=self._in_use, waiting=waiting)

    async def _acquire(self, priority: Priority, owner: str, on_queue: OnQueue | None) -> None:
        # Background yields to every waiter, interactive to the interactive ones only.
        ahead = self._queues["interactive"] or (
            priority == "background" and self._queues["background"]
        )
        if self._in_use < self._capacity and not ahead:
            self._in_use += 1
            return
        waiter = _Waiter(owner, on_queue)
        self._queues[priority].append(waiter)
        self._report()
        try:
            async with asyncio.timeout(self._timeout_s):
                await waiter.granted
        except TimeoutError:
            self._give_up(priority, waiter)
            log.warning("llm_gate_timeout", owner=owner, priority=priority)
            raise TransientGatewayError("llm_busy") from None
        except asyncio.CancelledError:
            self._give_up(priority, waiter)
            raise

    def _give_up(self, priority: Priority, waiter: _Waiter) -> None:
        if waiter.granted.done() and not waiter.granted.cancelled():
            self._release()  # the slot came as the wait ended: pass it on
            return
        waiter.granted.cancel()
        queue = self._queues[priority]
        if waiter in queue:  # a release may have dropped it already
            queue.remove(waiter)
        self._report()

    def _release(self) -> None:
        for queue in self._queues.values():  # interactive first: dicts keep their order
            while queue:
                waiter = queue.popleft()
                if not waiter.granted.done():
                    waiter.granted.set_result(None)  # the slot changes hands, in_use stays
                    self._report()
                    return
        self._in_use -= 1

    def _report(self) -> None:
        position = 0
        for waiter in (w for queue in self._queues.values() for w in queue):
            if waiter.granted.done():
                continue
            position += 1
            if waiter.position != position:
                waiter.position = position
                if waiter.on_queue is not None:
                    try:
                        waiter.on_queue(position)
                    except Exception:  # a failing listener must not break the gate
                        log.exception("llm_gate_listener_failed", owner=waiter.owner)
