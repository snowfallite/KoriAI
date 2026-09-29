"""DecimalStr, Money and UTC time on the wire (tech.md §6.1, §12.2)."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from app.contracts.common import DecimalStr, Money, UtcDatetime

decimal_str: TypeAdapter[Decimal] = TypeAdapter(DecimalStr)
utc_datetime: TypeAdapter[datetime] = TypeAdapter(UtcDatetime)


@pytest.mark.parametrize(
    ("raw", "value"),
    [("0", "0"), ("12.30", "12.30"), ("-0.5", "-0.5"), ("1250000", "1250000"), ("007", "7")],
)
def test_decimal_str_reads_plain_decimals(raw: str, value: str) -> None:
    assert decimal_str.validate_python(raw) == Decimal(value)


@pytest.mark.parametrize(
    "raw",
    ["", "1e5", "1E+3", "+1", "1.", ".5", " 1", "1 ", "1,5", "NaN", "Infinity", "٣"],
)
def test_decimal_str_rejects_other_strings(raw: str) -> None:
    with pytest.raises(ValidationError):
        decimal_str.validate_python(raw)


@pytest.mark.parametrize("raw", [1.5, True, Decimal("NaN"), Decimal("Infinity")])
def test_decimal_str_rejects_floats_and_non_finite(raw: object) -> None:
    with pytest.raises(ValidationError):
        decimal_str.validate_python(raw)


@pytest.mark.parametrize(
    ("value", "wire"),
    [
        (Decimal("1E+3"), "1000"),
        (Decimal("1E-7"), "0.0000001"),
        (Decimal("-1.50"), "-1.50"),
        (Decimal("0.000"), "0.000"),
    ],
)
def test_decimal_str_writes_the_pattern(value: Decimal, wire: str) -> None:
    assert decimal_str.dump_python(value, mode="json") == wire
    assert decimal_str.dump_python(value) == value


def test_money_round_trip() -> None:
    money = Money.model_validate({"amount": "1250000.50", "currency": "RUB"})

    assert money == Money(amount=Decimal("1250000.5"), currency="RUB")
    assert money.model_dump(mode="json") == {"amount": "1250000.50", "currency": "RUB"}


@pytest.mark.parametrize(
    "raw",
    [
        {"amount": "1", "currency": "rub"},
        {"amount": "1", "currency": "RUBL"},
        {"amount": 1.5, "currency": "RUB"},
        {"amount": "1", "currency": "RUB", "rate": "1"},
    ],
)
def test_money_rejects_bad_input(raw: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Money.model_validate(raw)


def test_time_goes_out_in_utc_with_z() -> None:
    moment = utc_datetime.validate_python("2026-09-29T03:00:00+03:00")

    assert moment == datetime(2026, 9, 29, tzinfo=UTC)
    assert utc_datetime.dump_python(moment, mode="json") == "2026-09-29T00:00:00Z"


def test_naive_time_is_rejected() -> None:
    with pytest.raises(ValidationError):
        utc_datetime.validate_python("2026-09-29T03:00:00")
