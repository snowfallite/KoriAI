"""The broker connection of a user (tech.md §6.3); S1-11 and F-01 add the token and accounts."""

from uuid import UUID

from app.contracts.api.broker import BrokerConnectionOut
from app.db.base import UnitOfWork
from app.domains.broker import repo

NOT_CONNECTED = BrokerConnectionOut(
    connected=False, status=None, token_hint=None, last_verified_at=None, accounts=[]
)


class BrokerService:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def connection(self, user_id: UUID) -> BrokerConnectionOut:
        async with self._uow as session:
            found = await repo.connection(session, user_id)
            accounts = await repo.accounts(session, found.id) if found else []
        if found is None:
            return NOT_CONNECTED
        out = {
            "connected": True,
            "status": found.status,
            "token_hint": found.token_hint,
            "last_verified_at": found.last_verified_at,
            "accounts": accounts,
        }
        return BrokerConnectionOut.model_validate(out, from_attributes=True)
