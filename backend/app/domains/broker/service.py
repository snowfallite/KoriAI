"""The broker connection of a user (tech.md §3.5, §6.3): the T-Invest token, checked and sealed,
and the accounts it reaches."""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

import structlog
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.contracts.api.broker import BrokerAccountOut, BrokerConnectionOut
from app.contracts.tinvest import TAccount
from app.core import time
from app.core.crypto import SealedToken, TokenKeyError, open_token, seal_token, token_hint
from app.core.errors import AppError, PermanentGatewayError
from app.db.base import UnitOfWork
from app.db.schema.broker import BrokerConnection
from app.domains.broker import mapping, repo
from app.domains.broker.repo import Ip
from app.gateways.tinvest.port import TInvestPort

log = structlog.get_logger(__name__)

NOT_CONNECTED = BrokerConnectionOut(
    connected=False, status=None, token_hint=None, last_verified_at=None, accounts=[]
)
# Visible ASCII is what the authorization header of gRPC carries; T-Invest tokens run about 90.
TOKEN = re.compile(r"[!-~]{1,512}")
TINVEST = "Т-Инвестиции"  # noqa: RUF001 - the brand starts with a Cyrillic letter
CONNECT = "Подключите брокера в Настройках"
BAD_PASTE = "Токен не подходит: скопируйте токен целиком или выпустите новый"
REFUSED = f"{TINVEST} не приняли токен: скопируйте токен целиком или выпустите новый"
NO_ACCOUNTS = "Токен не открывает ни одного счёта: выпустите токен на все счета"
NOT_READ_ONLY = "Токен даёт не только чтение: нужен доступ «Только чтение»"


@dataclass(frozen=True, slots=True)
class Account:
    alias: str
    name: str
    external_id: str  # the T-Invest account id: it stays in the backend (§3.5)


def read_token(raw: str) -> SecretStr:
    """The token as the user pasted it, without the spaces around it; AppError for a paste that
    can be no token, so it never reaches T-Invest."""
    token = raw.strip()
    if not token:
        raise AppError("validation_error", "Вставьте токен")
    if TOKEN.fullmatch(token) is None:
        raise AppError("token_invalid", BAD_PASTE)
    return SecretStr(token)


async def read_only_accounts(tinvest: TInvestPort, token: SecretStr) -> list[TAccount]:
    """The accounts the token reaches, when it only reads every one of them (§3.5).

    Any other token gets an AppError; so does a token without accounts, which leaves nothing
    to check. A failure of T-Invest itself stays a gateway error.
    """
    try:
        accounts = await tinvest.get_accounts(token)
    except PermanentGatewayError as error:
        if error.code != "token_invalid":
            raise
        raise AppError("token_invalid", REFUSED) from None
    if not accounts:
        raise AppError("token_invalid", NO_ACCOUNTS)
    if any(account.access_level != "read_only" for account in accounts):
        raise AppError("token_not_read_only", NOT_READ_ONLY)
    return accounts


