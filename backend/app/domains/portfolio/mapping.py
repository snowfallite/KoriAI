"""Account portfolios of T-Invest as the portfolio of the API (tech.md §6.4): pure functions.

A position is worth its quantity times the price plus the accrued interest of one unit, in the
price currency; value_rub converts that at the ruble rate of the currency. Weights, the yield of a
position and the yield of an account come as shares, like the weights: 0.0252 is 2.52 %.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, localcontext
from uuid import UUID

from app.contracts.api.instruments import InstrumentBrief
from app.contracts.api.portfolio import (
    AccountSummaryOut,
    AllocationSliceOut,
    PortfolioOut,
    PositionOut,
)
from app.contracts.common import InstrumentType, Money
from app.contracts.tinvest import TPortfolio, TPosition
from app.domains.analytics.portfolio import NANO, PRECISION, allocation, fx_convert, weights

RUB = "RUB"
SHARE = Decimal("1e-12")  # weights and yields on the wire: finer than any screen shows
TYPE_LABELS: dict[InstrumentType, str] = {
    "share": "Акции",
    "bond": "Облигации",
    "etf": "Фонды",
    "currency": "Валюта",
    "future": "Фьючерсы",
    "option": "Опционы",
    "structured": "Структурные продукты",
    "index": "Индексы",
    "other": "Прочее",
}


@dataclass(frozen=True, slots=True)
class Holdings:
    """The portfolio of one account as T-Invest gives it."""

    alias: str
    name: str
    portfolio: TPortfolio


@dataclass(frozen=True, slots=True)
class _Valued:
    alias: str
    position: TPosition
    instrument: InstrumentBrief
    value: Money  # in the price currency
    value_rub: Decimal
    yield_rub: Decimal | None


def price_currency(position: TPosition, instrument: InstrumentBrief | None) -> str:
    price = position.current_price or position.average_price
    if price is not None:
        return price.currency
    return instrument.currency if instrument is not None else RUB


def foreign_currencies(
    holdings: Sequence[Holdings], instruments: Mapping[UUID, InstrumentBrief]
) -> set[str]:
    """The currencies of values and yields that need a ruble rate."""
    found = set()
    for held in holdings:
        for position in held.portfolio.positions:
            found.add(price_currency(position, instruments.get(position.instrument_uid)))
            if position.expected_yield is not None:
                found.add(position.expected_yield.currency)
    return found - {RUB}


def portfolio_out(
    holdings: Sequence[Holdings],
    instruments: Mapping[UUID, InstrumentBrief],
    rates: Mapping[str, Decimal],
    as_of: datetime,
) -> PortfolioOut:
    """`rates` gives rubles per unit of every currency foreign_currencies names."""
    valued = sorted(
        (
            _value(held.alias, p, instruments, rates)
            for held in holdings
            for p in held.portfolio.positions
        ),
        key=lambda v: (-v.value_rub, v.alias, v.instrument.ticker, str(v.instrument.uid)),
    )
    shares = weights([v.value_rub for v in valued])
    by_type = allocation(
        valued, key=lambda v: v.instrument.instrument_type, value=lambda v: v.value_rub
    )
    slices = sorted(by_type.items(), key=lambda item: (-item[1], item[0]))
    total = sum((v.value_rub for v in valued), Decimal(0))
    return PortfolioOut(
        as_of=as_of,
        currency=RUB,
        total=_rub(total),
        accounts=[_account(held, valued) for held in holdings],
        allocation=[
            AllocationSliceOut(key=key, label=TYPE_LABELS[key], value=_rub(value), weight=_share(w))
            for (key, value), w in zip(slices, weights([v for _, v in slices]), strict=True)
        ],
        positions=[_position(v, w) for v, w in zip(valued, shares, strict=True)],
    )


def _value(
    alias: str,
    position: TPosition,
    instruments: Mapping[UUID, InstrumentBrief],
    rates: Mapping[str, Decimal],
) -> _Valued:
    known = instruments.get(position.instrument_uid)
    currency = price_currency(position, known)
    unit = position.current_price.amount if position.current_price is not None else Decimal(0)
    accrued = position.accrued_interest
    # Accrued interest comes in the currency of the bond, the one of its price.
    if accrued is not None and accrued.currency == currency:
        unit += accrued.amount
    value = _times(position.quantity, unit)
    earned = position.expected_yield
    return _Valued(
        alias=alias,
        position=position,
        instrument=known or _unknown(position, currency),
        value=Money(amount=value, currency=currency),
        value_rub=fx_convert(value, _rate(rates, currency)),
        yield_rub=None
        if earned is None
        else fx_convert(earned.amount, _rate(rates, earned.currency)),
    )


def _position(valued: _Valued, weight: Decimal) -> PositionOut:
    p = valued.position
    return PositionOut(
        instrument=valued.instrument,
        account_alias=valued.alias,
        quantity=_plain(p.quantity),
        avg_price=p.average_price,
        current_price=p.current_price,
        value=Money(amount=_plain(valued.value.amount), currency=valued.value.currency),
        value_rub=_rub(valued.value_rub),
        weight=_share(weight),
        yield_abs=p.expected_yield,
        yield_pct=_yield_share(p),
        accrued_interest=p.accrued_interest,
    )


def _account(held: Holdings, valued: Sequence[_Valued]) -> AccountSummaryOut:
    own = [v for v in valued if v.alias == held.alias]
    earned = [v.yield_rub for v in own if v.yield_rub is not None]
    percent = held.portfolio.expected_yield_pct  # T-Invest gives percents
    return AccountSummaryOut(
        alias=held.alias,
        name=held.name,
        total=_rub(sum((v.value_rub for v in own), Decimal(0))),
        expected_yield=_rub(sum(earned, Decimal(0))) if earned else None,
        expected_yield_pct=None if percent is None else _plain(percent.scaleb(-2)),
    )


def _yield_share(position: TPosition) -> Decimal | None:
    """The yield of a position over what it cost, when both are in one currency."""
    earned, average = position.expected_yield, position.average_price
    if earned is None or average is None or earned.currency != average.currency:
        return None
    cost = abs(_times(position.quantity, average.amount))
    if not cost:
        return None
    with localcontext() as context:
        context.prec = PRECISION  # a tiny cost may give a share far above one
        return _share(earned.amount / cost)


def _unknown(position: TPosition, currency: str) -> InstrumentBrief:
    """An instrument T-Invest no longer describes: the position still counts."""
    return InstrumentBrief(
        uid=position.instrument_uid,
        ticker=position.figi or "—",
        class_code="",
        name=position.figi or "Неизвестный инструмент",
        instrument_type=position.instrument_type,
        currency=currency,
        logo_url=None,
        brand_color=None,
    )


def _rate(rates: Mapping[str, Decimal], currency: str) -> Decimal:
    return Decimal(1) if currency == RUB else rates[currency]


def _times(a: Decimal, b: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = PRECISION
        return (a * b).quantize(NANO)


def _plain(value: Decimal) -> Decimal:
    """No trailing zeros and no minus zero on the wire."""
    return value.normalize() if value else Decimal(0)


def _share(value: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = PRECISION
        return _plain(value.quantize(SHARE))


def _rub(amount: Decimal) -> Money:
    return Money(amount=_plain(amount), currency=RUB)
