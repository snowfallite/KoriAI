"""Answers of T-Invest as DTOs (S1-09; tech.md §8.2) on recorded answers.

The fixtures are protobuf JSON, the shape the REST gateway of T-Invest answers with; the SDK reads
them the way it reads gRPC answers. Expectations are worked out from the files by hand.
"""

# ruff: noqa: RUF001  (Russian test data)

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from google.protobuf import json_format
from google.protobuf.message import Message
from grpc import StatusCode
from pydantic import SecretStr
from t_tech.invest import schemas as sdk
from t_tech.invest._grpc_helpers import protobuf_to_dataclass
from t_tech.invest.exceptions import AioRequestError
from t_tech.invest.grpc import instruments_pb2, marketdata_pb2, operations_pb2, users_pb2
from t_tech.invest.logging import Metadata

from app.config import Settings
from app.contracts.common import Money
from app.contracts.tinvest import (
    TAccount,
    TCandle,
    TConsensus,
    TCoupon,
    TDividend,
    TInstrument,
    TPosition,
    TPrice,
    TReportEvent,
    TTarget,
)
from app.core.errors import GatewayError, PermanentGatewayError, TransientGatewayError
from app.gateways.tinvest import mapping
from app.gateways.tinvest.real import RealTInvest

FIXTURES = Path(__file__).parents[2] / "fixtures" / "tinvest"
SBER = UUID("e6123145-9665-43e0-8413-cd61b8aa9b13")
RUB = "RUB"


def answer[T](name: str, message: type[Message], schema: type[T]) -> T:
    parsed = json_format.Parse((FIXTURES / f"{name}.json").read_text(encoding="utf-8"), message())
    found: T = protobuf_to_dataclass(parsed, schema)
    return found


def rub(amount: str) -> Money:
    return Money(amount=Decimal(amount), currency=RUB)


def test_accounts() -> None:
    found = answer("GetAccounts", users_pb2.GetAccountsResponse, sdk.GetAccountsResponse)

    assert [mapping.account(a) for a in found.accounts] == [
        TAccount(
            id="2000123456",
            name="Брокерский счёт",
            type="broker",
            status="open",
            opened_date=date(2021, 3, 15),
            access_level="read_only",
        ),
        TAccount(
            id="2000654321",
            name="ИИС",
            type="iis",
            status="open",
            opened_date=date(2023, 1, 20),
            access_level="full_access",
        ),
        TAccount(
            id="2000999999",
            name="Дебетовый",
            type="other",
            status="closed",
            opened_date=None,
            access_level="no_access",
        ),
    ]


def test_portfolio() -> None:
    found = mapping.portfolio(
        answer("GetPortfolio", operations_pb2.PortfolioResponse, sdk.PortfolioResponse)
    )

    assert (found.account_id, found.total) == ("2000123456", rub("601293.31"))
    assert found.total_by_type == {
        "share": rub("120984"),
        "bond": rub("175515"),
        "currency": rub("304794.31"),
    }
    assert (found.expected_yield, found.expected_yield_pct) == (None, Decimal("8.77"))
    assert found.positions == [
        TPosition(
            instrument_uid=SBER,
            figi="BBG004730N88",
            instrument_type="share",
            quantity=Decimal(400),
            average_price=rub("309.96"),
            current_price=rub("302.46"),
            expected_yield=rub("-3000"),
            accrued_interest=None,
            blocked=False,
        ),
        TPosition(
            instrument_uid=UUID("1c2d3e4f-0000-4000-8000-000000000238"),
            figi="TCS00A1038V6",
            instrument_type="bond",
            quantity=Decimal(300),
            average_price=rub("574.89"),
            current_price=rub("561.51"),
            expected_yield=rub("-4014"),
            accrued_interest=rub("23.54"),
            blocked=True,
        ),
        TPosition(
            instrument_uid=UUID("a92e2e25-a698-45cc-a781-167cf465257c"),
            figi="RUB000UTSTOM",
            instrument_type="currency",
            quantity=Decimal("304794.31"),
            average_price=None,
            current_price=None,
            expected_yield=None,
            accrued_interest=None,
            blocked=False,
        ),
    ]


