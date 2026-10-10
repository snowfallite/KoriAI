"""The broker connection of a user (tech.md §6.3); F-01 adds connecting and checking the token."""

from dataclasses import dataclass
from uuid import UUID

import structlog
from pydantic import SecretStr

from app.config import Settings
from app.contracts.api.broker import BrokerConnectionOut
from app.core.crypto import SealedToken, TokenKeyError, open_token
from app.core.errors import AppError
from app.db.base import UnitOfWork
from app.domains.broker import repo

log = structlog.get_logger(__name__)

NOT_CONNECTED = BrokerConnectionOut(
    connected=False, status=None, token_hint=None, last_verified_at=None, accounts=[]
)


@dataclass(frozen=True, slots=True)
class Account:
    alias: str
    name: str
    external_id: str  # the T-Invest account id: it stays in the backend (§3.5)


class BrokerService:
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._settings = settings

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

    async def get_token(self, user_id: UUID) -> SecretStr:
        """The T-Invest token of the user: no other domain opens it (§8.2)."""
        async with self._uow as session:
            found = await repo.connection(session, user_id)
        if found is None:
            raise AppError("broker_not_connected", "Подключите брокера в Настройках")
        sealed = SealedToken(found.token_ciphertext, found.token_nonce, found.token_key_id)
        try:
            return open_token(sealed, user_id, self._settings.TINVEST_TOKEN_KEYS)
        except TokenKeyError:
            # The key left TINVEST_TOKEN_KEYS: only a new token helps the user.
            log.error("broker_token_unreadable", key_id=found.token_key_id)
            raise AppError(
                "broker_not_connected", "Подключите брокера заново: сохранённый токен не читается"
            ) from None

    async def visible_accounts(self, user_id: UUID) -> list[Account]:
        """The accounts the user has not hidden, in alias order (F-01 AC 8)."""
        async with self._uow as session:
            rows = await repo.visible_accounts(session, user_id)
        return [Account(alias=r.alias, name=r.name, external_id=r.external_id) for r in rows]
