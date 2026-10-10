"""Weights, allocation and currency conversion of a portfolio: the invariants of tech.md §11."""

import itertools
from decimal import Decimal, localcontext

from hypothesis import given
from hypothesis import strategies as st

from app.domains.analytics.portfolio import allocation, fx_convert, weights

NANO = Decimal("1e-9")
# Sums and amounts as T-Invest gives them: nine decimals at most.
positive = st.decimals(min_value=Decimal("1e-9"), max_value=Decimal("1e12"), places=9)
signed = st.decimals(min_value=Decimal("-1e12"), max_value=Decimal("1e12"), places=9)
rates = st.decimals(min_value=Decimal("1e-9"), max_value=Decimal("1e5"), places=9)


def exact_product(a: Decimal, b: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = 80
        return a * b


@given(st.lists(positive, min_size=1, max_size=200))
def test_weights_of_positive_values_are_shares_that_sum_to_one(values: list[Decimal]) -> None:
    found = weights(values)

    assert len(found) == len(values)
    assert all(0 <= w <= 1 for w in found)
    assert abs(sum(found, Decimal(0)) - 1) <= Decimal("1e-9")


@given(
    st.lists(positive, min_size=1, max_size=50),
    st.decimals(min_value=Decimal("0.001"), max_value=Decimal("1000"), places=3),
)
def test_scaling_every_value_keeps_the_weights(values: list[Decimal], factor: Decimal) -> None:
    scaled = weights([v * factor for v in values])

    for before, after in zip(weights(values), scaled, strict=True):
        assert abs(before - after) <= Decimal("1e-25")


@given(st.lists(positive, min_size=2, max_size=50))
def test_a_larger_value_never_gets_a_smaller_weight(values: list[Decimal]) -> None:
    found = weights(values)

    pairs = sorted(zip(values, found, strict=True))
    assert all(a[1] <= b[1] for a, b in itertools.pairwise(pairs))


def test_nothing_and_zeros_have_no_shares() -> None:
    assert weights([]) == []
    assert weights([Decimal(0), Decimal(0)]) == [Decimal(0), Decimal(0)]


@given(st.lists(st.tuples(st.sampled_from(["share", "bond", "etf"]), signed), max_size=100))
def test_allocation_splits_the_total_by_key(items: list[tuple[str, Decimal]]) -> None:
    found = allocation(items, key=lambda item: item[0], value=lambda item: item[1])

    assert sum(found.values(), Decimal(0)) == sum((v for _, v in items), Decimal(0))
    assert list(found) == list(dict.fromkeys(key for key, _ in items))
    for key, total in found.items():
        assert total == sum((v for k, v in items if k == key), Decimal(0))


@given(signed)
def test_a_rate_of_one_keeps_the_value(value: Decimal) -> None:
    assert fx_convert(value, Decimal(1)) == value


@given(signed, rates)
def test_conversion_is_the_product_to_the_nano(value: Decimal, rate: Decimal) -> None:
    found = fx_convert(value, rate)

    assert found == found.quantize(NANO)
    assert abs(found - exact_product(value, rate)) <= NANO / 2


@given(signed, signed, rates)
def test_conversion_keeps_the_order_of_values(a: Decimal, b: Decimal, rate: Decimal) -> None:
    low, high = sorted((a, b))

    assert fx_convert(low, rate) <= fx_convert(high, rate)
