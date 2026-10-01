"""User settings (tech.md §6.3); F-02 adds the changes."""

from uuid import UUID

from app.contracts.api.settings import SettingsOut
from app.db.base import UnitOfWork
from app.domains.settings import repo

# The §5.1 column defaults: a user without a row has changed nothing yet.
DEFAULTS = SettingsOut(model_mode="auto", answer_style="concise", default_account=None)


class SettingsService:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def get(self, user_id: UUID) -> SettingsOut:
        async with self._uow as session:
            row = await repo.get(session, user_id)
        return DEFAULTS if row is None else SettingsOut.model_validate(row, from_attributes=True)
