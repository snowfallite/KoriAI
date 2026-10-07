"""Weights, allocation and currency conversion of a portfolio (tech.md §11): pure functions."""

from collections.abc import Callable, Iterable, Sequence
from decimal import Decimal, localcontext

NANO = Decimal("1e-9")  # the step of T-Invest sums
# Nine decimals of an int64 times a rate with nine decimals: wider than the default 28 digits.
PRECISION = 40


def weights(values: Sequence[Decimal]) -> list[Decimal]:
    """Each value's share of their sum; zeros when the sum is zero."""
    total = sum(values, Decimal(0))
    if total == 0:
        return [Decimal(0) for _ in values]
    return [value / total for value in values]


def allocation[P, K](
    positions: Iterable[P], key: Callable[[P], K], value: Callable[[P], Decimal]
) -> dict[K, Decimal]:
    """The sum of the values per key; keys keep the order they first come in."""
    sums: dict[K, Decimal] = {}
    for position in positions:
        group = key(position)
        sums[group] = sums.get(group, Decimal(0)) + value(position)
    return sums


def fx_convert(value: Decimal, rate: Decimal) -> Decimal:
    """The value at `rate` units of another currency per unit, rounded to the nano."""
    with localcontext() as context:
        context.prec = PRECISION
        return (value * rate).quantize(NANO)
