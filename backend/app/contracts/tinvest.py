"""DTOs of the T-Invest port (tech.md §8.2): sums in Money, numbers in Decimal."""

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.contracts.common import (
    AccessLevel,
    AccountStatus,
    AccountType,
    Contract,
    Currency,
    InstrumentType,
    Money,
    OperationKind,
    UtcDatetime,
)

type TInstrumentListKind = Literal["shares", "bonds", "etfs", "currencies", "indicatives"]
type Recommendation = Literal["buy", "hold", "sell", "unknown"]


class TAccount(Contract):
    id: str
    name: str
    type: AccountType
    status: AccountStatus
    opened_date: date | None
    access_level: AccessLevel


class TPosition(Contract):
    instrument_uid: UUID
    figi: str
    instrument_type: InstrumentType
    quantity: Decimal
    average_price: Money | None
    current_price: Money | None
    expected_yield: Money | None
    accrued_interest: Money | None
    blocked: bool


class TPortfolio(Contract):
    account_id: str
    total: Money
    total_by_type: dict[InstrumentType, Money]
    expected_yield: Money | None
    expected_yield_pct: Decimal | None
    positions: list[TPosition]


class TOperationsQuery(Contract):
    account_id: str
    from_: UtcDatetime
    to: UtcDatetime
    kinds: list[OperationKind] | None
    cursor: str | None
    limit: int = Field(ge=1, le=1000)


class TOperation(Contract):
    id: str
    kind: OperationKind
    date: UtcDatetime
    instrument_uid: UUID | None
    payment: Money
    quantity: Decimal | None
    price: Money | None
    description: str


class TOperationsPage(Contract):
    items: list[TOperation]
    next_cursor: str | None


class TInstrumentBrief(Contract):
    uid: UUID
    figi: str | None
    ticker: str
    class_code: str
    isin: str | None
    name: str
    instrument_type: InstrumentType
    currency: Currency


class TInstrument(TInstrumentBrief):
    lot: int
    asset_uid: UUID | None
    brand_uid: UUID | None
    logo_name: str | None  # '<base>.png'
    brand_color: str | None
    sector: str | None
    country_iso: str | None
    exchange: str | None
    for_qual_only: bool


class TFundamentals(Contract):
    asset_uid: UUID
    currency: Currency
    market_cap: Decimal | None
    pe_ttm: Decimal | None
    pb_ttm: Decimal | None
    ev_ebitda: Decimal | None
    dividend_yield_ttm: Decimal | None
    net_debt_ebitda: Decimal | None
    roe: Decimal | None
    revenue_ttm: Decimal | None
    net_income_ttm: Decimal | None
    ebitda_ttm: Decimal | None
    fcf_ttm: Decimal | None
    total_debt: Decimal | None
    beta: Decimal | None
    high_52w: Decimal | None
    low_52w: Decimal | None


class TReportEvent(Contract):
    instrument_uid: UUID
    report_date: date
    period_year: int
    period_num: int
    period_type: Literal["quarter", "semiannual", "annual", "other"]


class TConsensus(Contract):
    recommendation: Recommendation
    target_avg: Money | None
    target_min: Money | None
    target_max: Money | None
    upside_pct: Decimal | None


class TTarget(Contract):
    company: str
    recommendation: Recommendation
    target: Money
    date: date


class TForecasts(Contract):
    consensus: TConsensus | None
    targets: list[TTarget]


class TDividend(Contract):
    record_date: date
    payment_date: date
    last_buy_date: date
    amount: Money
    yield_pct: Decimal | None


class TCoupon(Contract):
    coupon_date: date
    number: int
    amount: Money | None


class TCandle(Contract):
    time: UtcDatetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    is_complete: bool


class TPrice(Contract):
    instrument_uid: UUID
    price: Decimal
    time: UtcDatetime
