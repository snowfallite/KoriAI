"""GET /api/portfolio on the seed (S1-11 AC 1-5, tech.md §6.4). Expectations come from the seed
files read here: the positions with their prices and accrued interest, and the last close of the
currency instrument for each foreign price currency."""

import csv
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
import pytest
import yaml
from fastapi import FastAPI
from sqlalchemy import select, update

from app.contracts.api.portfolio import PortfolioOut, PositionOut
from app.contracts.common import ErrorCode, ErrorOut
from app.contracts.faults import FaultPlan, FaultRule
from app.db.base import UnitOfWork
from app.db.schema.broker import BrokerAccount, BrokerConnection, Instrument
from app.gateways.factory import Gateways
from app.gateways.fakes import Fake
from app.gateways.fixtures import SEED
from tests.support.seed import seed_user

TINVEST = SEED / "tinvest"
NANO = Decimal("1e-9")
# §6.4: value_rub goes by the last prices of the currency instruments.
RATE_SOURCES = {"USD": "USD000UTSTOM", "EUR": "EUR_RUB__TOM", "CNY": "CNYRUB_TOM"}
WEIGHT_TOLERANCE = Decimal("1e-9")  # S1-11 AC 1


def seed_yaml(*parts: str) -> Any:
    return yaml.safe_load(TINVEST.joinpath(*parts).read_text(encoding="utf-8"))


def last_close(ticker: str) -> Decimal:
    with TINVEST.joinpath("candles", f"{ticker}.csv").open(encoding="utf-8", newline="") as rows:
        return Decimal(list(csv.DictReader(rows))[-1]["close"])


def aliases() -> dict[str, str]:
    """External account id to alias: aliases go by the opening day (§5.2)."""
    accounts = sorted(seed_yaml("accounts.yaml"), key=lambda account: account["opened_date"])
    return {account["id"]: f"acc{n}" for n, account in enumerate(accounts, 1)}


def seed_portfolio(alias: str) -> dict[str, Any]:
    [external_id] = [key for key, value in aliases().items() if value == alias]
    portfolio: dict[str, Any] = seed_yaml("portfolios", f"{external_id}.yaml")
    return portfolio


def seed_value(position: dict[str, Any]) -> tuple[Decimal, str]:
    """Quantity times the price plus the accrued interest of one unit, in the price currency."""
    price = position["current_price"]
    accrued = position["accrued_interest"]
    unit = Decimal(price["amount"]) + (Decimal(accrued["amount"]) if accrued else 0)
    return Decimal(position["quantity"]) * unit, price["currency"]


def in_rubles(amount: Decimal, currency: str) -> Decimal:
    return amount if currency == "RUB" else amount * last_close(RATE_SOURCES[currency])


def total_of(positions: list[PositionOut]) -> Decimal:
    return sum((p.value_rub.amount for p in positions), Decimal(0))


async def portfolio(client: httpx.AsyncClient, **params: str) -> PortfolioOut:
    reply = await client.get("/api/portfolio", params=params)
    assert reply.status_code == 200, reply.text
    return PortfolioOut.model_validate(reply.json())


def tinvest_fake(app: FastAPI) -> Fake:
    gateways: Gateways = app.state.gateways
    assert isinstance(gateways.tinvest, Fake)
    return gateways.tinvest


async def test_the_demo_portfolio_values_every_seed_position_in_rubles(
    demo_api: httpx.AsyncClient,
) -> None:
    started = datetime.now(UTC)
    found = await portfolio(demo_api)

    expected = {}
    for alias in ("acc1", "acc2"):
        for position in seed_portfolio(alias)["positions"]:
            value, currency = seed_value(position)
            expected[alias, position["instrument_uid"]] = (
                value,
                currency,
                in_rubles(value, currency),
            )
    assert {(p.account_alias, str(p.instrument.uid)) for p in found.positions} == expected.keys()
    for p in found.positions:
        value, currency, rub = expected[p.account_alias, str(p.instrument.uid)]
        assert (p.value.amount, p.value.currency) == (value.quantize(NANO), currency)
        assert (p.value_rub.amount, p.value_rub.currency) == (rub.quantize(NANO), "RUB")
    assert found.currency == "RUB"
    assert started <= found.as_of <= datetime.now(UTC)


