"""The graph of a run (tech.md §9.1, AD-07): a LangGraph StateGraph of our own nodes, no
checkpointer. F-03 runs its minimal form load_context → agent → postprocess: lite without tools.
"""

import asyncio
from collections.abc import Coroutine
from typing import Any
from uuid import UUID

import structlog
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.messages import AIMessage, BaseMessage
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from app.contracts.common import ErrorCode
from app.contracts.llm import LlmCallCtx
from app.contracts.stream import RunQueuedEvent, StepStartedEvent, TextDeltaEvent, TextResetEvent
from app.core.errors import GatewayError
from app.domains.agent.context import load_context
from app.domains.agent.postprocess import postprocess, run_error
from app.domains.agent.state import AgentState, RunContext

log = structlog.get_logger(__name__)


class _CallStarted(AsyncCallbackHandler):
    """Metering calls the model inside a slot of the gate (§3.3), so the start of the call is
    the moment the run holds its slot: run.started the first time, step.started each step."""

    raise_error = True

    def __init__(self, ctx: RunContext, step: int) -> None:
        self._ctx = ctx
        self._step = step
        self.told = False  # the model got the call: the step counts

    async def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[BaseMessage]],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        if self.told:  # metering retries the same step
            return
        self.told = True
        if not self._ctx.started:
            await self._ctx.start()
        self._ctx.emit(StepStartedEvent, step=self._step)


async def until_cancelled[T](work: Coroutine[Any, Any, T], cancelled: asyncio.Event) -> T | None:
    """The result of the work, or None once the run is cancelled first: the work stops then and
    finishes its own bookkeeping (metering records the cancelled call)."""
    task = asyncio.ensure_future(work)
    stop = asyncio.ensure_future(cancelled.wait())
    try:
        await asyncio.wait({task, stop}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        stop.cancel()
        if not task.done():
            task.cancel()
            await asyncio.wait({task})
    return None if task.cancelled() else task.result()


def _failed(code: ErrorCode, ctx: RunContext, text: str, step: int) -> dict[str, Any]:
    return {
        "status": "failed",
        "error": run_error(code, ctx.ticket.run_id),
        "final_text": text,
        "step": step,
    }


async def agent(state: AgentState, runtime: Runtime[RunContext]) -> dict[str, Any]:
    """One call of the model, its text streamed to the client as it comes (§7)."""
    ctx = runtime.context
    if ctx.cancelled.is_set():
        return {"status": "cancelled", "final_text": ""}
    step = state["step"] + 1
    shown: list[str] = []  # the deltas after the last text.reset

    def on_delta(delta: str) -> None:
        shown.append(delta)
        ctx.emit(TextDeltaEvent, delta=delta)

    def on_reset() -> None:
        shown.clear()
        ctx.emit(TextResetEvent)

    def on_queue(position: int) -> None:
        ctx.emit(RunQueuedEvent, position=position)

    started = _CallStarted(ctx, step)
    model = ctx.llm.chat_model(ctx.model_id, streaming=True).with_config(callbacks=[started])
    call = LlmCallCtx(
        purpose="agent_step",
        priority="interactive",
        family=ctx.family,
        model_id=ctx.model_id,
        user_id=ctx.ticket.user_id,
        run_id=ctx.ticket.run_id,
        session_id=str(ctx.ticket.thread_id),  # X-Session-ID: the cache of the thread (§1)
    )
    work = ctx.metering.stream(
        model,
        state["messages"],
        ctx=call,
        on_delta=on_delta,
        on_reset=on_reset,
        on_queue=on_queue,
    )
    try:
        async with asyncio.timeout_at(ctx.deadline):
            answer = await until_cancelled(work, ctx.cancelled)
    except TimeoutError:
        log.warning("agent_run_timed_out", step=step)
        error: ErrorCode | None = "llm_busy"
        answer = None
    except GatewayError as failure:
        log.warning("agent_step_failed", code=failure.code, step=step)
        error, answer = failure.code, None
    else:
        error = None
    steps = step if started.told else state["step"]
    if error is not None:
        return _failed(error, ctx, "".join(shown), steps)
    if answer is None:
        return {"status": "cancelled", "final_text": "".join(shown), "step": steps}
    return {"status": "done", "final_text": answer.text, "step": steps, **_usage(state, answer)}


def _usage(state: AgentState, answer: AIMessage) -> dict[str, int]:
    usage = answer.usage_metadata
    if usage is None:
        return {}
    details = usage.get("input_token_details") or {}
    return {
        "tokens_billable": state["tokens_billable"] + usage["total_tokens"],
        "tokens_precached": state["tokens_precached"] + details.get("cache_read", 0),
    }


def _graph() -> Any:
    graph = StateGraph(AgentState, context_schema=RunContext)
    graph.add_node("load_context", load_context)
    graph.add_node("agent", agent)
    graph.add_node("postprocess", postprocess)
    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "agent")
    graph.add_edge("agent", "postprocess")
    graph.add_edge("postprocess", END)
    return graph.compile()


GRAPH = _graph()
