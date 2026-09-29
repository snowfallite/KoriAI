"""Agent contracts: task profile, routing, tools (tech.md §9.3, §9.4, §9.7)."""

from decimal import Decimal
from typing import Literal

from pydantic import Field, JsonValue

from app.contracts.api.instruments import InstrumentBrief
from app.contracts.artifacts import ChartKind
from app.contracts.common import (
    Contract,
    DocKind,
    ErrorCode,
    InstrumentType,
    MetricCode,
    OperationKind,
    PeriodCode,
    ToolName,
)
from app.contracts.llm import ModelFamily
from app.contracts.web import TimeRange, WebDepth, WebTopic

type Intent = Literal[
    "smalltalk",
    "help",
    "portfolio_status",
    "portfolio_analysis",
    "instrument_quote",
    "instrument_analysis",
    "compare",
    "financials",
    "news",
    "research",
    "other",
]
type Need = Literal["portfolio", "market", "disclosures", "docs", "web", "calc"]
type ToolGroup = Literal["portfolio", "market", "disclosures", "docs", "web", "calc", "render"]


class TaskProfile(Contract):
    intent: Intent
    complexity: Literal["low", "medium", "high"]
    needs: list[Need]
    output: Literal["text", "table", "chart", "report"]
    instruments: list[str] = Field(default=[], max_length=5)  # mentions as written
    period: PeriodCode | None = None
    confidence: float = Field(ge=0, le=1)
    source: Literal["rules", "llm"]


class RoutingDecision(Contract):
    intent: Intent
    requested_family: ModelFamily  # from the table or model_mode
    family: ModelFamily  # after the budget
    model_id: str
    tools: list[ToolName]
    max_steps: int
    synthesize: bool
    synth_family: ModelFamily | None
    reason: str  # short, in Russian: goes to run.routed and meta


class ToolSpec(Contract):
    name: ToolName
    group: ToolGroup
    title: str  # for the UI, e.g. «Загружаю портфель»
    description: str  # for the LLM, in Russian: what it does and when to call it
    args_model: type[Contract]  # extra='forbid'
    few_shot_examples: list[dict[str, JsonValue]]  # [{request, params}] for GigaChat
    timeout_s: int


class ToolResult(Contract):
    ok: bool
    summary: str = Field(max_length=1500)  # goes to the LLM
    datasets: list[str] = []  # ds1..
    artifacts: list[str] = []  # c1, t1, i1
    sources: list[str] = []  # s1..
    facts: list[Decimal] = []  # numbers the tool asserts (§9.10)
    error_code: ErrorCode | None = None
    candidates: list[InstrumentBrief] = []  # an ambiguous instrument


# Tool arguments (§9.7). A nullable argument defaults to None: the model may leave it out.


class IndicatorSpec(Contract):
    kind: Literal["sma", "ema", "rsi", "macd", "bb"]
    window: int = Field(default=20, ge=2, le=200)


class PortfolioOverviewArgs(Contract):
    account: str | None = None


class PortfolioPositionsArgs(Contract):
    account: str | None = None
    instrument_type: InstrumentType | None = None
    sort_by: Literal["value", "yield", "weight"] = "value"
    limit: int = Field(default=50, ge=1, le=100)


class OperationsSummaryArgs(Contract):
    account: str | None = None
    period: PeriodCode = "1y"
    group_by: Literal["kind", "month", "instrument"] = "kind"
    kinds: list[OperationKind] | None = None


class PortfolioRiskArgs(Contract):
    account: str | None = None
    period: PeriodCode = "1y"


class InstrumentLookupArgs(Contract):
    query: str = Field(min_length=1, max_length=60)


class InstrumentProfileArgs(Contract):
    instrument: str


class PriceHistoryArgs(Contract):
    instrument: str
    period: PeriodCode = "1y"
    interval: Literal["day", "week", "month"] = "day"
    indicators: list[IndicatorSpec] = []


class CompareInstrumentsArgs(Contract):
    instruments: list[str] = Field(min_length=2, max_length=5)
    period: PeriodCode = "1y"
    metrics: list[Literal["return", "volatility", "drawdown", "correlation"]] = ["return"]


class IssuerReportsArgs(Contract):
    issuer: str
    kinds: list[DocKind] | None = None
    years: list[int] | None = None


class FinancialsArgs(Contract):
    issuer: str
    metrics: list[MetricCode] | None = None
    standard: Literal["ifrs", "ras", "auto"] = "auto"
    periods: Literal["annual", "interim", "all"] = "annual"
    years: int = Field(default=5, ge=1, le=10)


class DocsSearchArgs(Contract):
    query: str = Field(min_length=1, max_length=300)
    issuer: str | None = None
    kinds: list[DocKind] | None = None
    years: list[int] | None = None
    top_k: int = Field(default=6, ge=1, le=10)


class WebSearchArgs(Contract):
    query: str = Field(min_length=1, max_length=200)
    topic: WebTopic = "general"
    time_range: TimeRange | None = None
    domains: list[str] | None = None
    depth: WebDepth = "basic"
    images: bool = False


class WebExtractArgs(Contract):
    urls: list[str] = Field(min_length=1, max_length=5)


class WebCrawlArgs(Contract):
    url: str
    instructions: str | None = None
    limit: int = Field(default=5, ge=1, le=10)


class MakeChartArgs(Contract):
    dataset: str
    kind: ChartKind
    x: str
    y: list[str] = Field(min_length=1, max_length=6)
    title: str
    group_by: str | None = None
    y_format: Literal["money", "percent", "number"] | None = None


class MakeTableArgs(Contract):
    dataset: str
    columns: list[str] | None = None
    sort_by: str | None = None
    desc: bool = True
    limit: int = Field(default=20, ge=1, le=50)
    title: str


class CalcArgs(Contract):
    expression: str = Field(min_length=1, max_length=200)
