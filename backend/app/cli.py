"""Command line of the app: python -m app.cli <command> (tech.md §4.1)."""

import argparse
import asyncio
import getpass
import json
import sys
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from uuid import UUID

from pydantic import SecretStr, TypeAdapter
from sqlalchemy import insert, select, text, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, create_async_engine

from app.config import Settings
from app.contracts.api.auth import PASSWORD_MIN_LENGTH
from app.contracts.tinvest import TAccount
from app.core.crypto import SealedToken, TokenKeyError, open_token, seal_token, token_hint
from app.core.errors import AppError
from app.core.security import RateLimiter, hash_password, verify_password
from app.db.base import UnitOfWork
from app.db.schema.base import Base
from app.db.schema.broker import BrokerAccount, BrokerConnection
from app.db.schema.users import User
from app.domains.auth.service import AuthService, normalize_email
from app.gateways.fixtures import SEED, SeedUser, load, seed_users
from app.main import create_app

# §15.2: without SEED_OWNER_PASSWORD the seed users of dev and ci get this public password.
DEV_PASSWORD = "dev-password-123"  # noqa: S105


def openapi(out: Path) -> None:
    # A local .env must not leak into the committed schema.
    schema = create_app(Settings(_env_file=None)).openapi()
    text = json.dumps(schema, ensure_ascii=False, indent=2) + "\n"
    out.write_text(text, encoding="utf-8", newline="\n")


def with_engine[T](action: Callable[[AsyncEngine, Settings], Awaitable[T]]) -> T:
    """Runs a command on the database of the environment and .env."""

    async def run() -> T:
        settings = Settings()
        engine = create_async_engine(settings.DATABASE_URL.get_secret_value())
        try:
            return await action(engine, settings)
        finally:
            await engine.dispose()

    # psycopg's async mode cannot run on the Windows Proactor loop.
    return asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def with_auth[T](action: Callable[[AuthService, Settings], Awaitable[T]]) -> T:
    """Runs an account command."""
    return with_engine(
        lambda engine, settings: action(
            AuthService(UnitOfWork(engine), settings, RateLimiter()), settings
        )
    )


async def print_invites(auth: AuthService, settings: Settings, count: int) -> None:
    for code in await auth.create_invites(count):
        sys.stdout.write(f"{settings.APP_BASE_URL}/register?invite={code}\n")


@dataclass(frozen=True, slots=True)
class Seeded:
    users: list[str]  # addresses
    accounts: list[str]  # aliases of the demo accounts


def seed_password(settings: Settings) -> str:
    password = settings.SEED_OWNER_PASSWORD.get_secret_value()
    if not password:
        if settings.APP_ENV not in {"dev", "ci"}:
            raise AppError(
                "validation_error",
                "Задайте SEED_OWNER_PASSWORD: пароль по умолчанию есть только в dev и ci",
            )
        password = DEV_PASSWORD
    if len(password) < PASSWORD_MIN_LENGTH:
        raise AppError(
            "validation_error", f"SEED_OWNER_PASSWORD не короче {PASSWORD_MIN_LENGTH} символов"
        )
    return password


async def seed(
    bind: AsyncEngine | AsyncConnection, settings: Settings, *, reset: bool = False
) -> Seeded:
    """The users of seed/users.yaml and the broker of the demo (§15.2), upserted by their natural
    keys: a second run changes nothing. `reset` first empties every app table, in dev only."""
    if reset and settings.APP_ENV != "dev":
        raise AppError("forbidden", "seed --reset работает только при APP_ENV=dev")
    password = seed_password(settings)
    users = seed_users()
    emails: list[str] = []
    for user in users:
        email = normalize_email(settings.SEED_OWNER_EMAIL if user.role == "owner" else user.email)
        if email is None:
            raise AppError("validation_error", "Проверьте SEED_OWNER_EMAIL и seed/users.yaml")
        emails.append(email)
    keys_needed = any(user.broker_token is not None for user in users)
    if keys_needed and settings.TINVEST_TOKEN_ACTIVE_KEY not in settings.TINVEST_TOKEN_KEYS:
        raise AppError(
            "validation_error",
            "Задайте TINVEST_TOKEN_KEYS: ключом TINVEST_TOKEN_ACTIVE_KEY сид шифрует токен демо",
        )
    accounts = load(SEED / "tinvest" / "accounts.yaml", TypeAdapter(list[TAccount]))
    aliases: list[str] = []
    async with UnitOfWork(bind) as session:
        if reset:
            tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
            await session.execute(text(f"truncate {tables} restart identity cascade"))
        for user, email in zip(users, emails, strict=True):
            user_id = await _upsert_user(session, email, user, password)
            if user.broker_token is not None:
                connection_id = await _connect_broker(session, user_id, user.broker_token, settings)
                aliases = await _upsert_accounts(session, connection_id, accounts)
    return Seeded(users=emails, accounts=aliases)


