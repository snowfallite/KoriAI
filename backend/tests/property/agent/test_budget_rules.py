"""Invariants of the quota pacing (tech.md §9.5, §11): more usage never allows more families, a
substitute is always allowed or there is none, the weights are positive with lite at 1, and a
later day never refuses more."""

from datetime import date, timedelta

from hypothesis import given
from hypothesis import strategies as st

from app.contracts.llm import ModelFamily
from app.domains.agent.budget import CHAINS, FAMILIES, Pacing, allowed, substitute, weights

families = st.sampled_from(FAMILIES)
quotas = st.fixed_dictionaries({f: st.integers(1, 10**9) for f in FAMILIES})
spends = st.dictionaries(families, st.integers(0, 2 * 10**9))
days = st.dates(min_value=date(2025, 1, 1), max_value=date(2028, 12, 31))
pacings = st.builds(
    Pacing,
    quotas=quotas,
    period_start=days,
    period_days=st.integers(30, 730),
    pace_max=st.floats(0.5, 3),
    grace_days=st.integers(1, 30),
    reserve_pct=st.floats(0, 50),
)


@given(pacings, spends, spends, days)
def test_more_usage_never_allows_more_families(
    pacing: Pacing, spend: dict[ModelFamily, int], extra: dict[ModelFamily, int], today: date
) -> None:
    more = {f: spend.get(f, 0) + extra.get(f, 0) for f in FAMILIES}

    assert allowed(pacing, more, today) <= allowed(pacing, spend, today)


@given(pacings, spends, days, st.integers(0, 400))
def test_a_later_day_never_refuses_more(
    pacing: Pacing, spend: dict[ModelFamily, int], today: date, later: int
) -> None:
    assert allowed(pacing, spend, today) <= allowed(pacing, spend, today + timedelta(later))


@given(families, st.frozensets(families))
def test_a_substitute_is_the_first_allowed_family_of_the_chain_or_none(
    requested: ModelFamily, free: frozenset[ModelFamily]
) -> None:
    found = substitute(requested, free)

    chain = CHAINS[requested]
    assert chain[0] == requested
    candidates = [f for f in chain if f in free]
    assert found == (candidates[0] if candidates else None)
    assert found is None or found in free


@given(quotas)
def test_weights_are_positive_and_lite_weighs_one(q: dict[ModelFamily, int]) -> None:
    w = weights(q)

    assert set(w) == set(FAMILIES)
    assert all(value > 0 for value in w.values())
    assert w["lite"] == 1
