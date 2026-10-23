"""The routing table of tech.md §9.4 row by row and its corrections: model_mode, needs, the broker,
the tools in the code, the families without tools and the budget of §9.5.

The expected groups and tools are copied from the text of §9.4, not from the code."""

from collections.abc import Collection

import pytest

from app.contracts.agent import Intent, TaskProfile
from app.contracts.api.settings import ModelMode
from app.contracts.common import ToolName
from app.contracts.llm import ModelFamily
from app.domains.agent.routing import SERVICE, Routed, decide

GROUPS: dict[str, list[ToolName]] = {
    "portfolio": [
        "portfolio_overview",
        "portfolio_positions",
        "operations_summary",
        "portfolio_risk",
    ],
    "market": ["instrument_lookup", "instrument_profile", "price_history", "compare_instruments"],
    "disclosures": ["issuer_reports", "financials"],
    "docs": ["docs_search"],
    "web": ["web_search", "web_extract", "web_crawl"],
    "calc": ["calc"],
    "render": ["make_chart", "make_table"],
}
EVERY_TOOL = frozenset(tool for tools in GROUPS.values() for tool in tools)
ALL: frozenset[ModelFamily] = frozenset({"lite", "pro", "max", "ultra"})
MODELS: dict[ModelFamily, str] = {
    "lite": "GigaChat-2",
    "pro": "GigaChat-2-Pro",
    "max": "GigaChat-2-Max",
    "ultra": "GigaChat-3-Ultra",
}
TICKERS = ["SBER", "GAZP", "LKOH", "YDEX", "VTBR"]


def profile(
    intent: Intent,
    complexity: str = "low",
    instruments: int = 0,
    needs: Collection[str] = (),
) -> TaskProfile:
    return TaskProfile.model_validate(
        {
            "intent": intent,
            "complexity": complexity,
            "needs": list(needs),
            "output": "text",
            "instruments": TICKERS[:instruments],
            "confidence": 0.9,
            "source": "rules",
        }
    )


def route(
    asked: TaskProfile,
    *,
    mode: ModelMode = "auto",
    broker_ready: bool = True,
    free: Collection[ModelFamily] = ALL,
    available: Collection[ToolName] = EVERY_TOOL,
    no_tools: Collection[ModelFamily] = frozenset(),
) -> Routed:
    routed = decide(
        asked,
        mode=mode,
        broker_ready=broker_ready,
        free=free,
        available=available,
        models=MODELS,
        no_tools=no_tools,
    )
    assert routed is not None
    return routed


def tools_of(*groups: str) -> list[ToolName]:
    return [tool for group in groups for tool in GROUPS[group]]


@pytest.mark.parametrize(
    ("intent", "complexity", "instruments", "family", "groups", "max_steps", "synth"),
    [
        ("smalltalk", "low", 0, "lite", [], 1, None),
        ("help", "medium", 0, "lite", [], 1, None),
        ("portfolio_status", "low", 0, "lite", ["portfolio", "render"], 5, None),
        ("portfolio_status", "high", 0, "pro", ["portfolio", "render"], 5, None),
        (
            "portfolio_analysis",
            "medium",
            0,
            "pro",
            ["portfolio", "market", "calc", "render"],
            8,
            None,
        ),
        (
            "portfolio_analysis",
            "high",
            0,
            "max",
            ["portfolio", "market", "calc", "render"],
            8,
            None,
        ),
        ("instrument_quote", "high", 1, "lite", ["market", "render"], 5, None),
        (
            "instrument_analysis",
            "medium",
            1,
            "pro",
            ["market", "disclosures", "docs", "web", "calc", "render"],
            10,
            None,
        ),
        (
            "instrument_analysis",
            "high",
            1,
            "max",
            ["market", "disclosures", "docs", "web", "calc", "render"],
            10,
            None,
        ),
        ("compare", "medium", 3, "pro", ["market", "disclosures", "calc", "render"], 10, None),
        ("compare", "medium", 4, "max", ["market", "disclosures", "calc", "render"], 10, None),
        ("compare", "high", 2, "max", ["market", "disclosures", "calc", "render"], 10, None),
        ("financials", "low", 1, "max", ["disclosures", "docs", "calc", "render"], 10, None),
        ("news", "high", 1, "pro", ["web", "market"], 6, None),
        (
            "research",
            "high",
            1,
            "ultra",
            ["portfolio", "market", "disclosures", "docs", "web", "calc", "render"],
            14,
            "ultra",
        ),
        ("other", "low", 0, "lite", ["portfolio", "market", "web"], 5, None),
    ],
)
def test_each_row_of_the_table_gives_its_family_tools_and_limits(
    intent: Intent,
    complexity: str,
    instruments: int,
    family: ModelFamily,
    groups: list[str],
    max_steps: int,
    synth: ModelFamily | None,
) -> None:
    routed = route(profile(intent, complexity, instruments))

    decision = routed.decision
    assert decision.intent == intent
    assert (decision.requested_family, decision.family) == (family, family)
    assert decision.model_id == MODELS[family]
    assert decision.tools == tools_of(*groups)
    assert decision.max_steps == max_steps
    assert (decision.synthesize, decision.synth_family) == (synth is not None, synth)
    assert decision.reason
    assert routed.warning is None


