"""T-Invest port (tech.md §8.2): reads only, trading and the sandbox stay out."""

from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from pydantic import SecretStr

from app.contracts.common import CandleInterval
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
    TOperationsPage,
    TOperationsQuery,
    TPortfolio,
    TPrice,
    TReportEvent,
)


class TInvestPort(Protocol):
    async def get_accounts(self, token: SecretStr) -> list[TAccount]: ...
    async def get_portfolio(self, token: SecretStr, account_id: str) -> TPortfolio: ...
    async def get_operations(self, token: SecretStr, q: TOperationsQuery) -> TOperationsPage: ...
    async def find_instruments(
        self, token: SecretStr, query: str, limit: int = 20
    ) -> list[TInstrumentBrief]: ...
    async def get_instrument(self, token: SecretStr, uid: UUID) -> TInstrument: ...
    async def list_instruments(
        self, token: SecretStr, kind: TInstrumentListKind
    ) -> list[TInstrument]: ...
    async def get_fundamentals(
        self, token: SecretStr, asset_uids: list[UUID]
    ) -> list[TFundamentals]: ...
    async def get_report_schedule(
        self, token: SecretStr, instrument_uid: UUID, from_: date, to: date
    ) -> list[TReportEvent]: ...
    async def get_forecasts(self, token: SecretStr, instrument_uid: UUID) -> TForecasts: ...
    async def get_dividends(
        self, token: SecretStr, instrument_uid: UUID, from_: date, to: date
    ) -> list[TDividend]: ...
    async def get_coupons(
        self, token: SecretStr, instrument_uid: UUID, from_: date, to: date
    ) -> list[TCoupon]: ...
    async def get_candles(
        self,
        token: SecretStr,
        instrument_uid: UUID,
        from_: datetime,
        to: datetime,
        interval: CandleInterval,
    ) -> list[TCandle]: ...
    async def get_last_prices(
        self, token: SecretStr, instrument_uids: list[UUID]
    ) -> list[TPrice]: ...