def test_operations() -> None:
    page = mapping.operations_page(
        answer(
            "GetOperationsByCursor",
            operations_pb2.GetOperationsByCursorResponse,
            sdk.GetOperationsByCursorResponse,
        )
    )

    rows = [
        (op.id, op.kind, op.instrument_uid, op.payment, op.quantity, op.price, op.description)
        for op in page.items
    ]
    assert rows == [
        ("op-1", "buy", SBER, rub("-81384"), Decimal(300), rub("271.28"), "Покупка ценных бумаг"),
        ("op-2", "tax", SBER, rub("-1811.68"), None, None, "Удержание налога по дивидендам"),
        ("op-3", "commission", None, rub("-40.69"), None, None, "Удержание комиссии за операцию"),
        ("op-4", "other", None, Money(amount=Decimal("1.5"), currency="USD"), None, None,
         "Плата за перенос позиции"),
    ]  # fmt: skip
    assert page.items[0].date == datetime(2024, 10, 2, 7, 15, tzinfo=UTC)
    assert page.next_cursor == "Q1VSU09SLTM="


def test_instrument_and_its_brief() -> None:
    found = mapping.instrument(
        answer(
            "GetInstrumentBy", instruments_pb2.InstrumentResponse, sdk.InstrumentResponse
        ).instrument
    )

    assert found == TInstrument(
        uid=SBER,
        figi="BBG004730N88",
        ticker="SBER",
        class_code="TQBR",
        isin="RU0009029540",
        name="Сбер Банк",
        instrument_type="share",
        currency=RUB,
        lot=10,
        asset_uid=UUID("40d89385-a03a-4659-bf4e-d3ecba011782"),
        brand_uid=None,
        logo_name="sber.png",
        brand_color="#309c0b",
        sector=None,
        country_iso="RU",
        exchange="MOEX_EVENING_WEEKEND",
        for_qual_only=False,
    )
    assert mapping.brief(found).model_dump() == {
        "uid": SBER,
        "figi": "BBG004730N88",
        "ticker": "SBER",
        "class_code": "TQBR",
        "isin": "RU0009029540",
        "name": "Сбер Банк",
        "instrument_type": "share",
        "currency": RUB,
    }


def test_fundamentals_leave_unfilled_figures_empty() -> None:
    [item] = answer(
        "GetAssetFundamentals",
        instruments_pb2.GetAssetFundamentalsResponse,
        sdk.GetAssetFundamentalsResponse,
    ).fundamentals

    found = mapping.fundamentals(item)

    assert found.model_dump(exclude={"asset_uid"}) == {
        "currency": RUB,
        "market_cap": Decimal("6529188292080"),
        "pe_ttm": Decimal("4.3"),
        "pb_ttm": Decimal("0.95"),
        "ev_ebitda": None,
        "dividend_yield_ttm": Decimal("12.4"),
        "net_debt_ebitda": None,
        "roe": Decimal("22.5"),
        "revenue_ttm": Decimal("4100000000000"),
        "net_income_ttm": Decimal("1600000000000"),
        "ebitda_ttm": None,
        "fcf_ttm": None,
        "total_debt": None,
        "beta": Decimal("1.1"),
        "high_52w": Decimal("514.59"),
        "low_52w": Decimal("293.14"),
    }


def test_forecasts() -> None:
    found = mapping.forecasts(
        answer("GetForecastBy", instruments_pb2.GetForecastResponse, sdk.GetForecastResponse)
    )

    assert found.consensus == TConsensus(
        recommendation="buy",
        target_avg=rub("378.08"),
        target_min=rub("317.58"),
        target_max=rub("393.2"),
        upside_pct=Decimal(25),
    )
    assert found.targets == [
        TTarget(
            company="Аналитики А", recommendation="buy", target=rub("393.2"), date=date(2026, 8, 28)
        ),
        TTarget(
            company="analysts-c",
            recommendation="hold",
            target=rub("317.58"),
            date=date(2026, 7, 15),
        ),
    ]