async def test_weights_sum_to_one_and_the_total_is_the_sum_of_values(
    demo_api: httpx.AsyncClient,
) -> None:
    found = await portfolio(demo_api)

    assert abs(sum((p.weight for p in found.positions), Decimal(0)) - 1) <= WEIGHT_TOLERANCE
    assert found.total.currency == "RUB"
    assert found.total.amount == total_of(found.positions)
    for p in found.positions:
        assert abs(p.weight - p.value_rub.amount / found.total.amount) <= WEIGHT_TOLERANCE


async def test_each_account_sums_its_positions_and_matches_its_seed_portfolio(
    demo_api: httpx.AsyncClient,
) -> None:
    found = await portfolio(demo_api)
    names = {account["id"]: account["name"] for account in seed_yaml("accounts.yaml")}

    assert [(a.alias, a.name) for a in found.accounts] == [
        (alias, names[external_id]) for external_id, alias in aliases().items()
    ]
    for account in found.accounts:
        seed = seed_portfolio(account.alias)
        own = [p for p in found.positions if p.account_alias == account.alias]
        assert account.total.amount == total_of(own)
        # The seed totals of T-Invest are rounded to kopecks per instrument type.
        assert abs(account.total.amount - Decimal(seed["total"]["amount"])) <= Decimal("0.01")
        assert account.expected_yield is not None
        assert account.expected_yield.currency == "RUB"
        seed_yield = Decimal(seed["expected_yield"]["amount"])
        assert abs(account.expected_yield.amount - seed_yield) <= Decimal("0.01")
        # T-Invest gives the yield in percent, the API in shares like the weights.
        assert account.expected_yield_pct == Decimal(seed["expected_yield_pct"]) / 100
    assert sum((a.total.amount for a in found.accounts), Decimal(0)) == found.total.amount


async def test_allocation_splits_the_total_by_instrument_type(demo_api: httpx.AsyncClient) -> None:
    found = await portfolio(demo_api)

    by_type: dict[str, Decimal] = {}
    for p in found.positions:
        by_type[p.instrument.instrument_type] = by_type.get(p.instrument.instrument_type, 0) + (
            p.value_rub.amount
        )
    assert {s.key: s.value.amount for s in found.allocation} == by_type
    assert all(s.value.currency == "RUB" and s.label for s in found.allocation)
    assert len({s.label for s in found.allocation}) == len(found.allocation)
    assert abs(sum((s.weight for s in found.allocation), Decimal(0)) - 1) <= WEIGHT_TOLERANCE


async def test_an_account_filter_keeps_that_account_only(demo_api: httpx.AsyncClient) -> None:
    everything = await portfolio(demo_api)
    found = await portfolio(demo_api, account="acc2")

    [account] = found.accounts
    assert account.alias == "acc2"
    assert {p.account_alias for p in found.positions} == {"acc2"}
    assert len(found.positions) == len(seed_portfolio("acc2")["positions"])
    assert found.total.amount == total_of(found.positions)
    assert found.total == next(a.total for a in everything.accounts if a.alias == "acc2")
    assert abs(sum((p.weight for p in found.positions), Decimal(0)) - 1) <= WEIGHT_TOLERANCE


@pytest.mark.parametrize("account", ["acc9", "acc", "all"])
async def test_an_unknown_account_is_refused(demo_api: httpx.AsyncClient, account: str) -> None:
    reply = await demo_api.get("/api/portfolio", params={"account": account})

    assert reply.status_code == 422
    assert ErrorOut.model_validate(reply.json()).code == "validation_error"


async def test_a_hidden_account_stays_out(app: FastAPI, demo_api: httpx.AsyncClient) -> None:
    async with UnitOfWork(app.state.engine) as session:
        await session.execute(
            update(BrokerAccount).where(BrokerAccount.alias == "acc2").values(is_hidden=True)
        )

    found = await portfolio(demo_api)
    hidden = await demo_api.get("/api/portfolio", params={"account": "acc2"})

    assert [a.alias for a in found.accounts] == ["acc1"]
    assert {p.account_alias for p in found.positions} == {"acc1"}
    assert hidden.status_code == 422


