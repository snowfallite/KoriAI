"""Pacing of the model quotas (tech.md §9.5): pure functions of numbers, no IO.

A family stays allowed while the service spends it no faster than the plan of the quota period
allows and leaves its reserve. A refused family gives way along its chain. The usage U_f is the
sum of the usage_daily rows of the service (user_id null) since the start of the period.
"""

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Self

from app.config import Settings
from app.contracts.llm import ModelFamily

FAMILIES: tuple[ModelFamily, ...] = ("lite", "pro", "max", "ultra")
# The first allowed family of the chain answers instead of the requested one.
CHAINS: Mapping[ModelFamily, tuple[ModelFamily, ...]] = {
    "ultra": ("ultra", "max", "pro", "lite"),
    "max": ("max", "ultra", "pro", "lite"),
    "pro": ("pro", "max", "lite"),
    "lite": ("lite", "pro"),
}

type Spend = Mapping[ModelFamily, int]  # billable tokens by family


@dataclass(frozen=True, slots=True)
class Pacing:
    quotas: Mapping[ModelFamily, int]
    period_start: date
    period_days: int
    pace_max: float
    grace_days: int
    reserve_pct: float

    @classmethod
    def of(cls, settings: Settings) -> Self:
        return cls(
            quotas=settings.LLM_QUOTAS,
            period_start=settings.LLM_QUOTA_PERIOD_START,
            period_days=settings.LLM_QUOTA_PERIOD_DAYS,
            pace_max=settings.LLM_PACE_MAX,
            grace_days=settings.LLM_PACE_GRACE_DAYS,
            reserve_pct=settings.LLM_RESERVE_PCT,
        )


def period_share(pacing: Pacing, today: date) -> float:
    """e: the share of the period behind, at least the grace days, so the first days of a period
    do not refuse a family for a handful of questions."""
    elapsed = (today - pacing.period_start).days
    return max(elapsed, pacing.grace_days) / pacing.period_days


def pace_ratio(used: int, quota: int, share: float) -> float:
    """U_f / (Q_f * e): 1 keeps to the plan."""
    return used / (quota * share)


def allowed(pacing: Pacing, spend: Spend, today: date) -> frozenset[ModelFamily]:
    share = period_share(pacing, today)
    return frozenset(f for f in FAMILIES if _fits(pacing, f, spend.get(f, 0), share))


def _fits(pacing: Pacing, family: ModelFamily, used: int, share: float) -> bool:
    quota = pacing.quotas[family]
    reserve = quota * pacing.reserve_pct / 100
    return pace_ratio(used, quota, share) <= pacing.pace_max and quota - used > reserve


def substitute(requested: ModelFamily, free: Collection[ModelFamily]) -> ModelFamily | None:
    """The first allowed family of the chain; None means llm_quota_exhausted."""
    return next((family for family in CHAINS[requested] if family in free), None)


def weights(quotas: Mapping[ModelFamily, int]) -> dict[ModelFamily, float]:
    """w_f = Q_lite / Q_f: what a token of a family costs in tokens of lite."""
    return {family: quotas["lite"] / quotas[family] for family in FAMILIES}


def lite_equivalent(spend: Spend, quotas: Mapping[ModelFamily, int]) -> float:
    w = weights(quotas)
    return sum(amount * w[family] for family, amount in spend.items())


def over_daily_cap(spend: Spend, quotas: Mapping[ModelFamily, int], cap: int) -> bool:
    """A user's day against USER_DAILY_BUDGET_LITE_EQ, or the background day against
    BACKGROUND_DAILY_BUDGET_LITE_EQ."""
    return lite_equivalent(spend, quotas) >= cap