def test_dividends_without_dates_or_sums() -> None:
    dividends = answer(
        "GetDividends", instruments_pb2.GetDividendsResponse, sdk.GetDividendsResponse
    )

    found = [d for d in map(mapping.dividend, dividends.dividends) if d is not None]

    assert found == [
        TDividend(
            record_date=date(2025, 7, 18),
            payment_date=date(2025, 7, 25),
            last_buy_date=date(2025, 7, 17),
            amount=rub("34.84"),
            yield_pct=Decimal("10.89"),
        ),
        # announced: the record day stands in for the dates the API has not set yet
        TDividend(
            record_date=date(2026, 7, 17),
            payment_date=date(2026, 7, 17),
            last_buy_date=date(2026, 7, 17),
            amount=rub("37.5"),
            yield_pct=None,
        ),
    ]


def test_a_floating_coupon_not_yet_fixed_has_no_sum() -> None:
    coupons = answer(
        "GetBondCoupons", instruments_pb2.GetBondCouponsResponse, sdk.GetBondCouponsResponse
    )

    assert [mapping.coupon(c) for c in coupons.events] == [
        TCoupon(coupon_date=date(2025, 6, 4), number=9, amount=rub("35.4")),
        TCoupon(coupon_date=date(2027, 6, 2), number=13, amount=None),
    ]


def test_candles_and_last_prices() -> None:
    candles = answer("GetCandles", marketdata_pb2.GetCandlesResponse, sdk.GetCandlesResponse)
    prices = answer(
        "GetLastPrices", marketdata_pb2.GetLastPricesResponse, sdk.GetLastPricesResponse
    )

    assert mapping.candle(candles.candles[0]) == TCandle(
        time=datetime(2024, 10, 1, 7, tzinfo=UTC),
        open=Decimal("270.32"),
        high=Decimal("271.03"),
        low=Decimal("269.34"),
        close=Decimal(270),
        volume=160228,
        is_complete=True,
    )
    assert mapping.candle(candles.candles[1]).is_complete is False
    assert [mapping.price(p) for p in prices.last_prices] == [
        TPrice(
            instrument_uid=SBER,
            price=Decimal("302.46"),
            time=datetime(2026, 10, 2, 15, 39, 59, 123000, tzinfo=UTC),
        )
    ]


def test_report_events_without_a_date_are_dropped() -> None:
    reports = answer(
        "GetAssetReports", instruments_pb2.GetAssetReportsResponse, sdk.GetAssetReportsResponse
    )

    assert [mapping.report_event(SBER, e) for e in reports.events] == [
        TReportEvent(
            instrument_uid=SBER,
            report_date=date(2026, 10, 28),
            period_year=2026,
            period_num=3,
            period_type="quarter",
        ),
        None,
    ]


def failure(code: StatusCode, reset: str | None = None) -> AioRequestError:
    return AioRequestError(code, "details", Metadata("tracking", None, None, reset, None))


@pytest.mark.parametrize(
    ("code", "error", "expected", "retry_after_s"),
    [
        (StatusCode.RESOURCE_EXHAUSTED, TransientGatewayError, "tinvest_rate_limited", 12.0),
        (StatusCode.UNAUTHENTICATED, PermanentGatewayError, "token_invalid", None),
        (StatusCode.PERMISSION_DENIED, PermanentGatewayError, "token_invalid", None),
        (StatusCode.NOT_FOUND, PermanentGatewayError, "not_found", None),
        (StatusCode.INVALID_ARGUMENT, PermanentGatewayError, "tinvest_unavailable", None),
        (StatusCode.UNAVAILABLE, TransientGatewayError, "tinvest_unavailable", None),
        (StatusCode.DEADLINE_EXCEEDED, TransientGatewayError, "tinvest_unavailable", None),
    ],
)
def test_grpc_codes_map_as_the_core_says(
    code: StatusCode, error: type[GatewayError], expected: str, retry_after_s: float | None
) -> None:
    found = mapping.error(failure(code, "12"))

    assert isinstance(found, error)
    assert (found.code, found.retry_after_s) == (expected, retry_after_s)


async def test_a_read_turns_sdk_errors_into_gateway_errors() -> None:
    adapter = RealTInvest(Settings.model_construct())
    calls: list[int] = []

    async def refused() -> Any:
        calls.append(1)
        raise failure(StatusCode.UNAUTHENTICATED)

    with pytest.raises(PermanentGatewayError) as refusal:
        await adapter._read(refused)

    assert refusal.value.code == "token_invalid"
    assert calls == [1]  # a permanent error is not retried


