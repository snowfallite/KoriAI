"""The graph of a run (tech.md §9.1, AD-07): a LangGraph StateGraph of our own nodes, no
checkpointer. F-05 runs load_context → classify → route → agent → postprocess; a run that stops
before its answer (cancelled, or no family allowed) goes straight to postprocess. The tools join
the agent with F-07.
"""

import asyncio
import uuid
from collections.abc import Coroutine
from typing import Any, Literal
from uuid import UUID

import structlog
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from app.contracts.common import ErrorCode
from app.contracts.llm import LlmCallCtx, ModelFamily
from app.contracts.stream import (
    RunQueuedEvent,
    RunRoutedEvent,
    RunWarningEvent,
    StepStartedEvent,
    TextDeltaEvent,
    TextResetEvent,
)
from app.core import time
from app.core.errors import GatewayError
from app.domains.agent import budget, repo, routing, tools
from app.domains.agent.classify import (
    CONFIDENT,
    FALLBACK,
    FUNCTION,
    FUNCTION_NAME,
    classify_rules,
    lexicon,
    profile_of,
)
from app.domains.agent.context import load_context, prompt
from app.domains.agent.postprocess import postprocess, run_error
from app.domains.agent.state import AgentState, RunContext

log = structlog.get_logger(__name__)


class _CallStarted(AsyncCallbackHandler):
    """Metering calls the model inside a slot of the gate (§3.3), so the start of the call is
    the moment the run holds its slot: run.started the first time, step.started for each step of
    the agent (the classifier is no step)."""

    raise_error = True

    def __init__(self, ctx: RunContext, step: int | None) -> None:
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
        if self.told:  # metering retries the same call
            return
        self.told = True
        if not self._ctx.started:
            await self._ctx.start()
        if self._step is not None:
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


def _stopped() -> dict[str, Any]:
    return {"status": "cancelled", "final_text": ""}


async def _free(ctx: RunContext) -> frozenset[ModelFamily]:
    """The families the budget allows now (§9.5)."""
    pacing = budget.Pacing.of(ctx.settings)
    spend = await ctx.usage.service_period(pacing.period_start)
    return budget.allowed(pacing, spend, time.msk_day())


async def classify(state: AgentState, runtime: Runtime[RunContext]) -> dict[str, Any]:
    """The profile of the question (§9.1, §9.3): the rules, and Lite when they are not sure.
    A failed or unreadable answer of Lite leaves the guess of the rules."""
    ctx = runtime.context
    if ctx.cancelled.is_set():
        return _stopped()
    async with ctx.uow as session:
        known = lexicon(await repo.instrument_names(session))
    rules = classify_rules(state["question"], known)
    if rules is not None and rules.confidence >= CONFIDENT:
        return {"profile": rules}
    family = routing.SERVICE["classify"]
    if family not in await _free(ctx):
        return {"profile": rules or FALLBACK}

    def on_queue(position: int) -> None:
        ctx.emit(RunQueuedEvent, position=position)

    model_id = ctx.settings.LLM_MODELS[family]
    model = (
        ctx.llm.chat_model(model_id, streaming=False)
        .bind_tools([FUNCTION], tool_choice=FUNCTION_NAME)
        .with_config(callbacks=[_CallStarted(ctx, None)])
    )
    call = LlmCallCtx(
        purpose="classify",
        priority="interactive",
        family=family,
        model_id=model_id,
        user_id=ctx.ticket.user_id,
        run_id=ctx.ticket.run_id,
        # Its own session: the prompt of the classifier would push the thread out of the cache.
        session_id=str(uuid.uuid5(ctx.ticket.thread_id, "classify")),
    )
    messages = [SystemMessage(prompt("classify")), HumanMessage(_asked(state))]
    work = ctx.metering.invoke(model, messages, ctx=call, on_queue=on_queue)
    try:
        async with asyncio.timeout_at(ctx.deadline):
            answer = await until_cancelled(work, ctx.cancelled)
    except (TimeoutError, GatewayError) as failure:
        log.warning("agent_classify_failed", error=type(failure).__name__)
        return {"profile": rules or FALLBACK}
    if answer is None:
        return _stopped()
    found = next(
        (profile_of(c["args"]) for c in answer.tool_calls if c["name"] == FUNCTION_NAME), None
    )
    if found is None:
        log.warning("agent_classify_unreadable")
    return {"profile": found or rules or FALLBACK, **_usage(state, answer)}


def _asked(state: AgentState) -> str:
    """The question for the classifier; a short follow-up needs the question before it."""
    if state["previous"]:
        lines = [f"Предыдущий вопрос: {state['previous']}", f"Вопрос: {state['question']}"]
        return "\n".join(lines)
    return state["question"]


async def route(state: AgentState, runtime: Runtime[RunContext]) -> dict[str, Any]:
    """The family, the tools and the limits of the run (§9.4, §9.5): run.routed, and
    run.warning when another family answers instead of the requested one."""
    ctx = runtime.context
    if ctx.cancelled.is_set():
        return _stopped()
    profile = state["profile"] or FALLBACK
    routed = routing.decide(
        profile,
        mode=state["mode"],
        broker_ready=state["broker_ready"],
        free=await _free(ctx),
        available=tools.available(),
        models=ctx.settings.LLM_MODELS,
        no_tools=ctx.settings.LLM_TOOLS_UNSUPPORTED,
    )
    async with ctx.uow as session:
        decided = routed.decision if routed else None
        await repo.route_run(session, ctx.ticket.run_id, profile, decided)
    if routed is None:
        log.warning("agent_run_no_family", intent=profile.intent)
        return _failed("llm_quota_exhausted", ctx, "", state["step"])
    decision = routed.decision
    ctx.emit(
        RunRoutedEvent,
        intent=decision.intent,
        family=decision.family,
        model_id=decision.model_id,
        reason=decision.reason,
    )
    warnings = list(state["warnings"])
    if routed.warning is not None:
        ctx.emit(RunWarningEvent, code=routed.warning.code, message=routed.warning.message)
        warnings.append(routed.warning)
    log.info("agent_run_routed", intent=decision.intent, family=decision.family)
    return {"routing": decision, "warnings": warnings}


async def agent(state: AgentState, runtime: Runtime[RunContext]) -> dict[str, Any]:
    """One call of the model, its text streamed to the client as it comes (§7)."""
    ctx = runtime.context
    if ctx.cancelled.is_set():
        return _stopped()
    decision = state["routing"]
    if decision is None:
        raise RuntimeError("route gives every run it lets on a decision")
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
    model = ctx.llm.chat_model(decision.model_id, streaming=True).with_config(callbacks=[started])
    call = LlmCallCtx(
        purpose="agent_step",
        priority="interactive",
        family=decision.family,
        model_id=decision.model_id,
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


def _onward(state: AgentState) -> Literal["on", "end"]:
    """A run cancelled or failed before its answer skips the nodes left."""
    return "on" if state["status"] == "running" else "end"


def _graph() -> Any:
    graph = StateGraph(AgentState, context_schema=RunContext)
    graph.add_node("load_context", load_context)
    graph.add_node("classify", classify)
    graph.add_node("route", route)
    graph.add_node("agent", agent)
    graph.add_node("postprocess", postprocess)
    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "classify")
    graph.add_conditional_edges("classify", _onward, {"on": "route", "end": "postprocess"})
    graph.add_conditional_edges("route", _onward, {"on": "agent", "end": "postprocess"})
    graph.add_edge("agent", "postprocess")
    graph.add_edge("postprocess", END)
    return graph.compile()


GRAPH = _graph()
