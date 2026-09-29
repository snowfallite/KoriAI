"""Usage DTOs: LLM quotas and web credits (tech.md §6.3, §9.5)."""

from datetime import date

from app.contracts.common import Contract
from app.contracts.llm import ModelFamily


class FamilyUsageOut(Contract):
    family: ModelFamily
    model_id: str
    quota: int
    used: int
    pace_ratio: float
    allowed: bool


class WebUsageOut(Contract):
    monthly_quota: int
    used_this_month: int


class MyUsageOut(Contract):
    today_lite_eq: int
    daily_cap_lite_eq: int | None  # null for the owner
    today_web_credits: int
    web_daily_cap: int | None


class UsageOut(Contract):
    period_start: date
    period_end: date
    families: list[FamilyUsageOut]
    web: WebUsageOut
    me: MyUsageOut