async def _upsert_user(session: AsyncSession, email: str, user: SeedUser, password: str) -> UUID:
    found = await session.scalar(select(User).where(User.email == email))
    # argon2 salts every hash: keep the stored one while the password still matches it.
    if found is not None and await asyncio.to_thread(
        verify_password, found.password_hash, password
    ):
        password_hash = found.password_hash
    else:
        password_hash = await asyncio.to_thread(hash_password, password)
    values = {
        "password_hash": password_hash,
        "display_name": user.display_name,
        "role": user.role,
        "status": "active",
    }
    if found is None:
        added = await session.execute(insert(User).values(email=email, **values).returning(User.id))
        return added.scalar_one()
    if changes := {k: v for k, v in values.items() if getattr(found, k) != v}:
        await session.execute(update(User).where(User.id == found.id).values(**changes))
    return found.id


def _holds(found: BrokerConnection, user_id: UUID, token: SecretStr, settings: Settings) -> bool:
    """The stored token opens with the keys of the settings and is this token."""
    sealed = SealedToken(found.token_ciphertext, found.token_nonce, found.token_key_id)
    try:
        opened = open_token(sealed, user_id, settings.TINVEST_TOKEN_KEYS)
    except TokenKeyError:
        return False
    return opened.get_secret_value() == token.get_secret_value()


async def _connect_broker(
    session: AsyncSession, user_id: UUID, token: SecretStr, settings: Settings
) -> UUID:
    found = await session.scalar(
        select(BrokerConnection).where(
            BrokerConnection.user_id == user_id, BrokerConnection.broker == "tinvest"
        )
    )
    values: dict[str, object] = {
        "token_hint": token_hint(token),
        "status": "active",
        "last_error_code": None,
    }
    # AES-GCM takes a fresh nonce each time: seal again only when the stored token is lost.
    if found is None or not _holds(found, user_id, token, settings):
        sealed = seal_token(
            token, user_id, settings.TINVEST_TOKEN_KEYS, settings.TINVEST_TOKEN_ACTIVE_KEY
        )
        values |= {
            "token_ciphertext": sealed.ciphertext,
            "token_nonce": sealed.nonce,
            "token_key_id": sealed.key_id,
        }
    if found is None:
        added = await session.execute(
            insert(BrokerConnection)
            .values(user_id=user_id, **values)
            .returning(BrokerConnection.id)
        )
        return added.scalar_one()
    if changes := {k: v for k, v in values.items() if getattr(found, k) != v}:
        await session.execute(
            update(BrokerConnection).where(BrokerConnection.id == found.id).values(**changes)
        )
    return found.id


async def _upsert_accounts(
    session: AsyncSession, connection_id: UUID, accounts: list[TAccount]
) -> list[str]:
    rows = await session.scalars(
        select(BrokerAccount).where(BrokerAccount.connection_id == connection_id)
    )
    known = {row.external_id: row for row in rows}
    # §5.2: aliases go by the opening day; a new account takes the next free number.
    number = max((int(row.alias.removeprefix("acc")) for row in known.values()), default=0)
    aliases = []
    for account in sorted(accounts, key=lambda a: (a.opened_date or date.max, a.id)):
        values: dict[str, object] = {
            "name": account.name,
            "type": account.type,
            "status": account.status,
            "opened_at": account.opened_date,
            "access_level": account.access_level,
            "is_hidden": False,
        }
        row = known.get(account.id)
        if row is None:
            number += 1
            alias = f"acc{number}"
            await session.execute(
                insert(BrokerAccount).values(
                    connection_id=connection_id, external_id=account.id, alias=alias, **values
                )
            )
        else:
            alias = row.alias
            if changes := {k: v for k, v in values.items() if getattr(row, k) != v}:
                await session.execute(
                    update(BrokerAccount).where(BrokerAccount.id == row.id).values(**changes)
                )
        aliases.append(alias)
    return aliases


async def print_seed(engine: AsyncEngine, settings: Settings, reset: bool) -> None:
    seeded = await seed(engine, settings, reset=reset)
    sys.stdout.write(
        f"Seed users: {', '.join(seeded.users)}; the demo accounts: {', '.join(seeded.accounts)}\n"
    )


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    gen = commands.add_parser("openapi", help="write the OpenAPI schema (just gen)")
    gen.add_argument("out", type=Path)
    invites = commands.add_parser("invites", help="registration invites (just invites <n>)")
    actions = invites.add_subparsers(dest="action", required=True)
    create = actions.add_parser("create", help="print links with new invite codes")
    create.add_argument("--count", type=int, default=1)
    owner = commands.add_parser(
        "create-owner", help="create the owner or make a user the owner; asks for the password"
    )
    owner.add_argument("--email", required=True)
    seeder = commands.add_parser(
        "seed", help="the seed users and the demo broker (just seed); a rerun changes nothing"
    )
    seeder.add_argument("--reset", action="store_true", help="empty every app table first (dev)")
    args = parser.parse_args(argv)

    try:
        if args.command == "openapi":
            openapi(args.out)
        elif args.command == "invites":
            if args.count < 1:
                parser.error("--count must be positive")
            with_auth(lambda auth, settings: print_invites(auth, settings, args.count))
        elif args.command == "seed":
            with_engine(lambda engine, settings: print_seed(engine, settings, args.reset))
        else:
            password = getpass.getpass("Password: ")
            if getpass.getpass("Repeat the password: ") != password:
                parser.exit(1, "The passwords differ\n")
            with_auth(lambda auth, _: auth.create_owner(args.email, password))
    except AppError as error:
        parser.exit(1, f"{error.message}\n")


if __name__ == "__main__":
    main()
