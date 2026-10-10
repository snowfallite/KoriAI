"""T-Invest behind TInvestPort (tech.md §8.2): read-only services of the SDK over gRPC.

The SDK services run on our own channel: AsyncClient of the SDK would start T-Bank's Sentry for
the whole process (owner's decision, S1-09). Target and app name stay as §8.2 gives them; the
trading and sandbox services are never called.
"""

import asyncio
import functools
import hashlib
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from uuid import UUID

from pydantic import SecretStr
from t_tech.invest import schemas as sdk
from t_tech.invest.async_services import AsyncServices
from t_tech.invest.channels import create_channel
from t_tech.invest.constants import INVEST_GRPC_API
from t_tech.invest.exceptions import AioRequestError

from app.config import Settings
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
from app.core.cache import TtlCache
from app.core.errors import PermanentGatewayError, TransientGatewayError
from app.gateways.retry import with_retries
from app.gateways.tinvest import mapping

HOUR = 3600.0
FUNDAMENTALS_BATCH = 100  # assets per GetAssetFundamentals


def _start(day: date) -> datetime:
    return datetime.combine(day, time(), UTC)


def _end(day: date) -> datetime:
    return datetime.combine(day + timedelta(days=1), time(), UTC)


def _token_key(token: SecretStr) -> str:
    # The cache keeps a digest: the token itself stays out of long-lived memory.
    return hashlib.sha256(token.get_secret_value().encode()).hexdigest()