async def test_find_skips_a_hit_the_instrument_service_does_not_know(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = RealTInvest(Settings.model_construct())
    gone = UUID("00000000-0000-4000-8000-000000000000")
    sber = mapping.instrument(
        answer(
            "GetInstrumentBy", instruments_pb2.InstrumentResponse, sdk.InstrumentResponse
        ).instrument
    )

    class Instruments:
        async def find_instrument(self, *, query: str) -> sdk.FindInstrumentResponse:
            hits = [short("SBERX", "TQBR", uid=str(gone)), short("SBER", "TQBR", uid=str(SBER))]
            return sdk.FindInstrumentResponse(instruments=hits)

    class Services:
        instruments = Instruments()

    async def get_instrument(token: Any, uid: UUID) -> TInstrument:
        if uid == gone:
            raise PermanentGatewayError("not_found")
        return sber

    monkeypatch.setattr(adapter, "_services", lambda token: Services())
    monkeypatch.setattr(adapter, "get_instrument", get_instrument)

    found = await adapter.find_instruments(SecretStr("t"), "сбер")

    assert [brief.ticker for brief in found] == ["SBER"]


def short(
    ticker: str, class_code: str, *, tradable: bool = True, **codes: str
) -> sdk.InstrumentShort:
    return sdk.InstrumentShort(
        ticker=ticker,
        class_code=class_code,
        uid=codes.get("uid", str(uuid4())),
        isin=codes.get("isin", ""),
        figi=codes.get("figi", ""),
        # The SDK annotates the flag as str; protobuf gives a bool.
        api_trade_available_flag=cast(Any, tradable),
    )


def test_search_ranks_the_exact_ticker_then_its_prefix_then_the_rest() -> None:
    hits = [
        short("SR250", "SPBOPT"),
        short("SBERP", "TQBR"),
        short("SBER", "SPBDE", tradable=False),
        short("GAZP", "TQBR", isin="RU0009029540"),
        short("SBER", "TQBR"),
    ]

    ranked = sorted(hits, key=lambda hit: mapping.search_rank(" sber ", hit))

    assert [(hit.ticker, hit.class_code) for hit in ranked] == [
        ("SBER", "TQBR"),
        ("SBER", "SPBDE"),
        ("SBERP", "TQBR"),
        ("SR250", "SPBOPT"),
        ("GAZP", "TQBR"),
    ]
    by_isin = sorted(hits, key=lambda hit: mapping.search_rank("ru0009029540", hit))
    assert (by_isin[0].ticker, by_isin[0].class_code) == ("GAZP", "TQBR")


async def test_find_fetches_the_best_hits_within_the_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = RealTInvest(Settings.model_construct())
    sber = mapping.instrument(
        answer(
            "GetInstrumentBy", instruments_pb2.InstrumentResponse, sdk.InstrumentResponse
        ).instrument
    )
    # The share comes last in the answer, behind derivatives named after it.
    hits = [short(f"SBER{n:02}", "SPBOPT") for n in range(12)] + [
        short("SBER", "TQBR", uid=str(SBER))
    ]
    fetched: list[UUID] = []

    class Instruments:
        async def find_instrument(self, *, query: str) -> sdk.FindInstrumentResponse:
            return sdk.FindInstrumentResponse(instruments=hits)

    class Services:
        instruments = Instruments()

    async def get_instrument(token: Any, uid: UUID) -> TInstrument:
        fetched.append(uid)
        return sber if uid == SBER else sber.model_copy(update={"uid": uid, "ticker": "SBER00"})

    monkeypatch.setattr(adapter, "_services", lambda token: Services())
    monkeypatch.setattr(adapter, "get_instrument", get_instrument)

    found = await adapter.find_instruments(SecretStr("t"), "SBER", limit=3)

    assert (found[0].ticker, found[0].class_code) == ("SBER", "TQBR")
    assert len(fetched) == 3  # one GetInstrumentBy per hit within the limit
