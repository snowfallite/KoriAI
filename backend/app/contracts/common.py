"""Shared contract types and enumerations (tech.md §6.1, §6.7, §12)."""

import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    JsonValue,
    PlainSerializer,
    StringConstraints,
    WithJsonSchema,
)


class Contract(BaseModel):
    """Base of every contract model (tech.md §16.1)."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        allow_inf_nan=False,
        # A response carries every field, so the output schema marks fields with defaults required.
        json_schema_serialization_defaults_required=True,
    )


DECIMAL_PATTERN = r"^-?\d+(\.\d+)?$"
_DECIMAL = re.compile(r"-?[0-9]+(?:\.[0-9]+)?")


def _decimal(value: object) -> object:
    if isinstance(value, str):
        if _DECIMAL.fullmatch(value) is None:
            raise ValueError("expected a decimal string like -12.34")
        return Decimal(value)
    # Money and prices never pass through float (tech.md §5).
    if isinstance(value, float | bool):
        raise ValueError("expected a decimal string or Decimal")
    return value


def _plain(value: Decimal) -> str:
    return format(value, "f")  # never an exponent: Decimal('1E+3') -> '1000'


# Decimal in code, a string on the wire.
type DecimalStr = Annotated[
    Decimal,
    BeforeValidator(_decimal),
    PlainSerializer(_plain, return_type=str, when_used="json"),
    WithJsonSchema({"type": "string", "pattern": DECIMAL_PATTERN}),
]

# ISO 4217 in upper case: T-Invest 'rub' becomes 'RUB'.
Currency = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]

Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


def _utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


# ISO 8601 in UTC with Z on the wire (tech.md §6.1).
UtcDatetime = Annotated[AwareDatetime, AfterValidator(_utc)]


class Money(Contract):
    amount: DecimalStr
    currency: Currency


class Page[T](Contract):
    items: list[T]
    next_cursor: str | None


type ErrorCode = Literal[
    "unauthorized",
    "invalid_credentials",
    "forbidden",
    "registration_closed",
    "not_found",
    "conflict",
    "run_active",
    "email_taken",
    "broker_not_connected",
    "gone",
    "validation_error",
    "invite_required",
    "invite_invalid",
    "token_invalid",
    "token_not_read_only",
    "rate_limited",
    "user_budget_exhausted",
    "llm_busy",
    "llm_quota_exhausted",
    "tinvest_unavailable",
    "tinvest_rate_limited",
    "web_unavailable",
    "web_credits_exhausted",
    "disclosure_unavailable",
    "internal",
]


class ErrorOut(Contract):
    code: ErrorCode
    message: str
    details: dict[str, JsonValue] | None = None
    request_id: str


type WarningCode = Literal[
    "model_downgraded",
    "budget_low",
    "web_credits_low",
    "tool_failed",
    "steps_limit",
    "ungrounded_numbers",
    "partial_answer",
    "unknown_placeholder",
    "broker_not_connected",
]

type RunStatus = Literal[
    "queued", "running", "done", "partial", "cancelled", "failed", "interrupted"
]
type MessageRole = Literal["user", "assistant"]
type MessageStatus = Literal["complete", "partial", "failed"]

type ToolName = Literal[
    "portfolio_overview",
    "portfolio_positions",
    "operations_summary",
    "portfolio_risk",
    "instrument_lookup",
    "instrument_profile",
    "price_history",
    "compare_instruments",
    "issuer_reports",
    "financials",
    "docs_search",
    "web_search",
    "web_extract",
    "web_crawl",
    "make_chart",
    "make_table",
    "calc",
]

type InstrumentType = Literal[
    "share", "bond", "etf", "currency", "future", "option", "structured", "index", "other"
]
type AccountType = Literal["broker", "iis", "invest_box", "invest_fund", "other"]
type AccountStatus = Literal["new", "open", "closed", "other"]
# Only read_only reaches the database (tech.md AD-10).
type AccessLevel = Literal["read_only", "full_access", "no_access", "unspecified"]
type OperationKind = Literal[
    "buy",
    "sell",
    "dividend",
    "coupon",
    "amortization",
    "commission",
    "tax",
    "input",
    "output",
    "other",
]
type CandleInterval = Literal["day", "week", "month"]
type PeriodCode = Literal["1m", "3m", "6m", "ytd", "1y", "3y", "5y", "max"]

type DocKind = Literal[
    "ifrs_annual",
    "ifrs_interim",
    "ras_annual",
    "ras_interim",
    "annual_report",
    "issuer_report",
    "presentation",
    "press_release",
    "other",
]
type Standard = Literal["ifrs", "ras", "none"]
type FileSection = Literal[
    "charter",
    "annual",
    "ras",
    "ifrs",
    "issuer_reports",
    "affiliates",
    "emission",
    "investors",
    "other",
    "meetings",
]

# Financial metrics (tech.md §12.3); expenses keep the minus sign of the report.
type MetricCode = Literal[
    "revenue",
    "cost_of_sales",
    "gross_profit",
    "operating_profit",
    "interest_income",
    "interest_expense",
    "profit_before_tax",
    "income_tax",
    "net_income",
    "net_income_parent",
    "ebitda",
    "total_assets",
    "non_current_assets",
    "current_assets",
    "cash",
    "total_equity",
    "non_current_liabilities",
    "long_term_debt",
    "current_liabilities",
    "short_term_debt",
    "lease_liabilities",
    "net_debt",
    "cfo",
    "cfi",
    "cff",
    "capex",
    "fcf",
    "dividends_paid",
]