async def test_an_account_tinvest_does_not_know_counts_as_empty(
    app: FastAPI, demo_api: httpx.AsyncClient
) -> None:
    # A closed account may vanish from T-Invest; the others must still show.
    async with UnitOfWork(app.state.engine) as session:
        connection_id = await session.scalar(select(BrokerConnection.id))
        session.add(
            BrokerAccount(
                connection_id=connection_id,
                external_id="2999999999",
                alias="acc3",
                name="Закрытый счёт",
                type="broker",
                status="closed",
                access_level="read_only",
            )
        )

    found = await portfolio(demo_api)

    gone = next(a for a in found.accounts if a.alias == "acc3")
    assert gone.total.amount == 0
    assert gone.expected_yield is None
    assert {p.account_alias for p in found.positions} == {"acc1", "acc2"}


async def test_without_a_broker_the_portfolio_answers_409(user_api: httpx.AsyncClient) -> None:
    reply = await user_api.get("/api/portfolio")

    assert reply.status_code == 409
    assert ErrorOut.model_validate(reply.json()).code == "broker_not_connected"


@pytest.mark.parametrize(
    ("rule", "code"),
    [
        (FaultRule(method="get_portfolio", mode="error", error_code="tinvest_unavailable"), None),
        (FaultRule(method="get_portfolio", mode="timeout"), "tinvest_unavailable"),
        (FaultRule(method="get_instrument", mode="timeout"), "tinvest_unavailable"),
        (FaultRule(method="get_last_prices", mode="timeout"), "tinvest_unavailable"),
    ],
)
async def test_a_tinvest_failure_answers_503(
    demo_api: httpx.AsyncClient,
    faults: Any,
    rule: FaultRule,
    code: ErrorCode | None,
) -> None:
    plan: FaultPlan = faults(rule.model_copy(update={"times": 100}))

    reply = await demo_api.get("/api/portfolio")

    assert reply.status_code == 503, reply.text
    error = ErrorOut.model_validate(reply.json())
    assert error.code == (code or plan.rules[0].error_code)
    assert error.message
    assert error.request_id == reply.headers["x-request-id"]


async def test_a_tinvest_rate_limit_answers_503_with_retry_after(
    demo_api: httpx.AsyncClient, faults: Any
) -> None:
    faults(FaultRule(method="get_portfolio", mode="rate_limit", latency_ms=30_000, times=100))

    reply = await demo_api.get("/api/portfolio")

    assert reply.status_code == 503
    assert ErrorOut.model_validate(reply.json()).code == "tinvest_rate_limited"
    assert reply.headers["retry-after"] == "30"


async def test_logos_go_through_the_media_proxy(demo_api: httpx.AsyncClient) -> None:
    found = await portfolio(demo_api)
    logos = {item["uid"]: item["logo_name"] for item in seed_yaml("instruments.yaml")}

    for p in found.positions:
        name = logos[str(p.instrument.uid)]
        expected = None if name is None else f"/api/media/logos/{name.removesuffix('.png')}"
        assert p.instrument.logo_url == expected
    # The yuan bond of the seed has no logo: the UI shows its initials (S1-11 AC 5).
    assert any(p.instrument.logo_url is None for p in found.positions)


async def test_instruments_are_stored_on_first_use(
    app: FastAPI, demo_api: httpx.AsyncClient
) -> None:
    first = await portfolio(demo_api)
    fake = tinvest_fake(app)
    looked_up = [call for call in fake.calls if call.method == "get_instrument"]

    second = await portfolio(demo_api)

    # The second request reads the instruments from the table, not from T-Invest.
    assert [call for call in fake.calls if call.method == "get_instrument"] == looked_up
    assert second.positions == first.positions
    uids = {p.instrument.uid for p in first.positions}
    async with UnitOfWork(app.state.engine) as session:
        rows = (await session.execute(select(Instrument).where(Instrument.uid.in_(uids)))).scalars()
        stored = {row.uid: row for row in rows}
    assert stored.keys() == uids
    seed = {item["uid"]: item for item in seed_yaml("instruments.yaml")}
    for uid, row in stored.items():
        item = seed[str(uid)]
        assert (row.ticker, row.class_code, row.name) == (
            item["ticker"],
            item["class_code"],
            item["name"],
        )
        logo = item["logo_name"]
        assert row.logo_base == (logo.removesuffix(".png") if logo else None)


async def test_account_ids_and_the_token_stay_in_the_backend(demo_api: httpx.AsyncClient) -> None:
    reply = await demo_api.get("/api/portfolio")
    token = seed_user("user").broker_token

    assert token is not None
    for secret in [*aliases().keys(), token.get_secret_value()]:
        assert secret not in reply.text
