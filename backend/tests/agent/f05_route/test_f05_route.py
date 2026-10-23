"""Scenario f05_route (F-05 AC 2, 3, 6, 7; tech.md §9.1, §9.4, §9.5, §7): the run classifies the
question, routes it by the table and the budget, and its events, answer, run row and usage rows
tell which family answered. Answers come from seed/llm/f05_route.yaml."""

# ruff: noqa: RUF001  (Russian test data)

from collections.abc import Callable, Iterator
from typing import Any, get_args

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import insert, select

from app.contracts.common import ToolName
from app.contracts.faults import FaultPlan, FaultRule
from app.contracts.llm import ModelFamily
from app.contracts.stream import RunFinishedEvent, RunRoutedEvent, RunWarningEvent
from app.core import time
from app.db.schema.agent import AgentRun, LlmCall, UsageDaily
from app.db.schema.users import UserSettings
from app.gateways.factory import Gateways, override_gateways
from app.gateways.llm.fake import FakeLlm
from app.gateways.llm.metering import Metering
from tests.support.chat import ask, settle, thread_of, user_id_of
from tests.support.sse import sse_collect

FALL = "Почему мой портфель упал за неделю?"  # the rules: portfolio_analysis, pro
MARKET = "Расскажи, как там дела на рынке"  # the rules know nothing: Lite says news, pro
GREETING = "Привет!"  # the rules: smalltalk, lite
MINE = "Что у меня в портфеле?"  # the rules: portfolio_status, lite
PORTFOLIO_TOOLS = {
    "portfolio_overview",
    "portfolio_positions",
    "operations_summary",
    "portfolio_risk",
}

type Faults = Callable[..., FaultPlan]


async def rows(app: FastAPI, model: Any, *where: Any) -> list[Any]:
    query = select(model).where(*where)
    if hasattr(model, "id"):  # journals in the order they were written
        query = query.order_by(model.id)
    return list((await app.state.engine.execute(query)).all())


async def exhaust(app: FastAPI, *families: ModelFamily) -> None:
    """The service spent the whole quota of the families: the reserve refuses them any day."""
    quotas = app.state.settings.LLM_QUOTAS
    for family in families:
        row = insert(UsageDaily).values(
            day=time.msk_day(), user_id=None, resource=f"llm:{family}", amount=quotas[family]
        )
        await app.state.engine.execute(row)


def fake_llm(app: FastAPI) -> FakeLlm:
    gateways: Gateways = app.state.gateways
    assert isinstance(gateways.llm, FakeLlm)
    return gateways.llm


@pytest.fixture
def no_backoff(app: FastAPI) -> Iterator[None]:
    """Metering retries 5xx without the pauses between tries."""
    gateways: Gateways = app.state.gateways
    metering = Metering(gateways.gate, lambda: app.state.engine, app.state.settings, backoff_s=0)
    with override_gateways(app.state, metering=metering):
        yield


@pytest.fixture
def every_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    """The registry as if every slice were merged, so the route shows the groups it keeps."""
    names = frozenset(get_args(ToolName.__value__))
    monkeypatch.setattr("app.domains.agent.tools.available", lambda: names)


# AC 3


async def test_a_family_over_its_quota_gives_way_with_a_warning(
    app: FastAPI, demo_api: httpx.AsyncClient
) -> None:
    await exhaust(app, "pro")

    accepted = await ask(demo_api, FALL)
    await settle(app)
    events = await sse_collect(demo_api, accepted.run_id)
    answer = (await thread_of(demo_api, accepted.thread_id)).messages[-1]

    assert [e.type for e in events[:4]] == [
        "run.routed",
        "run.warning",
        "run.started",
        "step.started",
    ]
    routed, warning = events[0], events[1]
    assert isinstance(routed, RunRoutedEvent) and isinstance(warning, RunWarningEvent)
    # §9.5: pro gives way along pro -> max -> lite.
    assert (routed.intent, routed.family, routed.model_id) == (
        "portfolio_analysis",
        "max",
        "GigaChat-2-Max",
    )
    assert "Max вместо Pro" in routed.reason
    assert warning.code == "model_downgraded"
    assert (answer.status, answer.meta.model_family, answer.meta.model_id) == (
        "complete",
        "max",
        "GigaChat-2-Max",
    )
    assert [w.code for w in answer.meta.warnings] == ["model_downgraded"]
    assert answer.meta.routing_reason == routed.reason
    [run] = await rows(app, AgentRun, AgentRun.id == accepted.run_id)
    assert (run.model_family, run.model_id) == ("max", "GigaChat-2-Max")
    assert (run.routing["requested_family"], run.routing["family"]) == ("pro", "max")
    assert (run.profile["intent"], run.profile["source"]) == ("portfolio_analysis", "rules")
    calls = await rows(app, LlmCall, LlmCall.run_id == accepted.run_id)
    assert [(c.purpose, c.family) for c in calls] == [("agent_step", "max")]


# AC 1 (the rest goes to Lite) and AC 6


