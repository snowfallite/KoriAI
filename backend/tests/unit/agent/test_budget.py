"""Pacing of the model quotas on the numbers of tech.md §9.5 and the freemium quotas of §1:
lite 250M, pro 40M, max 25M, ultra 50M tokens for 365 days, pace 1.15, grace 7 days, reserve 1%.
"""

from datetime import date, timedelta

import pytest

from app.contracts.llm import ModelFamily
from app.domains.agent.budget import (
    Pacing,
    allowed,
    lite_equivalent,
    over_daily_cap,
    period_share,
    substitute,
    weights,
)

START = date(2026, 9, 26)
FREEMIUM: dict[ModelFamily, int] = {
    "lite": 250_000_000,
    "pro": 40_000_000,
    "max": 25_000_000,
    "ultra": 50_000_000,
}
PACING = Pacing(
    quotas=FREEMIUM,
    period_start=START,
    period_days=365,
    pace_max=1.15,
    grace_days=7,
    reserve_pct=1,
)
ALL = frozenset(FREEMIUM)


def day(n: int) -> date:
    return START + timedelta(days=n)


def test_a_token_of_each_family_weighs_in_tokens_of_lite() -> None:
    # §9.5: with the freemium quotas lite 1, pro 6.25, max 10, ultra 5.
    assert weights(FREEMIUM) == {"lite": 1, "pro": 6.25, "max": 10, "ultra": 5}


@pytest.mark.parametrize(
    ("today", "share"),
    [
        (day(-30), 7 / 365),  # before the period the grace days still count
        (day(0), 7 / 365),
        (day(3), 7 / 365),
        (day(7), 7 / 365),
        (day(100), 100 / 365),
        (day(365), 1),
    ],
)
def test_the_share_of_the_period_starts_from_the_grace_days(today: date, share: float) -> None:
    assert period_share(PACING, today) == pytest.approx(share)


def test_a_family_ahead_of_its_plan_by_more_than_the_pace_is_refused() -> None:
    # Day 100: the plan of pro is 40M x 100/365 = 10.96M tokens.
    keeps = allowed(PACING, {"pro": 12_000_000}, day(100))  # ratio 1.095
    ahead = allowed(PACING, {"pro": 13_000_000}, day(100))  # ratio 1.186

    assert keeps == ALL
    assert ahead == ALL - {"pro"}


def test_a_family_that_reached_its_reserve_is_refused_even_on_its_plan() -> None:
    # The last day: the plan is the whole quota, the reserve is 1% of 40M = 400k.
    above = allowed(PACING, {"pro": 39_599_999}, day(365))
    at_reserve = allowed(PACING, {"pro": 39_600_000}, day(365))

    assert "pro" in above
    assert "pro" not in at_reserve


def test_a_family_with_no_usage_is_allowed_from_the_first_day() -> None:
    assert allowed(PACING, {}, day(0)) == ALL


@pytest.mark.parametrize(
    ("requested", "free", "answers"),
    [
        ("ultra", ALL, "ultra"),
        ("ultra", {"pro", "lite"}, "pro"),
        ("ultra", {"lite"}, "lite"),
        ("max", {"ultra", "lite"}, "ultra"),
        ("max", {"pro", "lite"}, "pro"),
        ("pro", {"max", "lite"}, "max"),
        ("pro", {"lite"}, "lite"),
        ("pro", {"ultra"}, None),
        ("lite", {"pro", "max"}, "pro"),
        ("lite", {"max", "ultra"}, None),
        ("lite", set(), None),
    ],
)
def test_a_refused_family_gives_way_along_its_chain(
    requested: ModelFamily, free: set[ModelFamily], answers: ModelFamily | None
) -> None:
    # §9.5: ultra -> max -> pro -> lite; max -> ultra -> pro -> lite; pro -> max -> lite;
    # lite -> pro.
    assert substitute(requested, free) == answers


def test_the_spend_of_a_day_counts_in_tokens_of_lite() -> None:
    assert lite_equivalent({"lite": 100_000, "pro": 80_000}, FREEMIUM) == 600_000
    assert lite_equivalent({"max": 1_000, "ultra": 1_000}, FREEMIUM) == 15_000
    assert lite_equivalent({}, FREEMIUM) == 0


def test_the_daily_cap_stops_at_its_value() -> None:
    cap = 600_000

    assert over_daily_cap({"lite": 100_000, "pro": 80_000}, FREEMIUM, cap)
    assert not over_daily_cap({"lite": 599_999}, FREEMIUM, cap)


def test_a_quota_of_zero_switches_its_family_off() -> None:
    # The owner may turn ultra off with LLM_QUOTAS ultra:0 (L-01).
    off = Pacing(
        quotas={**FREEMIUM, "ultra": 0},
        period_start=START,
        period_days=365,
        pace_max=1.15,
        grace_days=7,
        reserve_pct=1,
    )

    assert allowed(off, {}, day(100)) == ALL - {"ultra"}
    assert "ultra" not in weights(off.quotas)
    assert lite_equivalent({"ultra": 1_000, "lite": 10}, off.quotas) == 10