def test_the_service_calls_take_their_families() -> None:
    assert SERVICE == {
        "classify": "lite",
        "title": "lite",
        "summarize": "lite",
        "ifrs_extract": "max",
    }


def test_a_model_mode_replaces_the_family_of_the_table() -> None:
    routed = route(profile("portfolio_status"), mode="ultra")

    assert (routed.decision.requested_family, routed.decision.family) == ("ultra", "ultra")
    assert routed.decision.model_id == "GigaChat-3-Ultra"
    assert routed.warning is None


def test_a_need_outside_the_row_adds_its_group() -> None:
    routed = route(profile("portfolio_status", needs=["web", "portfolio"]))

    assert routed.decision.tools == tools_of("portfolio", "render", "web")


def test_without_a_broker_the_portfolio_group_drops_out() -> None:
    routed = route(profile("portfolio_analysis", needs=["portfolio"]), broker_ready=False)

    assert routed.decision.tools == tools_of("market", "calc", "render")


def test_only_the_tools_of_the_code_stay_in_the_list() -> None:
    routed = route(profile("portfolio_status"), available={"make_table", "portfolio_overview"})

    assert routed.decision.tools == ["portfolio_overview", "make_table"]


def test_a_refused_family_gives_way_along_its_chain_with_a_warning() -> None:
    routed = route(profile("portfolio_analysis"), free={"lite", "max"})

    decision = routed.decision
    assert (decision.requested_family, decision.family) == ("pro", "max")
    assert decision.model_id == "GigaChat-2-Max"
    assert routed.warning is not None and routed.warning.code == "model_downgraded"
    assert "Pro" in routed.warning.message and "Max" in routed.warning.message
    assert "Max" in decision.reason


def test_a_refused_family_of_the_settings_gives_way_too() -> None:
    routed = route(profile("smalltalk"), mode="max", free={"ultra", "lite"})

    assert (routed.decision.requested_family, routed.decision.family) == ("max", "ultra")
    assert routed.warning is not None and routed.warning.code == "model_downgraded"


@pytest.mark.parametrize(("intent", "free"), [("smalltalk", {"max", "ultra"}), ("news", set())])
def test_no_allowed_family_of_the_chain_routes_nowhere(
    intent: Intent, free: set[ModelFamily]
) -> None:
    routed = decide(
        profile(intent),
        mode="auto",
        broker_ready=True,
        free=free,
        available=EVERY_TOOL,
        models=MODELS,
    )

    assert routed is None


def test_a_family_without_tools_answers_only_questions_without_tools() -> None:
    with_tools = route(profile("portfolio_status"), no_tools={"lite"})
    without = route(profile("smalltalk"), no_tools={"lite"})

    assert with_tools.decision.family == "pro"
    assert with_tools.warning is not None and with_tools.warning.code == "model_downgraded"
    assert without.decision.family == "lite"
    assert without.warning is None


def test_no_tool_in_the_code_leaves_every_family_usable() -> None:
    routed = route(profile("portfolio_status"), available=set(), no_tools={"lite"})

    assert routed.decision.tools == []
    assert routed.decision.family == "lite"