class RealTInvest:
    def __init__(self, settings: Settings) -> None:
        self._app_name = settings.TINVEST_APP_NAME
        self._timeout_s = settings.TINVEST_TIMEOUT_S
        self._channel: Any = None
        # TTLs of §8.2; instruments and market data are the same for every token.
        self._instruments: TtlCache[TInstrument] = TtlCache(24 * HOUR)
        self._lists: TtlCache[list[TInstrument]] = TtlCache(24 * HOUR)
        self._fundamentals: TtlCache[TFundamentals] = TtlCache(12 * HOUR)
        self._forecasts: TtlCache[TForecasts] = TtlCache(6 * HOUR)
        self._dividends: TtlCache[list[TDividend]] = TtlCache(12 * HOUR)
        self._coupons: TtlCache[list[TCoupon]] = TtlCache(12 * HOUR)
        self._portfolios: TtlCache[TPortfolio] = TtlCache(30)
        self._prices: TtlCache[TPrice] = TtlCache(30)

    async def aclose(self) -> None:
        if self._channel is not None:
            await self._channel.close()
            self._channel = None

    def _services(self, token: SecretStr) -> AsyncServices:
        if self._channel is None:
            self._channel = create_channel(target=INVEST_GRPC_API, force_async=True)
        return AsyncServices(self._channel, token=token.get_secret_value(), app_name=self._app_name)

    async def _read[T](self, call: Callable[[], Awaitable[T]]) -> T:
        """One read with the timeout of the config and the retries of §8.1."""

        async def attempt() -> T:
            try:
                async with asyncio.timeout(self._timeout_s):
                    return await call()
            except AioRequestError as exc:
                raise mapping.error(exc) from exc
            except TimeoutError as exc:
                raise TransientGatewayError("tinvest_unavailable") from exc

        return await with_retries(attempt)

    async def get_accounts(self, token: SecretStr) -> list[TAccount]:
        users = self._services(token).users
        answer = await self._read(users.get_accounts)
        return [mapping.account(item) for item in answer.accounts]

    async def get_portfolio(self, token: SecretStr, account_id: str) -> TPortfolio:
        operations = self._services(token).operations

        async def load() -> TPortfolio:
            answer = await self._read(lambda: operations.get_portfolio(account_id=account_id))
            return mapping.portfolio(answer)

        return await self._portfolios.get_or_load((_token_key(token), account_id), load)

    async def get_operations(self, token: SecretStr, q: TOperationsQuery) -> TOperationsPage:
        operations = self._services(token).operations
        kinds = set(q.kinds or [])
        # The API has no filter for "other": then every type comes and the page gets filtered.
        server_side = kinds and "other" not in kinds
        types = [t for kind in kinds for t in mapping.OPERATION_TYPES[kind]] if server_side else []
        request = sdk.GetOperationsByCursorRequest(
            account_id=q.account_id,
            from_=q.from_,
            to=q.to,
            cursor=q.cursor or "",
            limit=q.limit,
            operation_types=types,
            state=sdk.OperationState.OPERATION_STATE_EXECUTED,
        )
        page = mapping.operations_page(
            await self._read(lambda: operations.get_operations_by_cursor(request))
        )
        if kinds:
            page = page.model_copy(update={"items": [i for i in page.items if i.kind in kinds]})
        return page

    async def find_instruments(
        self, token: SecretStr, query: str, limit: int = 20
    ) -> list[TInstrumentBrief]:
        instruments = self._services(token).instruments
        answer = await self._read(lambda: instruments.find_instrument(query=query))
        # The API order is no ranking: SBER on TQBR was not among the first ten hits of "SBER"
        # (smoke of 2026-10-08). Rank before the limit, as the fake does.
        hits = sorted(answer.instruments, key=lambda hit: mapping.search_rank(query, hit))
        # FindInstrument gives no currency: the full instruments do, and their cache is warm.
        found = await asyncio.gather(
            *(self.get_instrument(token, UUID(i.uid)) for i in hits[:limit] if i.uid),
            return_exceptions=True,
        )
        briefs = []
        for item in found:
            if isinstance(item, PermanentGatewayError) and item.code == "not_found":
                continue  # a hit the instrument service does not know: not worth a failed search
            if isinstance(item, BaseException):
                raise item
            briefs.append(mapping.brief(item))
        return briefs

    async def get_instrument(self, token: SecretStr, uid: UUID) -> TInstrument:
        instruments = self._services(token).instruments

        async def load() -> TInstrument:
            answer = await self._read(
                lambda: instruments.get_instrument_by(
                    id_type=sdk.InstrumentIdType.INSTRUMENT_ID_TYPE_UID, id=str(uid)
                )
            )
            return mapping.instrument(answer.instrument)

        return await self._instruments.get_or_load(uid, load)

    async def list_instruments(
        self, token: SecretStr, kind: TInstrumentListKind
    ) -> list[TInstrument]:
        instruments = self._services(token).instruments

        async def load() -> list[TInstrument]:
            if kind == "indicatives":
                found = await self._read(lambda: instruments.indicatives(sdk.IndicativesRequest()))
                return [mapping.indicative(i) for i in found.instruments]
            calls = {
                "shares": instruments.shares,
                "bonds": instruments.bonds,
                "etfs": instruments.etfs,
                "currencies": instruments.currencies,
            }
            answer = await self._read(calls[kind])
            return [mapping.instrument(i) for i in answer.instruments]

        return await self._lists.get_or_load(kind, load)

    async def get_fundamentals(
        self, token: SecretStr, asset_uids: list[UUID]
    ) -> list[TFundamentals]:
        instruments = self._services(token).instruments
        missing = [uid for uid in dict.fromkeys(asset_uids) if self._fundamentals.get(uid) is None]
        for start in range(0, len(missing), FUNDAMENTALS_BATCH):
            batch = [str(uid) for uid in missing[start : start + FUNDAMENTALS_BATCH]]
            request = sdk.GetAssetFundamentalsRequest(assets=batch)
            answer = await self._read(
                functools.partial(instruments.get_asset_fundamentals, request)
            )
            for item in answer.fundamentals:
                found = mapping.fundamentals(item)
                self._fundamentals.put(found.asset_uid, found)
        return [f for uid in asset_uids if (f := self._fundamentals.get(uid)) is not None]

    async def get_report_schedule(
        self, token: SecretStr, instrument_uid: UUID, from_: date, to: date
    ) -> list[TReportEvent]:
        instruments = self._services(token).instruments
        request = sdk.GetAssetReportsRequest(
            instrument_id=str(instrument_uid), from_=_start(from_), to=_end(to)
        )
        answer = await self._read(lambda: instruments.get_asset_reports(request))
        events = (mapping.report_event(instrument_uid, e) for e in answer.events)
        return [e for e in events if e is not None]

    async def get_forecasts(self, token: SecretStr, instrument_uid: UUID) -> TForecasts:
        instruments = self._services(token).instruments
        request = sdk.GetForecastRequest(instrument_id=str(instrument_uid))

        async def load() -> TForecasts:
            try:
                return mapping.forecasts(
                    await self._read(lambda: instruments.get_forecast_by(request))
                )
            except PermanentGatewayError as error:
                if error.code != "not_found":
                    raise
                return TForecasts(consensus=None, targets=[])  # no analyst covers it

        return await self._forecasts.get_or_load(instrument_uid, load)

    async def get_dividends(
        self, token: SecretStr, instrument_uid: UUID, from_: date, to: date
    ) -> list[TDividend]:
        instruments = self._services(token).instruments

        async def load() -> list[TDividend]:
            answer = await self._read(
                lambda: instruments.get_dividends(
                    instrument_id=str(instrument_uid), from_=_start(from_), to=_end(to)
                )
            )
            found = (mapping.dividend(d) for d in answer.dividends)
            return [d for d in found if d is not None]

        return await self._dividends.get_or_load((instrument_uid, from_, to), load)

    async def get_coupons(
        self, token: SecretStr, instrument_uid: UUID, from_: date, to: date
    ) -> list[TCoupon]:
        instruments = self._services(token).instruments

        async def load() -> list[TCoupon]:
            answer = await self._read(
                lambda: instruments.get_bond_coupons(
                    instrument_id=str(instrument_uid), from_=_start(from_), to=_end(to)
                )
            )
            found = (mapping.coupon(c) for c in answer.events)
            return [c for c in found if c is not None]

        return await self._coupons.get_or_load((instrument_uid, from_, to), load)

    async def get_candles(
        self,
        token: SecretStr,
        instrument_uid: UUID,
        from_: datetime,
        to: datetime,
        interval: CandleInterval,
    ) -> list[TCandle]:
        services = self._services(token)

        async def load() -> list[TCandle]:
            # The SDK cuts the range by the limits of the interval (§8.2).
            pages = services.get_all_candles(
                instrument_id=str(instrument_uid),
                from_=from_,
                to=to,
                interval=mapping.INTERVALS[interval],
            )
            return [mapping.candle(c) async for c in pages]

        return await self._read(load)

    async def get_last_prices(self, token: SecretStr, instrument_uids: list[UUID]) -> list[TPrice]:
        market = self._services(token).market_data
        missing = [uid for uid in dict.fromkeys(instrument_uids) if self._prices.get(uid) is None]
        if missing:
            answer = await self._read(
                lambda: market.get_last_prices(instrument_id=[str(uid) for uid in missing])
            )
            for item in answer.last_prices:
                if item.instrument_uid:
                    found = mapping.price(item)
                    self._prices.put(found.instrument_uid, found)
        return [p for uid in instrument_uids if (p := self._prices.get(uid)) is not None]
