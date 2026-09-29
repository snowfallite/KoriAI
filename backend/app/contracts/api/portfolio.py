"""Portfolio DTOs (tech.md §6.4)."""

from datetime import date
from typing import Annotated, Literal

from pydantic import StringConstraints

from app.contracts.api.broker import AccountAlias
from app.contracts.api.instruments import InstrumentBrief
from app.contracts.common import (
    Contract,
    Currency,
    DecimalStr,
    InstrumentType,
    Money,
    PeriodCode,
    UtcDatetime,
)


class AccountSummaryOut(Contract):
    alias: AccountAlias
    name: str
    total: Money
    expected_yield: Money | None
    expected_yield_pct: DecimalStr | None


class AllocationSliceOut(Contract):
    key: InstrumentType
    label: str
    value: Money
    weight: DecimalStr  # a share in 0..1; the weights sum to 1


class PositionOut(Contract):
    instrument: InstrumentBrief
    account_alias: AccountAlias
    quantity: DecimalStr
    avg_price: Money | None
    current_price: Money | None
    value: Money  # in the instrument currency
    value_rub: Money  # at the last prices of currency instruments
    weight: DecimalStr  # of value_rub
    yield_abs: Money | None
    yield_pct: DecimalStr | None
    accrued_interest: Money | None


class PortfolioOut(Contract):
    as_of: UtcDatetime
    currency: Literal["RUB"]
    total: Money
    accounts: list[AccountSummaryOut]
    allocation: list[AllocationSliceOut]
    positions: list[PositionOut]


class PortfolioPointOut(Contract):
    day: date
    value: DecimalStr


class PortfolioHistoryOut(Contract):
    currency: Currency
    points: list[PortfolioPointOut]


class IncomeItemOut(Contract):
    date: date
    instrument: InstrumentBrief
    kind: Literal["dividend", "coupon"]
    amount: Money
    status: Literal["paid", "expected"]


class IncomeMonthOut(Contract):
    month: Annotated[str, StringConstraints(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")]  # YYYY-MM
    amount: Money


class PortfolioIncomeOut(Contract):
    items: list[IncomeItemOut]
    by_month: list[IncomeMonthOut]


class PortfolioRiskOut(Contract):
    period: PeriodCode
    volatility_ann: DecimalStr | None
    max_drawdown: DecimalStr | None
    beta: DecimalStr | None
    benchmark: Literal["IMOEX"] | None
    observations: int
