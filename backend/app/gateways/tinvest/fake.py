"""T-Invest fake (tech.md §8.1, §8.2): answers from backend/fixtures/seed/tinvest."""

import functools
from collections.abc import Callable, Hashable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from pydantic import AwareDatetime, Field, InstanceOf, SecretStr, TypeAdapter

from app.contracts.common import CandleInterval, InstrumentType, Money
from app.contracts.tinvest import (
    TAccount,
    TCandle,
    TCoupon,
    TDividend,
    TForecasts,
    TFundamentals,
    TInstrument,
    TInstrumentBrief,
    TInstrumentListKind,
    TOperation,
    TOperationsPage,
    TOperationsQuery,
    TPortfolio,
    TPrice,
    TReportEvent,
)
from app.core.errors import PermanentGatewayError
from app.gateways.fakes import Fake, port_method
from app.gateways.fixtures import SEED, load, read_csv

ROOT = SEED / "tinvest"
LISTS: dict[TInstrumentListKind, InstrumentType] = {
    "shares": "share",
    "bonds": "bond",
    "etfs": "etf",
    "currencies": "currency",
    "indicatives": "index",
}
BRIEF = set(TInstrumentBrief.model_fields)
Token = InstanceOf[SecretStr]


@dataclass(frozen=True)
class Seed:
    accounts: list[TAccount]
    portfolios: dict[str, TPortfolio]
    operations: dict[str, list[TOperation]]  # newest first, as the API pages them
    instruments: dict[UUID, TInstrument]
    candles: dict[UUID, list[TCandle]]
    fundamentals: dict[UUID, TFundamentals]
    forecasts: dict[UUID, TForecasts]
    dividends: dict[UUID, list[TDividend]]
    coupons: dict[UUID, list[TCoupon]]
    reports: list[TReportEvent]


@functools.cache
def seed() -> Seed:
    """The files of seed/tinvest, read once per process."""
    instruments = load(ROOT / "instruments.yaml", TypeAdapter(list[TInstrument]))
    uid = {i.ticker: i.uid for i in instruments}

    def by_ticker[T](name: str, adapter: TypeAdapter[dict[str, T]]) -> dict[UUID, T]:
        return {uid[ticker]: value for ticker, value in load(ROOT / name, adapter).items()}

    def by_account[T](folder: str, adapter: TypeAdapter[T]) -> dict[str, T]:
        return {path.stem: load(path, adapter) for path in sorted((ROOT / folder).glob("*.yaml"))}

    candles = TypeAdapter(list[TCandle])
    operations = by_account("operations", TypeAdapter(list[TOperation]))
    return Seed(
        accounts=load(ROOT / "accounts.yaml", TypeAdapter(list[TAccount])),
        portfolios=by_account("portfolios", TypeAdapter(TPortfolio)),
        operations={
            k: sorted(v, key=lambda o: o.date, reverse=True) for k, v in operations.items()
        },
        instruments={i.uid: i for i in instruments},
        candles={
            uid[path.stem]: candles.validate_python(read_csv(path))
            for path in sorted((ROOT / "candles").glob("*.csv"))
        },
        fundamentals={
            f.asset_uid: f
            for f in load(ROOT / "fundamentals.yaml", TypeAdapter(list[TFundamentals]))
        },
        forecasts=by_ticker("forecasts.yaml", TypeAdapter(dict[str, TForecasts])),
        dividends=by_ticker("dividends.yaml", TypeAdapter(dict[str, list[TDividend]])),
        coupons=by_ticker("coupons.yaml", TypeAdapter(dict[str, list[TCoupon]])),
        reports=load(ROOT / "report_schedule.yaml", TypeAdapter(list[TReportEvent])),
    )


def _nothing(arguments: dict[str, Any]) -> list[Any]:
    return []


def _empty_portfolio(arguments: dict[str, Any]) -> TPortfolio:
    zero = Money(amount=Decimal(0), currency="RUB")
    return TPortfolio(
        account_id=arguments["account_id"],
        total=zero,
        total_by_type={},
        expected_yield=None,
        expected_yield_pct=None,
        positions=[],
    )


def _bucket(interval: CandleInterval) -> Callable[[TCandle], Hashable]:
    if interval == "week":
        return lambda candle: candle.time.isocalendar()[:2]
    if interval == "month":
        return lambda candle: (candle.time.year, candle.time.month)
    return lambda candle: candle.time.date()


def _merge(candles: list[TCandle]) -> TCandle:
    return TCandle(
        time=candles[0].time,
        open=candles[0].open,
        high=max(c.high for c in candles),
        low=min(c.low for c in candles),
        close=candles[-1].close,
        volume=sum(c.volume for c in candles),
        is_complete=all(c.is_complete for c in candles),
    )


