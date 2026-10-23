"""The routing table of tech.md §9.4 [FROZEN] with its corrections: the family, the tools and
the limits of a question by its profile, then the budget of §9.5 picks the family that answers.

The table changes only in the contract mode (§4.2, §19.3).
"""

from collections.abc import Collection, Mapping
from dataclasses import dataclass

from app.contracts.agent import Intent, RoutingDecision, TaskProfile, ToolGroup
from app.contracts.api.chat import WarningOut
from app.contracts.api.settings import ModelMode
from app.contracts.common import ToolName
from app.contracts.llm import LlmPurpose, ModelFamily
from app.domains.agent import budget


@dataclass(frozen=True, slots=True)
class Row:
    family: ModelFamily
    groups: tuple[ToolGroup, ...]
    max_steps: int
    high: ModelFamily | None = None  # the family of a question of high complexity
    many: int | None = None  # more instruments than this take the family of high too
    synth_family: ModelFamily | None = None  # set: the answer goes through synthesize


GROUP_ORDER: tuple[ToolGroup, ...] = (
    "portfolio",
    "market",
    "disclosures",
    "docs",
    "web",
    "calc",
    "render",
)
TABLE: Mapping[Intent, Row] = {
    "smalltalk": Row("lite", (), 1),
    "help": Row("lite", (), 1),
    "portfolio_status": Row("lite", ("portfolio", "render"), 5, high="pro"),
    "portfolio_analysis": Row("pro", ("portfolio", "market", "calc", "render"), 8, high="max"),
    "instrument_quote": Row("lite", ("market", "render"), 5),
    "instrument_analysis": Row(
        "pro", ("market", "disclosures", "docs", "web", "calc", "render"), 10, high="max"
    ),
    "compare": Row("pro", ("market", "disclosures", "calc", "render"), 10, high="max", many=3),
    "financials": Row("max", ("disclosures", "docs", "calc", "render"), 10),
    "news": Row("pro", ("web", "market"), 6),
    "research": Row("ultra", GROUP_ORDER, 14, synth_family="ultra"),
    "other": Row("lite", ("portfolio", "market", "web"), 5),
}
GROUPS: Mapping[ToolGroup, tuple[ToolName, ...]] = {
    "portfolio": (
        "portfolio_overview",
        "portfolio_positions",
        "operations_summary",
        "portfolio_risk",
    ),
    "market": ("instrument_lookup", "instrument_profile", "price_history", "compare_instruments"),
    "disclosures": ("issuer_reports", "financials"),
    "docs": ("docs_search",),
    "web": ("web_search", "web_extract", "web_crawl"),
    "calc": ("calc",),
    "render": ("make_chart", "make_table"),
}
# The service calls of the models; model_mode leaves them as they are.
SERVICE: Mapping[LlmPurpose, ModelFamily] = {
    "classify": "lite",
    "title": "lite",
    "summarize": "lite",
    "ifrs_extract": "max",
}

NAMES: Mapping[ModelFamily, str] = {"lite": "Lite", "pro": "Pro", "max": "Max", "ultra": "Ultra"}
TOPICS: Mapping[Intent, str] = {
    "smalltalk": "разговор",
    "help": "вопрос про сервис",
    "portfolio_status": "состав портфеля",
    "portfolio_analysis": "анализ портфеля",
    "instrument_quote": "цена инструмента",
    "instrument_analysis": "анализ инструмента",
    "compare": "сравнение инструментов",
    "financials": "отчётность",
    "news": "новости",
    "research": "исследование",
    "other": "общий вопрос",
}


@dataclass(frozen=True, slots=True)
class Routed:
    decision: RoutingDecision
    warning: WarningOut | None  # model_downgraded: another family answers the question


def requested_family(profile: TaskProfile) -> ModelFamily:
    """The family of the table for the profile, before model_mode and the budget."""
    row = TABLE[profile.intent]
    many = row.many is not None and len(profile.instruments) > row.many
    if row.high is not None and (profile.complexity == "high" or many):
        return row.high
    return row.family


def tools_for(
    profile: TaskProfile, broker_ready: bool, available: Collection[ToolName]
) -> list[ToolName]:
    """The groups of the row and of the needs, without portfolio when the broker gives no data,
    and only the tools the code has: a tool of a slice not merged yet drops out silently."""
    groups = list(TABLE[profile.intent].groups)
    groups += [group for group in GROUP_ORDER if group in profile.needs and group not in groups]
    if not broker_ready:
        groups = [group for group in groups if group != "portfolio"]
    return [tool for group in groups for tool in GROUPS[group] if tool in available]


def decide(
    profile: TaskProfile,
    *,
    mode: ModelMode,
    broker_ready: bool,
    free: Collection[ModelFamily],
    available: Collection[ToolName],
    models: Mapping[ModelFamily, str],
    no_tools: Collection[ModelFamily] = frozenset(),
) -> Routed | None:
    """The route of a question; None when no family of its chain is allowed (§9.5).

    `free` holds the families the budget allows, `no_tools` the families that call no functions
    (LLM_TOOLS_UNSUPPORTED): they take only questions without tools.
    """
    row = TABLE[profile.intent]
    requested = requested_family(profile) if mode == "auto" else mode
    tools = tools_for(profile, broker_ready, available)
    usable = {family for family in free if not (tools and family in no_tools)}
    family = budget.substitute(requested, usable)
    if family is None:
        return None
    synth = None
    if row.synth_family is not None:
        synth = budget.substitute(row.synth_family, usable) or family
    decision = RoutingDecision(
        intent=profile.intent,
        requested_family=requested,
        family=family,
        model_id=models[family],
        tools=tools,
        max_steps=row.max_steps,
        synthesize=synth is not None,
        synth_family=synth,
        reason=_reason(profile, mode, requested, family),
    )
    return Routed(decision, _warning(requested, family, tools, no_tools))


def _reason(
    profile: TaskProfile, mode: ModelMode, requested: ModelFamily, family: ModelFamily
) -> str:
    topic = [TOPICS[profile.intent]]
    if mode != "auto":
        topic.append("модель из настроек")
    elif requested != TABLE[profile.intent].family:
        topic.append("сложный вопрос")
    reason = f"{', '.join(topic)}: {NAMES[family]}"
    return reason if family == requested else f"{reason} вместо {NAMES[requested]}"


def _warning(
    requested: ModelFamily,
    family: ModelFamily,
    tools: Collection[ToolName],
    no_tools: Collection[ModelFamily],
) -> WarningOut | None:
    if family == requested:
        return None
    if tools and requested in no_tools:
        why = f"Модель {NAMES[requested]} не вызывает инструменты"
    else:
        why = f"Квота модели {NAMES[requested]} на пределе"
    return WarningOut(code="model_downgraded", message=f"{why}, отвечает {NAMES[family]}")
