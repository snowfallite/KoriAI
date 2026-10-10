"""Answers of the T-Invest SDK as DTOs (tech.md §8.2): pure functions.

Protobuf has no null: an absent number comes as zero, an absent time as the epoch, an absent sum
as a MoneyValue without currency. The functions below turn those into None.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from grpc import StatusCode
from t_tech.invest import schemas as sdk
from t_tech.invest.exceptions import AioRequestError

from app.contracts.common import (
    AccessLevel,
    AccountStatus,
    AccountType,
    CandleInterval,
    InstrumentType,
    Money,
    OperationKind,
)
from app.contracts.tinvest import (
    Recommendation,
    TAccount,
    TCandle,
    TConsensus,
    TCoupon,
    TDividend,
    TForecasts,
    TFundamentals,
    TInstrument,
    TInstrumentBrief,
    TOperation,
    TOperationsPage,
    TPortfolio,
    TPosition,
    TPrice,
    TReportEvent,
    TTarget,
)
from app.core.errors import GatewayError, PermanentGatewayError, TransientGatewayError
from app.core.money import money_from_tinvest, quotation_to_decimal

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)

ACCOUNT_TYPES: dict[sdk.AccountType, AccountType] = {
    sdk.AccountType.ACCOUNT_TYPE_TINKOFF: "broker",
    sdk.AccountType.ACCOUNT_TYPE_TINKOFF_IIS: "iis",
    sdk.AccountType.ACCOUNT_TYPE_INVEST_BOX: "invest_box",
    sdk.AccountType.ACCOUNT_TYPE_INVEST_FUND: "invest_fund",
}
ACCOUNT_STATUSES: dict[sdk.AccountStatus, AccountStatus] = {
    sdk.AccountStatus.ACCOUNT_STATUS_NEW: "new",
    sdk.AccountStatus.ACCOUNT_STATUS_OPEN: "open",
    sdk.AccountStatus.ACCOUNT_STATUS_CLOSED: "closed",
}
ACCESS_LEVELS: dict[sdk.AccessLevel, AccessLevel] = {
    sdk.AccessLevel.ACCOUNT_ACCESS_LEVEL_FULL_ACCESS: "full_access",
    sdk.AccessLevel.ACCOUNT_ACCESS_LEVEL_READ_ONLY: "read_only",
    sdk.AccessLevel.ACCOUNT_ACCESS_LEVEL_NO_ACCESS: "no_access",
}
INSTRUMENT_KINDS: dict[sdk.InstrumentType, InstrumentType] = {
    sdk.InstrumentType.INSTRUMENT_TYPE_BOND: "bond",
    sdk.InstrumentType.INSTRUMENT_TYPE_SHARE: "share",
    sdk.InstrumentType.INSTRUMENT_TYPE_CURRENCY: "currency",
    sdk.InstrumentType.INSTRUMENT_TYPE_ETF: "etf",
    sdk.InstrumentType.INSTRUMENT_TYPE_FUTURES: "future",
    sdk.InstrumentType.INSTRUMENT_TYPE_SP: "structured",
    sdk.InstrumentType.INSTRUMENT_TYPE_OPTION: "option",
    sdk.InstrumentType.INSTRUMENT_TYPE_INDEX: "index",
}
# instrument_type of positions and instruments comes as a string.
INSTRUMENT_TYPES: dict[str, InstrumentType] = {
    "share": "share",
    "bond": "bond",
    "etf": "etf",
    "currency": "currency",
    "futures": "future",
    "option": "option",
    "sp": "structured",
    "index": "index",
}
OT = sdk.OperationType
OPERATION_TYPES: dict[OperationKind, list[sdk.OperationType]] = {
    "buy": [OT.OPERATION_TYPE_BUY, OT.OPERATION_TYPE_BUY_CARD, OT.OPERATION_TYPE_BUY_MARGIN,
            OT.OPERATION_TYPE_DELIVERY_BUY],
    "sell": [OT.OPERATION_TYPE_SELL, OT.OPERATION_TYPE_SELL_CARD, OT.OPERATION_TYPE_SELL_MARGIN,
             OT.OPERATION_TYPE_DELIVERY_SELL],
    "dividend": [OT.OPERATION_TYPE_DIVIDEND, OT.OPERATION_TYPE_DIV_EXT],
    "coupon": [OT.OPERATION_TYPE_COUPON],
    "amortization": [OT.OPERATION_TYPE_BOND_REPAYMENT, OT.OPERATION_TYPE_BOND_REPAYMENT_FULL],
    "commission": [OT.OPERATION_TYPE_BROKER_FEE, OT.OPERATION_TYPE_SERVICE_FEE,
                   OT.OPERATION_TYPE_MARGIN_FEE, OT.OPERATION_TYPE_SUCCESS_FEE,
                   OT.OPERATION_TYPE_TRACK_MFEE, OT.OPERATION_TYPE_TRACK_PFEE,
                   OT.OPERATION_TYPE_CASH_FEE, OT.OPERATION_TYPE_OUT_FEE,
                   OT.OPERATION_TYPE_ADVICE_FEE],
    "tax": [OT.OPERATION_TYPE_TAX, OT.OPERATION_TYPE_BOND_TAX, OT.OPERATION_TYPE_DIVIDEND_TAX,
            OT.OPERATION_TYPE_BENEFIT_TAX, OT.OPERATION_TYPE_TAX_CORRECTION,
            OT.OPERATION_TYPE_TAX_PROGRESSIVE, OT.OPERATION_TYPE_BOND_TAX_PROGRESSIVE,
            OT.OPERATION_TYPE_DIVIDEND_TAX_PROGRESSIVE, OT.OPERATION_TYPE_BENEFIT_TAX_PROGRESSIVE,
            OT.OPERATION_TYPE_TAX_CORRECTION_PROGRESSIVE, OT.OPERATION_TYPE_TAX_REPO_PROGRESSIVE,
            OT.OPERATION_TYPE_TAX_REPO, OT.OPERATION_TYPE_TAX_REPO_HOLD,
            OT.OPERATION_TYPE_TAX_REPO_REFUND, OT.OPERATION_TYPE_TAX_REPO_HOLD_PROGRESSIVE,
            OT.OPERATION_TYPE_TAX_REPO_REFUND_PROGRESSIVE,
            OT.OPERATION_TYPE_TAX_CORRECTION_COUPON, OT.OPERATION_TYPE_OUT_STAMP_DUTY],
    "input": [OT.OPERATION_TYPE_INPUT, OT.OPERATION_TYPE_INPUT_SWIFT,
              OT.OPERATION_TYPE_INPUT_ACQUIRING, OT.OPERATION_TYPE_INP_MULTI],
    "output": [OT.OPERATION_TYPE_OUTPUT, OT.OPERATION_TYPE_OUTPUT_SWIFT,
               OT.OPERATION_TYPE_OUTPUT_ACQUIRING, OT.OPERATION_TYPE_OUT_MULTI],
}  # fmt: skip
OPERATION_KINDS: dict[sdk.OperationType, OperationKind] = {
    t: kind for kind, types in OPERATION_TYPES.items() for t in types
}
RECOMMENDATIONS: dict[sdk.Recommendation, Recommendation] = {
    sdk.Recommendation.RECOMMENDATION_BUY: "buy",
    sdk.Recommendation.RECOMMENDATION_HOLD: "hold",
    sdk.Recommendation.RECOMMENDATION_SELL: "sell",
}
type ReportPeriod = Literal["quarter", "semiannual", "annual", "other"]
REPORT_PERIODS: dict[sdk.AssetReportPeriodType, ReportPeriod] = {
    sdk.AssetReportPeriodType.PERIOD_TYPE_QUARTER: "quarter",
    sdk.AssetReportPeriodType.PERIOD_TYPE_SEMIANNUAL: "semiannual",
    sdk.AssetReportPeriodType.PERIOD_TYPE_ANNUAL: "annual",
}
INTERVALS: dict[CandleInterval, sdk.CandleInterval] = {
    "day": sdk.CandleInterval.CANDLE_INTERVAL_DAY,
    "week": sdk.CandleInterval.CANDLE_INTERVAL_WEEK,
    "month": sdk.CandleInterval.CANDLE_INTERVAL_MONTH,
}


def decimal(value: sdk.Quotation) -> Decimal:
    return quotation_to_decimal(value.units, value.nano)


def nonzero(value: sdk.Quotation | None) -> Decimal | None:
    return None if value is None or (value.units == 0 and value.nano == 0) else decimal(value)


def money(value: sdk.MoneyValue | None) -> Money | None:
    return money_from_tinvest(value) if value is not None and value.currency else None


def nonzero_money(value: sdk.MoneyValue | None) -> Money | None:
    found = money(value)
    return found if found is not None and found.amount != 0 else None


def day(moment: datetime | None) -> date | None:
    return moment.date() if moment is not None and moment > EPOCH else None


def uid_or_none(text: str) -> UUID | None:
    return UUID(text) if text else None


def account(item: sdk.Account) -> TAccount:
    return TAccount(
        id=item.id,
        name=item.name,
        type=ACCOUNT_TYPES.get(item.type, "other"),
        status=ACCOUNT_STATUSES.get(item.status, "other"),
        opened_date=day(item.opened_date),
        access_level=ACCESS_LEVELS.get(item.access_level, "unspecified"),
    )


def position(item: sdk.PortfolioPosition) -> TPosition:
    current, average = money(item.current_price), money(item.average_position_price)
    # The yield of a position is a Quotation in the currency of its prices.
    priced = current or average
    currency = priced.currency if priced is not None else None
    return TPosition(
        instrument_uid=UUID(item.instrument_uid),
        figi=item.figi,
        instrument_type=INSTRUMENT_TYPES.get(item.instrument_type, "other"),
        quantity=decimal(item.quantity),
        average_price=average,
        current_price=current,
        expected_yield=Money(amount=decimal(item.expected_yield), currency=currency)
        if currency and item.expected_yield is not None
        else None,
        accrued_interest=nonzero_money(item.current_nkd),
        blocked=item.blocked,
    )


def portfolio(answer: sdk.PortfolioResponse) -> TPortfolio:
    totals: dict[InstrumentType, sdk.MoneyValue] = {
        "share": answer.total_amount_shares,
        "bond": answer.total_amount_bonds,
        "etf": answer.total_amount_etf,
        "currency": answer.total_amount_currencies,
        "future": answer.total_amount_futures,
        "option": answer.total_amount_options,
        "structured": answer.total_amount_sp,
    }
    by_type = {kind: m for kind, value in totals.items() if (m := nonzero_money(value))}
    total = money(answer.total_amount_portfolio) or Money(amount=Decimal(0), currency="RUB")
    return TPortfolio(
        account_id=answer.account_id,
        total=total,
        total_by_type=by_type,
        # The API gives the yield of the whole portfolio in percent only.
        expected_yield=None,
        expected_yield_pct=decimal(answer.expected_yield)
        if answer.expected_yield is not None
        else None,
        positions=[position(p) for p in answer.positions],
    )


def operation(item: sdk.OperationItem) -> TOperation:
    return TOperation(
        id=item.id,
        kind=OPERATION_KINDS.get(item.type, "other"),
        date=item.date,
        instrument_uid=uid_or_none(item.instrument_uid),
        payment=money(item.payment) or Money(amount=Decimal(0), currency="RUB"),
        quantity=Decimal(item.quantity) if item.quantity else None,
        price=nonzero_money(item.price),
        description=item.description or item.name,
    )


def operations_page(answer: sdk.GetOperationsByCursorResponse) -> TOperationsPage:
    return TOperationsPage(
        items=[operation(item) for item in answer.items],
        next_cursor=answer.next_cursor if answer.has_next and answer.next_cursor else None,
    )


def _type_of(
    item: sdk.Instrument | sdk.Share | sdk.Bond | sdk.Etf | sdk.Currency,
) -> InstrumentType:
    match item:
        case sdk.Instrument():
            return INSTRUMENT_TYPES.get(item.instrument_type, "other")
        case sdk.Share():
            return "share"
        case sdk.Bond():
            return "bond"
        case sdk.Etf():
            return "etf"
    return "currency"


def instrument(item: sdk.Instrument | sdk.Share | sdk.Bond | sdk.Etf | sdk.Currency) -> TInstrument:
    logo = item.brand.logo_name if item.brand else ""
    color = item.brand.logo_base_color if item.brand else ""
    return TInstrument(
        uid=UUID(item.uid),
        figi=item.figi or None,
        ticker=item.ticker,
        class_code=item.class_code,
        isin=item.isin or None,
        name=item.name,
        instrument_type=_type_of(item),
        currency=item.currency.upper(),
        lot=item.lot,
        asset_uid=uid_or_none(item.asset_uid),
        # The brand uid comes only with the asset (GetAssetBy): the domain fills it in.
        brand_uid=None,
        logo_name=logo or None,
        brand_color=color or None,
        # Instrument and Currency have no sector.
        sector=getattr(item, "sector", "") or None,
        country_iso=item.country_of_risk or None,
        exchange=item.exchange or None,
        for_qual_only=item.for_qual_investor_flag,
    )


def indicative(item: sdk.IndicativeResponse) -> TInstrument:
    return TInstrument(
        uid=UUID(item.uid),
        figi=item.figi or None,
        ticker=item.ticker,
        class_code=item.class_code,
        isin=None,
        name=item.name,
        instrument_type=INSTRUMENT_KINDS.get(item.instrument_kind, "other"),
        currency=(item.currency or "rub").upper(),
        lot=1,
        asset_uid=None,
        brand_uid=None,
        logo_name=None,
        brand_color=None,
        sector=None,
        country_iso=None,
        exchange=item.exchange or None,
        for_qual_only=False,
    )


def brief(item: TInstrument) -> TInstrumentBrief:
    return TInstrumentBrief(**item.model_dump(include=set(TInstrumentBrief.model_fields)))


def search_rank(query: str, hit: sdk.InstrumentShort) -> tuple[int, bool]:
    """The order of FindInstrument hits the fake keeps too: the exact ticker or code first, then
    tickers that start with the query, then the rest; tradable hits first within each step."""
    needle = query.strip().casefold()
    ticker = hit.ticker.casefold()
    codes = {hit.isin.casefold(), hit.figi.casefold(), hit.uid.casefold()} - {""}
    if ticker == needle or needle in codes:
        step = 0
    elif ticker.startswith(needle):
        step = 1
    else:
        step = 2
    # The SDK annotates the flag as str; protobuf gives a bool.
    tradable: object = hit.api_trade_available_flag
    return step, tradable is not True


def _figure(value: float) -> Decimal | None:
    # A double the API did not fill in comes as 0: no figure rather than a zero.
    return Decimal(repr(value)) if value else None


def fundamentals(item: sdk.StatisticResponse) -> TFundamentals:
    return TFundamentals(
        asset_uid=UUID(item.asset_uid),
        currency=item.currency.upper(),
        market_cap=_figure(item.market_capitalization),
        pe_ttm=_figure(item.pe_ratio_ttm),
        pb_ttm=_figure(item.price_to_book_ttm),
        ev_ebitda=_figure(item.ev_to_ebitda_mrq),
        dividend_yield_ttm=_figure(item.dividend_yield_daily_ttm),
        net_debt_ebitda=_figure(item.net_debt_to_ebitda),
        roe=_figure(item.roe),
        revenue_ttm=_figure(item.revenue_ttm),
        net_income_ttm=_figure(item.net_income_ttm),
        ebitda_ttm=_figure(item.ebitda_ttm),
        fcf_ttm=_figure(item.free_cash_flow_ttm),
        total_debt=_figure(item.total_debt_mrq),
        beta=_figure(item.beta),
        high_52w=_figure(item.high_price_last_52_weeks),
        low_52w=_figure(item.low_price_last_52_weeks),
    )


def report_event(instrument_uid: UUID, item: sdk.GetAssetReportsEvent) -> TReportEvent | None:
    reported = day(item.report_date)
    if reported is None:
        return None
    return TReportEvent(
        instrument_uid=instrument_uid,
        report_date=reported,
        period_year=item.period_year,
        period_num=item.period_num,
        period_type=REPORT_PERIODS.get(item.period_type, "other"),
    )


def forecasts(answer: sdk.GetForecastResponse) -> TForecasts:
    c = answer.consensus
    consensus = None
    if c is not None and c.uid:
        currency = c.currency.upper()

        def target(value: sdk.Quotation) -> Money | None:
            found = nonzero(value)
            return Money(amount=found, currency=currency) if found is not None else None

        consensus = TConsensus(
            recommendation=RECOMMENDATIONS.get(c.recommendation, "unknown"),
            target_avg=target(c.consensus),
            target_min=target(c.min_target),
            target_max=target(c.max_target),
            upside_pct=nonzero(c.price_change_rel),
        )
    targets = [
        TTarget(
            company=t.show_name or t.company,
            recommendation=RECOMMENDATIONS.get(t.recommendation, "unknown"),
            target=Money(amount=decimal(t.target_price), currency=t.currency.upper()),
            date=recommended,
        )
        for t in answer.targets
        if (recommended := day(t.recommendation_date)) is not None
    ]
    return TForecasts(consensus=consensus, targets=targets)


def dividend(item: sdk.Dividend) -> TDividend | None:
    record, amount = day(item.record_date), money(item.dividend_net)
    if record is None or amount is None:
        return None
    return TDividend(
        record_date=record,
        # Announced payouts may lack the other dates: the record day stands in.
        payment_date=day(item.payment_date) or record,
        last_buy_date=day(item.last_buy_date) or record,
        amount=amount,
        yield_pct=nonzero(item.yield_value),
    )


def coupon(item: sdk.Coupon) -> TCoupon | None:
    paid = day(item.coupon_date)
    if paid is None:
        return None
    # A floating coupon not yet fixed comes as zero: unknown, not free.
    return TCoupon(
        coupon_date=paid, number=item.coupon_number, amount=nonzero_money(item.pay_one_bond)
    )


def candle(item: sdk.HistoricCandle) -> TCandle:
    return TCandle(
        time=item.time,
        open=decimal(item.open),
        high=decimal(item.high),
        low=decimal(item.low),
        close=decimal(item.close),
        volume=item.volume,
        is_complete=item.is_complete,
    )


def price(item: sdk.LastPrice) -> TPrice:
    return TPrice(
        instrument_uid=UUID(item.instrument_uid), price=decimal(item.price), time=item.time
    )


def error(exc: AioRequestError) -> GatewayError:
    """gRPC codes as §8.2 maps them."""
    match exc.code:
        case StatusCode.RESOURCE_EXHAUSTED:
            reset = getattr(exc.metadata, "ratelimit_reset", None)
            return TransientGatewayError(
                "tinvest_rate_limited", float(reset) if reset is not None else None
            )
        case StatusCode.UNAUTHENTICATED | StatusCode.PERMISSION_DENIED:
            return PermanentGatewayError("token_invalid")
        case StatusCode.NOT_FOUND:
            return PermanentGatewayError("not_found")
        case StatusCode.INVALID_ARGUMENT | StatusCode.FAILED_PRECONDITION | StatusCode.OUT_OF_RANGE:
            return PermanentGatewayError("tinvest_unavailable")
    return TransientGatewayError("tinvest_unavailable")  # UNAVAILABLE, DEADLINE_EXCEEDED, others