class BrokerService:
    def __init__(
        self, uow: UnitOfWork, settings: Settings, tinvest: TInvestPort | None = None
    ) -> None:
        # Connecting and checking a token need T-Invest; the other domains only read.
        self._uow = uow
        self._settings = settings
        self._tinvest = tinvest

    @property
    def _port(self) -> TInvestPort:
        if self._tinvest is None:
            raise RuntimeError("BrokerService checks tokens only with the T-Invest port")
        return self._tinvest

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

    async def connect(self, user_id: UUID, raw: str, ip: Ip) -> BrokerConnectionOut:
        """Checks a new token with T-Invest and keeps it, sealed, with the accounts it reaches
        (F-01 AC 1-4). A refused token leaves the database as it was."""
        token = read_token(raw)
        accounts = await read_only_accounts(self._port, token)
        keys, key_id = self._settings.TINVEST_TOKEN_KEYS, self._settings.TINVEST_TOKEN_ACTIVE_KEY
        sealed = seal_token(token, user_id, keys, key_id)
        async with self._uow as session:
            replaced = await repo.connection(session, user_id) is not None
            connection_id = await repo.save_connection(
                session, user_id, sealed, token_hint(token), time.now()
            )
            await _sync(session, connection_id, accounts)
            meta: dict[str, object] = {"accounts": len(accounts), "replaced": replaced}
            await repo.add_audit(session, "broker_connected", user_id, ip, meta)
        log.info("broker_connected", accounts=len(accounts), replaced=replaced)
        return await self.connection(user_id)

    async def verify(self, user_id: UUID, ip: Ip) -> BrokerConnectionOut:
        """Asks T-Invest about the stored token again (F-01 AC 5): a refused token turns the
        connection invalid, a good one refreshes the accounts."""
        async with self._uow as session:
            found = await repo.connection(session, user_id)
        if found is None:
            raise AppError("broker_not_connected", CONNECT)
        token = self._open(found)
        try:
            accounts = await read_only_accounts(self._port, token)
        except AppError as refused:
            async with self._uow as session:
                if await repo.set_check(
                    session, found.id, found.token_nonce, "invalid", refused.code, time.now()
                ):
                    meta: dict[str, object] = {"code": refused.code}
                    await repo.add_audit(session, "broker_verify_failed", user_id, ip, meta)
            log.warning("broker_token_refused", code=refused.code)
            return await self.connection(user_id)
        async with self._uow as session:
            if await repo.set_check(
                session, found.id, found.token_nonce, "active", None, time.now()
            ):
                await _sync(session, found.id, accounts)
        return await self.connection(user_id)

    async def disconnect(self, user_id: UUID, ip: Ip) -> None:
        """Drops the token and the accounts (F-01 AC 6); without a connection nothing happens."""
        async with self._uow as session:
            if await repo.delete_connection(session, user_id):
                await repo.add_audit(session, "broker_disconnected", user_id, ip, {})

    async def set_hidden(self, user_id: UUID, alias: str, hidden: bool) -> BrokerAccountOut:
        """A hidden account stays out of the portfolio and the agent (F-01 AC 8)."""
        async with self._uow as session:
            found = await repo.set_hidden(session, user_id, alias, hidden)
        if found is None:
            raise AppError("not_found", "Нет такого счёта")
        return BrokerAccountOut.model_validate(found, from_attributes=True)

    async def get_token(self, user_id: UUID) -> SecretStr:
        """The T-Invest token of the user: no other domain opens it (§8.2)."""
        async with self._uow as session:
            found = await repo.connection(session, user_id)
        if found is None:
            raise AppError("broker_not_connected", CONNECT)
        return self._open(found)

    async def visible_accounts(self, user_id: UUID) -> list[Account]:
        """The accounts the user has not hidden, in alias order (F-01 AC 8)."""
        async with self._uow as session:
            rows = await repo.visible_accounts(session, user_id)
        return [Account(alias=r.alias, name=r.name, external_id=r.external_id) for r in rows]

    def _open(self, found: BrokerConnection) -> SecretStr:
        sealed = SealedToken(found.token_ciphertext, found.token_nonce, found.token_key_id)
        try:
            return open_token(sealed, found.user_id, self._settings.TINVEST_TOKEN_KEYS)
        except TokenKeyError:
            # The key left TINVEST_TOKEN_KEYS: only a new token helps the user.
            log.error("broker_token_unreadable", key_id=found.token_key_id)
            raise AppError(
                "broker_not_connected", "Подключите брокера заново: сохранённый токен не читается"
            ) from None


async def _sync(session: AsyncSession, connection_id: UUID, accounts: Sequence[TAccount]) -> None:
    """Brings the stored accounts to the list of T-Invest (§5.2). An account the token no longer
    reaches turns hidden and keeps its alias: the portfolio and the agent leave it alone."""
    stored = {row.external_id: row for row in await repo.accounts(session, connection_id)}
    found = mapping.aliases({key: row.alias for key, row in stored.items()}, accounts)
    for account in accounts:
        values = mapping.account_values(account)
        row = stored.get(account.id)
        if row is None:
            await repo.add_account(session, connection_id, account.id, found[account.id], values)
        elif changes := {key: value for key, value in values.items() if getattr(row, key) != value}:
            await repo.update_account(session, row.id, changes)
    gone = [row.id for key, row in stored.items() if key not in found and not row.is_hidden]
    await repo.hide_accounts(session, gone)
