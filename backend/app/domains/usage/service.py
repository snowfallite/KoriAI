"""Spend of the models (tech.md §9.5): billable tokens by family for the quota period of the
service, a Moscow day of a user and a Moscow day of the background jobs. F-06 adds GET /api/usage
on top."""

from datetime import date, datetime
from uuid import UUID

from app.contracts.llm import ModelFamily
from app.core import time
from app.db.base import UnitOfWork
from app.domains.usage import repo


class UsageService:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def service_period(self, start: date) -> dict[ModelFamily, int]:
        """U_f: the usage of the whole service since the start of the quota period."""
        async with self._uow as session:
            return await repo.service_since(session, start)

    async def user_day(self, user_id: UUID, day: date) -> dict[ModelFamily, int]:
        async with self._uow as session:
            return await repo.user_day(session, user_id, day)

    async def background_day(self, day: date) -> dict[ModelFamily, int]:
        midnight = datetime.combine(day, datetime.min.time(), tzinfo=time.MSK)
        async with self._uow as session:
            return await repo.background_since(session, midnight)
