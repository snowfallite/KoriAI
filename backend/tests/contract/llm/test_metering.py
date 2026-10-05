"""Metering of model calls (S1-09; tech.md §3.3, §5.5, §8.3): a row of llm_calls per call, usage
of the day for the user and the service, 429 and 5xx retried inside the slot, X-Session-ID."""

# ruff: noqa: RUF001  (Russian test data)

import asyncio
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from gigachat.context import session_id_cvar
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from sqlalchemy import insert, select

from app.contracts.faults import FaultPlan, FaultRule
from app.contracts.llm import LlmCallCtx
from app.core import time
from app.core.errors import TransientGatewayError
from app.db.schema.agent import LlmCall, UsageDaily
from app.db.schema.users import User
from app.gateways.llm.fake import FakeLlm, ScriptedChatModel
from app.gateways.llm.gate import InProcessPriorityGate
from app.gateways.llm.metering import Metering

FIXTURES = Path(__file__).parents[2] / "fixtures" / "llm"
GREETING = [HumanMessage("Привет!")]
# usage of the greeting in seed/llm/smalltalk.yaml: 420 + 24 tokens
PROMPT, COMPLETION = 420, 24

type Faults = Callable[..., FaultPlan]


async def new_user(app: FastAPI) -> UUID:
    row = insert(User).values(email=f"{uuid.uuid4().hex}@example.test", password_hash="x")
    user_id: UUID = (await app.state.engine.execute(row.returning(User.id))).scalar_one()
    return user_id


def ctx(user_id: UUID | None = None, **changes: Any) -> LlmCallCtx:
    fields: dict[str, Any] = {
        "purpose": "agent_step",
        "priority": "interactive",
        "family": "lite",
        "model_id": "GigaChat-2",
        "user_id": user_id,
        "session_id": "thread-1",
    }
    return LlmCallCtx(**fields | changes)


def metering(app: FastAPI, gate: InProcessPriorityGate | None = None) -> Metering:
    gate = gate or InProcessPriorityGate(capacity=1, timeout_s=5)
    return Metering(gate, lambda: app.state.engine, app.state.settings, backoff_s=0)


def fake_llm(app: FastAPI) -> FakeLlm:
    llm = app.state.gateways.llm
    assert isinstance(llm, FakeLlm)
    return llm


async def calls(app: FastAPI) -> list[Any]:
    found = await app.state.engine.execute(select(LlmCall))
    return list(found.all())


async def usage(app: FastAPI) -> set[tuple[Any, ...]]:
    found = await app.state.engine.execute(
        select(
            UsageDaily.day,
            UsageDaily.user_id,
            UsageDaily.resource,
            UsageDaily.amount,
            UsageDaily.calls,
        )
    )
    return {tuple(row) for row in found.all()}


async def test_a_call_writes_its_row_and_the_usage_of_the_day(app: FastAPI) -> None:
    user_id = await new_user(app)
    model = fake_llm(app).chat_model("GigaChat-2", streaming=False)

    answer = await metering(app).invoke(model, GREETING, ctx=ctx(user_id))

    [row] = await calls(app)
    assert answer.text.startswith("Здравствуйте")
    assert (row.purpose, row.priority, row.family, row.model_id, row.user_id) == (
        "agent_step",
        "interactive",
        "lite",
        "GigaChat-2",
        user_id,
    )
    assert (row.prompt_tokens, row.completion_tokens, row.precached_tokens) == (
        PROMPT,
        COMPLETION,
        0,
    )
    assert (row.billable_tokens, row.status, row.error_code) == (PROMPT + COMPLETION, "ok", None)
    today = time.msk_day()
    assert await usage(app) == {
        (today, user_id, "llm:lite", PROMPT + COMPLETION, 1),
        (today, None, "llm:lite", PROMPT + COMPLETION, 1),
    }


async def test_a_call_of_a_job_counts_for_the_service_only(app: FastAPI) -> None:
    model = fake_llm(app).chat_model("GigaChat-2", streaming=False)

    await metering(app).invoke(model, GREETING, ctx=ctx(priority="background", job_id=7))

    [row] = await calls(app)
    assert (row.job_id, row.priority) == (7, "background")
    assert await usage(app) == {(time.msk_day(), None, "llm:lite", PROMPT + COMPLETION, 1)}


async def test_the_session_id_goes_to_the_api_for_the_call_only(app: FastAPI) -> None:
    llm = fake_llm(app)

    await metering(app).invoke(llm.chat_model("GigaChat-2", streaming=False), GREETING, ctx=ctx())

    assert llm.calls[-1].args["session_id"] == "thread-1"  # X-Session-ID of the SDK (§9.6)
    assert session_id_cvar.get() is None