async def test_lite_classifies_a_question_the_rules_do_not_know(
    app: FastAPI, user_api: httpx.AsyncClient
) -> None:
    user = await user_id_of(user_api)

    accepted = await ask(user_api, MARKET)
    await settle(app)
    events = await sse_collect(user_api, accepted.run_id)
    answer = (await thread_of(user_api, accepted.thread_id)).messages[-1]

    # The classifier holds the first slot of the run, the route comes after it.
    assert [e.type for e in events[:3]] == ["run.started", "run.routed", "step.started"]
    routed = events[1]
    assert isinstance(routed, RunRoutedEvent)
    assert (routed.intent, routed.family) == ("news", "pro")
    calls = await rows(app, LlmCall, LlmCall.run_id == accepted.run_id)
    assert [(c.purpose, c.family, c.priority) for c in calls] == [
        ("classify", "lite", "interactive"),
        ("agent_step", "pro", "interactive"),
    ]
    [run] = await rows(app, AgentRun, AgentRun.id == accepted.run_id)
    assert (run.profile["intent"], run.profile["source"]) == ("news", "llm")
    # usage of f05_route.yaml: the classifier 300 + 40 tokens, the answer 700 + 60.
    usage = {(u.user_id, u.resource): u.amount for u in await rows(app, UsageDaily)}
    assert usage == {
        (user, "llm:lite"): 340,
        (None, "llm:lite"): 340,
        (user, "llm:pro"): 760,
        (None, "llm:pro"): 760,
    }
    assert answer.meta.tokens_billable == 1100


async def test_a_failing_classifier_leaves_the_question_to_the_rules(
    app: FastAPI, user_api: httpx.AsyncClient, faults: Faults, no_backoff: None
) -> None:
    # Every try of the call fails: metering gives up after its 3 retries (§3.3).
    faults(FaultRule(method="chat_model", mode="error", times=4, match={"purpose": "classify"}))

    accepted = await ask(user_api, MARKET)
    await settle(app)
    events = await sse_collect(user_api, accepted.run_id)
    answer = (await thread_of(user_api, accepted.thread_id)).messages[-1]

    routed = next(e for e in events if isinstance(e, RunRoutedEvent))
    assert (routed.intent, routed.family) == ("other", "lite")
    assert answer.status == "complete" and answer.content
    calls = await rows(app, LlmCall, LlmCall.run_id == accepted.run_id)
    assert [(c.purpose, c.status) for c in calls] == [("classify", "error"), ("agent_step", "ok")]


# §9.1 route: no family of the chain


async def test_no_allowed_family_of_the_chain_fails_the_run(
    app: FastAPI, user_api: httpx.AsyncClient
) -> None:
    # max and ultra let the question in, but the chain of lite is lite -> pro.
    await exhaust(app, "lite", "pro")

    accepted = await ask(user_api, GREETING)
    await settle(app)
    events = await sse_collect(user_api, accepted.run_id)
    answer = (await thread_of(user_api, accepted.thread_id)).messages[-1]

    assert [e.type for e in events] == ["run.finished"]
    finished = events[-1]
    assert isinstance(finished, RunFinishedEvent) and finished.error is not None
    assert (finished.status, finished.error.code) == ("failed", "llm_quota_exhausted")
    assert answer.status == "failed"
    [run] = await rows(app, AgentRun, AgentRun.id == accepted.run_id)
    assert (run.status, run.error_code, run.routing) == ("failed", "llm_quota_exhausted", None)
    assert run.profile["intent"] == "smalltalk"
    assert await rows(app, LlmCall, LlmCall.run_id == accepted.run_id) == []


# AC 2


async def test_the_model_of_the_settings_answers_and_the_classifier_stays_on_lite(
    app: FastAPI, user_api: httpx.AsyncClient
) -> None:
    user = await user_id_of(user_api)
    await app.state.engine.execute(insert(UserSettings).values(user_id=user, model_mode="ultra"))

    accepted = await ask(user_api, MARKET)
    await settle(app)
    events = await sse_collect(user_api, accepted.run_id)

    routed = next(e for e in events if isinstance(e, RunRoutedEvent))
    assert (routed.family, routed.model_id) == ("ultra", "GigaChat-3-Ultra")
    assert "модель из настроек" in routed.reason
    calls = await rows(app, LlmCall, LlmCall.run_id == accepted.run_id)
    assert [(c.purpose, c.family) for c in calls] == [("classify", "lite"), ("agent_step", "ultra")]


# AC 7


async def test_without_a_broker_the_portfolio_tools_drop_out_and_the_model_offers_the_token(
    app: FastAPI, user_api: httpx.AsyncClient, every_tool: None
) -> None:
    accepted = await ask(user_api, MINE)
    await settle(app)

    [run] = await rows(app, AgentRun, AgentRun.id == accepted.run_id)
    assert run.routing["intent"] == "portfolio_status"
    assert run.routing["tools"] == ["make_chart", "make_table"]
    [step] = [c for c in fake_llm(app).calls if c.args.get("purpose") == "agent_step"]
    read = str(step.args["user_message"])
    assert "брокер не подключён" in read
    assert "предложи подключить токен в Настройках" in read


async def test_with_a_broker_the_portfolio_tools_stay(
    app: FastAPI, demo_api: httpx.AsyncClient, every_tool: None
) -> None:
    accepted = await ask(demo_api, FALL)
    await settle(app)

    [run] = await rows(app, AgentRun, AgentRun.id == accepted.run_id)
    assert set(run.routing["tools"]) >= PORTFOLIO_TOOLS
