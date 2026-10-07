"""The portfolio the API answers, assembled from any account portfolios (tech.md §6.4, S1-11 AC 1):
the total is the sum of the values in rubles, the weights sum to one, the allocation splits the
total, and every position of every account stays."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from app.contracts.api.instruments import InstrumentBrief
from app.contracts.common import Money
from app.contracts.tinvest import TPortfolio, TPosition
from app.domains.portfolio.mapping import Holdings, portfolio_out

RATES = {"CNY": Decimal("11.6943"), "USD": Decimal("81.2345")}
AS_OF = datetime(2026, 10, 2, 16, 0, tzinfo=UTC)
TOLERANCE = Decimal("1e-9")


@st.composite
def positions(draw: st.DrawFn) -> TPosition:
    currency = draw(st.sampled_from(["RUB", *RATES]))
    price = draw(st.decimals(min_value=Decimal("0.0001"), max_value=Decimal("100000"), places=4))
    accrued = draw(st.none() | st.decimals(min_value=0, max_value=100, places=2))
    earned = draw(st.none() | st.decimals(min_value=-1000, max_value=1000, places=2))
    return TPosition(
        instrument_uid=draw(st.uuids()),
        figi="BBG000000000",
        instrument_type=draw(st.sampled_from(["share", "bond", "etf", "currency"])),
        quantity=draw(st.decimals(min_value=Decimal("0.01"), max_value=Decimal("1e6"), places=2)),
        average_price=Money(amount=price, currency=currency),
        current_price=Money(amount=price, currency=currency),
        expected_yield=None if earned is None else Money(amount=earned, currency=currency),
        accrued_interest=None if accrued is None else Money(amount=accrued, currency=currency),
        blocked=False,
    )


@st.composite
def accounts(draw: st.DrawFn) -> list[Holdings]:
    count = draw(st.integers(1, 3))
    found = []
    for n in range(1, count + 1):
        portfolio = TPortfolio(
            account_id=str(n),
            total=Money(amount=Decimal(0), currency="RUB"),
            total_by_type={},
            expected_yield=None,
            expected_yield_pct=draw(st.none() | st.decimals(-50, 50, places=2)),
            positions=draw(st.lists(positions(), max_size=12)),
        )
        found.append(Holdings(alias=f"acc{n}", name=f"Счёт {n}", portfolio=portfolio))
    return found


def briefs(holdings: list[Holdings], known: set[uuid.UUID]) -> dict[uuid.UUID, InstrumentBrief]:
    """Briefs of some instruments: the others stand for ones T-Invest no longer knows."""
    return {
        p.instrument_uid: InstrumentBrief(
            uid=p.instrument_uid,
            ticker="TEST",
            class_code="TQBR",
            name="Тест",
            instrument_type=p.instrument_type,
            currency=p.current_price.currency if p.current_price else "RUB",
            logo_url=None,
            brand_color=None,
        )
        for h in holdings
        for p in h.portfolio.positions
        if p.instrument_uid in known
    }


@given(accounts(), st.data())
def test_the_answer_keeps_every_position_and_adds_up(
    holdings: list[Holdings], data: st.DataObject
) -> None:
    uids = sorted({p.instrument_uid for h in holdings for p in h.portfolio.positions})
    known = set(data.draw(st.lists(st.sampled_from(uids), unique=True))) if uids else set()

    found = portfolio_out(holdings, briefs(holdings, known), RATES, AS_OF)

    held = sorted((h.alias, str(p.instrument_uid)) for h in holdings for p in h.portfolio.positions)
    assert sorted((p.account_alias, str(p.instrument.uid)) for p in found.positions) == held
    assert found.total.amount == sum((p.value_rub.amount for p in found.positions), Decimal(0))
    assert {p.value_rub.currency for p in found.positions} <= {"RUB"}
    assert [a.alias for a in found.accounts] == [h.alias for h in holdings]
    assert sum((a.total.amount for a in found.accounts), Decimal(0)) == found.total.amount
    assert sum((s.value.amount for s in found.allocation), Decimal(0)) == found.total.amount
    values = [p.value_rub.amount for p in found.positions]
    assert values == sorted(values, reverse=True)
    if found.total.amount > 0:
        assert abs(sum((p.weight for p in found.positions), Decimal(0)) - 1) <= TOLERANCE
        assert abs(sum((s.weight for s in found.allocation), Decimal(0)) - 1) <= TOLERANCE
        assert all(p.weight >= 0 for p in found.positions)
    assert found.as_of == AS_OF
