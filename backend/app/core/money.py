"""Quotation and MoneyValue of T-Invest as Decimal (tech.md §8.2, §11)."""

from decimal import Decimal, localcontext
from typing import Protocol

from app.contracts.common import Money

NANO = 1_000_000_000
# int64 units with nine decimals need 28 digits: more than the default context guarantees.
PRECISION = 40


class MoneyValue(Protocol):
    """MoneyValue of the SDK: units and nano carry the same sign, |nano| < 10^9."""

    @property
    def currency(self) -> str: ...
    @property
    def units(self) -> int: ...
    @property
    def nano(self) -> int: ...


def quotation_to_decimal(units: int, nano: int) -> Decimal:
    with localcontext() as context:
        context.prec = PRECISION
        return (Decimal(units) + Decimal(nano).scaleb(-9)).normalize()


def decimal_to_quotation(value: Decimal) -> tuple[int, int]:
    """Rounds to nine decimals; units and nano get the sign of the value."""
    with localcontext() as context:
        context.prec = PRECISION
        nanos = int((value * NANO).to_integral_value())
    units, nano = divmod(abs(nanos), NANO)
    sign = -1 if nanos < 0 else 1
    return sign * units, sign * nano


def money_from_tinvest(value: MoneyValue) -> Money:
    # T-Invest writes currencies in lower case: 'rub' becomes 'RUB' (§12.2).
    return Money(
        amount=quotation_to_decimal(value.units, value.nano), currency=value.currency.upper()
    )