async def test_a_429_is_retried_inside_the_slot(app: FastAPI, faults: Faults) -> None:
    faults(FaultRule(method="chat_model", mode="rate_limit", times=2))
    llm = fake_llm(app)

    answer = await metering(app).invoke(
        llm.chat_model("GigaChat-2", streaming=False), GREETING, ctx=ctx()
    )

    assert answer.text.startswith("Здравствуйте")
    assert [call.method for call in llm.calls] == ["chat_model"] * 3
    [row] = await calls(app)
    assert (row.status, row.billable_tokens) == ("ok", PROMPT + COMPLETION)


async def test_a_fourth_429_gives_up_with_llm_busy(app: FastAPI, faults: Faults) -> None:
    faults(FaultRule(method="chat_model", mode="rate_limit", times=4))
    model = fake_llm(app).chat_model("GigaChat-2", streaming=False)

    with pytest.raises(TransientGatewayError) as busy:
        await metering(app).invoke(model, GREETING, ctx=ctx())

    assert busy.value.code == "llm_busy"
    [row] = await calls(app)
    assert (row.status, row.error_code, row.billable_tokens) == ("rate_limited", "llm_busy", 0)
    assert await usage(app) == set()  # nothing answered, nothing spent


@pytest.mark.parametrize(
    ("mode", "times", "status"),
    [("error", 3, "ok"), ("timeout", 1, "ok"), ("error", 4, "error"), ("timeout", 4, "timeout")],
)
async def test_5xx_and_timeouts_get_three_more_tries(
    app: FastAPI, faults: Faults, mode: str, times: int, status: str
) -> None:
    faults(FaultRule(method="chat_model", mode=mode, times=times))
    model = fake_llm(app).chat_model("GigaChat-2", streaming=False)

    try:
        await metering(app).invoke(model, GREETING, ctx=ctx())
    except TransientGatewayError as error:
        assert error.code == "llm_busy"

    [row] = await calls(app)
    assert row.status == status


async def test_a_busy_gate_ends_in_llm_busy_and_still_leaves_a_row(app: FastAPI) -> None:
    gate = InProcessPriorityGate(capacity=1, timeout_s=0.05)
    model = fake_llm(app).chat_model("GigaChat-2", streaming=False)

    async with gate.slot("interactive", "run:other"):
        with pytest.raises(TransientGatewayError) as busy:
            await metering(app, gate).invoke(model, GREETING, ctx=ctx())

    assert busy.value.code == "llm_busy"
    [row] = await calls(app)
    assert (row.status, row.error_code) == ("error", "llm_busy")
    assert row.wait_ms >= 40


async def test_queue_places_reach_the_caller(app: FastAPI) -> None:
    gate = InProcessPriorityGate(capacity=1, timeout_s=5)
    model = fake_llm(app).chat_model("GigaChat-2", streaming=False)
    places: list[int] = []

    async with gate.slot("interactive", "run:other"):
        call = asyncio.create_task(
            metering(app, gate).invoke(model, GREETING, ctx=ctx(), on_queue=places.append)
        )
        await asyncio.sleep(0.01)
    await asyncio.wait_for(call, 2)

    assert places == [1]


async def test_a_cancelled_call_is_recorded_as_cancelled(app: FastAPI, faults: Faults) -> None:
    faults(FaultRule(method="chat_model", mode="latency", latency_ms=5000))
    model = fake_llm(app).chat_model("GigaChat-2", streaming=False)

    call = asyncio.create_task(metering(app).invoke(model, GREETING, ctx=ctx()))
    await asyncio.sleep(0.05)
    call.cancel()
    with pytest.raises(asyncio.CancelledError):
        await call

    [row] = await calls(app)
    assert row.status == "cancelled"


async def test_a_stream_resets_its_preamble_before_a_function_call(app: FastAPI) -> None:
    model = ScriptedChatModel.from_file(FIXTURES / "stream.yaml")
    deltas: list[str] = []
    resets: list[int] = []

    first = await metering(app).stream(
        model,
        [HumanMessage("Что у меня в портфеле?")],
        ctx=ctx(),
        on_delta=deltas.append,
        on_reset=lambda: resets.append(len(deltas)),
    )
    history = [
        HumanMessage("Что у меня в портфеле?"),
        first,
        ToolMessage("Портфель: 7 позиций", tool_call_id=first.tool_calls[0]["id"] or ""),
    ]
    second = await metering(app).stream(
        model, history, ctx=ctx(), on_delta=deltas.append, on_reset=lambda: None
    )

    assert "".join(deltas[: resets[0]]) == "Сейчас посмотрю портфель."
    assert [call["name"] for call in first.tool_calls] == ["portfolio_overview"]
    assert isinstance(second, AIMessage)
    assert second.text == "Портфель стоит 1 065 082,71 ₽."
    assert "".join(deltas[resets[0] :]) == second.text
    rows = await calls(app)
    assert [(r.prompt_tokens, r.precached_tokens, r.billable_tokens) for r in rows] == [
        (900, 300, 1020),
        (900, 300, 1020),
    ]
