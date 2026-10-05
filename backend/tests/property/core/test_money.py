"""Quotation and MoneyValue of T-Invest as Decimal: the invariants of tech.md §11."""

from dataclasses import dataclass
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from app.core.money import (
    NANO,
    decimal_to_quotation,
    money_from_tinvest,
    quotation_to_decimal,
)

INT64 = 2**63 - 1


@dataclass(frozen=True)
class MoneyValue:
    currency: str
    units: int
    nano: int


@st.composite
def quotations(draw: st.DrawFn) -> tuple[int, int]:
    """units and nano as the API sends them: one sign, |nano| < 10^9."""
    sign = draw(st.sampled_from([1, -1]))
    units = draw(st.integers(0, INT64))
    nano = draw(st.integers(0, NANO - 1))
    return sign * units, sign * nano


# Nine decimals at most, inside int64 units: everything a Quotation can hold.
decimals = st.decimals(
    min_value=-INT64, max_value=INT64, places=9, allow_nan=False, allow_infinity=False
)


@given(quotations())
def test_a_quotation_survives_the_round_trip(quotation: tuple[int, int]) -> None:
    assert decimal_to_quotation(quotation_to_decimal(*quotation)) == quotation


@given(decimals)
def test_a_decimal_survives_the_round_trip(value: Decimal) -> None:
    assert quotation_to_decimal(*decimal_to_quotation(value)) == value


@given(decimals)
def test_units_and_nano_share_the_sign_and_nano_stays_below_a_unit(value: Decimal) -> None:
    units, nano = decimal_to_quotation(value)

    assert abs(nano) < NANO
    assert units * nano >= 0
    assert (units < 0 or nano < 0) == (value < 0)


@given(quotations(), st.sampled_from(["rub", "usd", "cny", "RUB"]))
def test_money_takes_the_currency_in_upper_case(quotation: tuple[int, int], code: str) -> None:
    units, nano = quotation
    money = money_from_tinvest(MoneyValue(currency=code, units=units, nano=nano))

    assert money.currency == code.upper()
    assert money.amount == quotation_to_decimal(units, nano)


def test_known_values() -> None:
    assert quotation_to_decimal(114, 250_000_000) == Decimal("114.25")
    assert quotation_to_decimal(-200, -200_000_000) == Decimal("-200.2")
    assert decimal_to_quotation(Decimal("-0.000000001")) == (0, -1)
    assert decimal_to_quotation(Decimal("1.0000000004")) == (1, 0)  # rounds to nine places
