"""Every call of a model goes through here (tech.md §8.3): a slot of the gate, X-Session-ID, the
timeout, retries of 429 and 5xx, a row of llm_calls and the usage of the day."""

import asyncio
import time
from collections.abc import Awaitable, Callable, Sequence
from contextvars import ContextVar
from typing import Literal

import structlog
from gigachat.context import session_id_cvar
from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    BaseMessageChunk,
    message_chunk_to_message,
)
from langchain_core.runnables import Runnable
from sqlalchemy import insert

from app.config import Settings
from app.contracts.llm import LlmCallCtx, ModelFamily
from app.core import time as clock
from app.core.errors import GatewayError
from app.db.base import UnitOfWork
from app.db.schema.agent import LlmCall
from app.gateways.llm.gate import LlmGate, OnQueue
from app.gateways.llm.gigachat import call_error
from app.gateways.retry import backoff
from app.gateways.usage import Bind, Resource, add_usage

log = structlog.get_logger(__name__)

# The call in progress: the fake model reads its purpose, and no purpose means no metering.
current_call: ContextVar[LlmCallCtx | None] = ContextVar("llm_call", default=None)
RETRIES = 3  # a 429 or a 5xx gets this many more tries inside the slot (§3.3)

type Model = Runnable[LanguageModelInput, BaseMessage]  # a chat model, tools bound or not
RESOURCES: dict[ModelFamily, Resource] = {
    "lite": "llm:lite",
    "pro": "llm:pro",
    "max": "llm:max",
    "ultra": "llm:ultra",
}
type Status = Literal["ok", "error", "timeout", "rate_limited", "cancelled"]


class Metering:
    def __init__(
        self, gate: LlmGate, bind: Bind, settings: Settings, *, backoff_s: float = 0.5
    ) -> None:
        self._gate = gate
        self._bind = bind
        self._timeout_s = settings.GIGACHAT_TIMEOUT_S
        self._backoff_s = backoff_s

    async def invoke(
        self,
        model: Model,
        messages: Sequence[BaseMessage],
        *,
        ctx: LlmCallCtx,
        on_queue: OnQueue | None = None,
    ) -> AIMessage:
        async def call() -> AIMessage:
            return _final(await model.ainvoke(list(messages)))

        return await self._run(ctx, on_queue, call)

    async def stream(
        self,
        model: Model,
        messages: Sequence[BaseMessage],
        *,
        ctx: LlmCallCtx,
        on_delta: Callable[[str], None],
        on_reset: Callable[[], None],
        on_queue: OnQueue | None = None,
    ) -> AIMessage:
        shown = False  # text already went to the client

        async def call() -> AIMessage:
            nonlocal shown
            whole: BaseMessageChunk | None = None
            async for chunk in model.astream(list(messages)):
                if not isinstance(chunk, BaseMessageChunk):
                    raise TypeError(f"a chat model streamed {type(chunk).__name__}")
                whole = chunk if whole is None else whole + chunk
                if isinstance(chunk, AIMessageChunk) and chunk.tool_call_chunks and shown:
                    on_reset()  # the text was a preamble to a function call (§7 text.reset)
                    shown = False
                if delta := str(chunk.text):
                    on_delta(delta)
                    shown = True
            return _final(whole if whole is not None else AIMessageChunk(content=""))

        def before_retry() -> None:
            nonlocal shown
            if shown:  # the next try streams the answer from the start
                on_reset()
                shown = False

        return await self._run(ctx, on_queue, call, before_retry)

    async def _run(
        self,
        ctx: LlmCallCtx,
        on_queue: OnQueue | None,
        call: Callable[[], Awaitable[AIMessage]],
        before_retry: Callable[[], None] | None = None,
    ) -> AIMessage:
        status: Status = "error"
        error_code: str | None = None
        answer: AIMessage | None = None
        wait_ms = duration_ms = 0
        queued = time.monotonic()
        try:
            async with self._gate.slot(ctx.priority, _owner(ctx), on_queue=on_queue) as ticket:
                wait_ms, started = ticket.wait_ms, time.monotonic()
                session, current = session_id_cvar.set(ctx.session_id), current_call.set(ctx)
                try:
                    for attempt in range(RETRIES + 1):
                        try:
                            async with asyncio.timeout(self._timeout_s):
                                answer = await call()
                            status, error_code = "ok", None
                            return answer
                        except Exception as exc:
                            failure = call_error(exc)
                            if failure is None:
                                raise
                            status, error = failure
                            error_code = error.code
                            if not error.retryable or attempt == RETRIES:
                                if error is exc:  # a GatewayError of a model goes up as it is
                                    raise
                                raise error from exc
                        await asyncio.sleep(backoff(attempt, error.retry_after_s, self._backoff_s))
                        if before_retry is not None:
                            before_retry()
                finally:
                    duration_ms = round((time.monotonic() - started) * 1000)
                    current_call.reset(current)
                    session_id_cvar.reset(session)
            raise AssertionError("unreachable")  # pragma: no cover
        except GatewayError as error:
            error_code = error.code  # llm_busy of the gate too: the call never started
            if not wait_ms:
                wait_ms = round((time.monotonic() - queued) * 1000)
            raise
        except asyncio.CancelledError:
            status = "cancelled"
            raise
        finally:
            await self._record(ctx, status, error_code, answer, wait_ms, duration_ms)

    async def _record(
        self,
        ctx: LlmCallCtx,
        status: Status,
        error_code: str | None,
        answer: AIMessage | None,
        wait_ms: int,
        duration_ms: int,
    ) -> None:
        usage = answer.usage_metadata if answer is not None else None
        prompt = usage["input_tokens"] if usage else 0
        completion = usage["output_tokens"] if usage else 0
        billable = usage["total_tokens"] if usage else 0
        details = usage.get("input_token_details") if usage else None
        precached = details.get("cache_read", 0) if details else 0
        try:
            async with UnitOfWork(self._bind()) as session:
                await session.execute(
                    insert(LlmCall).values(
                        user_id=ctx.user_id,
                        run_id=ctx.run_id,
                        job_id=ctx.job_id,
                        purpose=ctx.purpose,
                        priority=ctx.priority,
                        family=ctx.family,
                        model_id=ctx.model_id,
                        prompt_tokens=prompt,
                        completion_tokens=completion,
                        precached_tokens=precached,
                        billable_tokens=billable,
                        wait_ms=wait_ms,
                        duration_ms=duration_ms,
                        status=status,
                        error_code=error_code,
                    )
                )
                if status == "ok" and billable:
                    await add_usage(
                        session,
                        day=clock.msk_day(),
                        user_id=ctx.user_id,
                        resource=RESOURCES[ctx.family],
                        amount=billable,
                    )
        except Exception:  # the answer is paid for: losing it over accounting helps nobody
            log.exception("llm_call_not_recorded", purpose=ctx.purpose, status=status)


def _owner(ctx: LlmCallCtx) -> str:
    if ctx.run_id is not None:
        return f"run:{ctx.run_id}"
    return f"job:{ctx.job_id}" if ctx.job_id is not None else ctx.purpose


def _final(message: BaseMessage) -> AIMessage:
    if isinstance(message, AIMessageChunk):
        message = message_chunk_to_message(message)
    if not isinstance(message, AIMessage):
        raise TypeError(f"a chat model answered with {type(message).__name__}")
    return message