class FakeTInvest(Fake):
    port = "tinvest"
    unavailable = "tinvest_unavailable"
    rate_limited = "tinvest_rate_limited"

    def __init__(self, **options: Any) -> None:
        super().__init__(**options)
        self.seed = seed()

    @port_method(empty=_nothing)
    async def get_accounts(self, token: Token) -> list[TAccount]:
        return list(self.seed.accounts)

    @port_method(empty=_empty_portfolio)
    async def get_portfolio(self, token: Token, account_id: str) -> TPortfolio:
        if account_id not in self.seed.portfolios:
            raise PermanentGatewayError("not_found")
        return self.seed.portfolios[account_id]

    @port_method(empty=lambda arguments: TOperationsPage(items=[], next_cursor=None))
    async def get_operations(
        self, token: Token, q: InstanceOf[TOperationsQuery]
    ) -> TOperationsPage:
        if q.account_id not in self.seed.operations:
            raise PermanentGatewayError("not_found")
        found = [
            op
            for op in self.seed.operations[q.account_id]
            if q.from_ <= op.date < q.to and (q.kinds is None or op.kind in q.kinds)
        ]
        if q.cursor is not None and not q.cursor.isdigit():
            raise PermanentGatewayError("validation_error")
        start = int(q.cursor or 0)
        end = start + q.limit
        return TOperationsPage(
            items=found[start:end], next_cursor=str(end) if end < len(found) else None
        )

    @port_method(empty=_nothing)
    async def find_instruments(
        self, token: Token, query: str, limit: Annotated[int, Field(ge=1)] = 20
    ) -> list[TInstrumentBrief]:
        needle = query.strip().casefold()
        found = [
            i
            for i in self.seed.instruments.values()
            if needle
            and any(
                needle in (text or "").casefold() for text in (i.ticker, i.name, i.isin, i.figi)
            )
        ]
        # An exact ticker first, then tickers that start with the query, then names.
        found.sort(
            key=lambda i: (
                i.ticker.casefold() != needle,
                not i.ticker.casefold().startswith(needle),
                i.name,
            )
        )
        return [TInstrumentBrief(**i.model_dump(include=BRIEF)) for i in found[:limit]]

    @port_method()
    async def get_instrument(self, token: Token, uid: UUID) -> TInstrument:
        if uid not in self.seed.instruments:
            raise PermanentGatewayError("not_found")
        return self.seed.instruments[uid]

    @port_method(empty=_nothing)
    async def list_instruments(self, token: Token, kind: TInstrumentListKind) -> list[TInstrument]:
        return [i for i in self.seed.instruments.values() if i.instrument_type == LISTS[kind]]

    @port_method(empty=_nothing)
    async def get_fundamentals(self, token: Token, asset_uids: list[UUID]) -> list[TFundamentals]:
        return [self.seed.fundamentals[a] for a in asset_uids if a in self.seed.fundamentals]

    @port_method(empty=_nothing)
    async def get_report_schedule(
        self, token: Token, instrument_uid: UUID, from_: date, to: date
    ) -> list[TReportEvent]:
        return [
            event
            for event in self.seed.reports
            if event.instrument_uid == instrument_uid and from_ <= event.report_date <= to
        ]

    @port_method(empty=lambda arguments: TForecasts(consensus=None, targets=[]))
    async def get_forecasts(self, token: Token, instrument_uid: UUID) -> TForecasts:
        return self.seed.forecasts.get(instrument_uid, TForecasts(consensus=None, targets=[]))

    @port_method(empty=_nothing)
    async def get_dividends(
        self, token: Token, instrument_uid: UUID, from_: date, to: date
    ) -> list[TDividend]:
        rows = self.seed.dividends.get(instrument_uid, [])
        return [d for d in rows if from_ <= d.record_date <= to]

    @port_method(empty=_nothing)
    async def get_coupons(
        self, token: Token, instrument_uid: UUID, from_: date, to: date
    ) -> list[TCoupon]:
        return [
            c for c in self.seed.coupons.get(instrument_uid, []) if from_ <= c.coupon_date <= to
        ]

    @port_method(empty=_nothing)
    async def get_candles(
        self,
        token: Token,
        instrument_uid: UUID,
        from_: AwareDatetime,
        to: AwareDatetime,
        interval: CandleInterval,
    ) -> list[TCandle]:
        days = [c for c in self.seed.candles.get(instrument_uid, []) if from_ <= c.time < to]
        groups: dict[Hashable, list[TCandle]] = {}
        for candle in days:
            groups.setdefault(_bucket(interval)(candle), []).append(candle)
        return [_merge(group) for group in groups.values()]

    @port_method(empty=_nothing)
    async def get_last_prices(self, token: Token, instrument_uids: list[UUID]) -> list[TPrice]:
        return [
            TPrice(instrument_uid=uid, price=candles[-1].close, time=candles[-1].time)
            for uid in instrument_uids
            if (candles := self.seed.candles.get(uid))
        ]
