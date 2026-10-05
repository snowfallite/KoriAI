"""cli seed on a real Postgres (S1-10 AC 1, tech.md §15.2, §15.4): two runs leave the same
database, a run brings back what the seed users changed, --reset wipes the tables in dev only,
and a run without the settings it needs refuses."""

import asyncio
import base64
from collections.abc import AsyncIterator, Iterator
from datetime import date
from pathlib import Path

import pytest
from alembic import command
from pydantic import TypeAdapter
from sqlalchemy import func, insert, select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app import cli
from app.config import Settings
from app.contracts.tinvest import TAccount
from app.core.crypto import SealedToken, open_token
from app.core.security import hash_password, verify_password
from app.db.base import UnitOfWork
from app.db.schema.base import Base
from app.db.schema.broker import BrokerAccount, BrokerConnection
from app.db.schema.chat import Thread
from app.db.schema.users import User
from app.gateways.fixtures import SEED, read_yaml, seed_users
from tests.support.db import alembic_config, scratch_database
from tests.support.jobs import run_twice, snapshot

DEV_PASSWORD = "dev-password-123"  # §15.2
TABLES = [table.name for table in Base.metadata.sorted_tables]


def key_pair(key_id: str, fill: int) -> str:
    return f"{key_id}:{base64.b64encode(bytes([fill]) * 32).decode()}"


def seed_emails() -> set[str]:
    return {user.email for user in seed_users()}


def demo_email() -> str:
    [demo] = [user.email for user in seed_users() if user.broker_token is not None]
    return demo


@pytest.fixture(scope="module")
def database_url() -> Iterator[str]:
    with scratch_database() as url:
        command.upgrade(alembic_config(url), "head")
        yield url


@pytest.fixture
async def engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:  # every test starts from empty tables
        await conn.execute(text(f"truncate {', '.join(TABLES)} restart identity cascade"))
    yield engine
    await engine.dispose()


@pytest.fixture(autouse=True)
def _environment(database_url: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)  # away from a local .env
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("TINVEST_TOKEN_KEYS", key_pair("k1", 1))


async def run(*argv: str) -> None:
    # The command starts its own event loop.
    await asyncio.to_thread(cli.main, ["seed", *argv])


async def users(engine: AsyncEngine) -> dict[str, User]:
    async with UnitOfWork(engine) as session:
        return {user.email: user for user in (await session.scalars(select(User))).all()}


async def broker(engine: AsyncEngine) -> tuple[BrokerConnection, list[BrokerAccount]]:
    async with UnitOfWork(engine) as session:
        connection = (await session.scalars(select(BrokerConnection))).one()
        accounts = await session.scalars(select(BrokerAccount).order_by(BrokerAccount.alias))
        return connection, list(accounts)


async def stored_token(engine: AsyncEngine) -> SealedToken:
    connection, _ = await broker(engine)
    return SealedToken(connection.token_ciphertext, connection.token_nonce, connection.token_key_id)


async def test_two_seeds_in_a_row_leave_the_same_database(engine: AsyncEngine) -> None:
    first = await run_twice(run, engine, *TABLES)

    assert {row.email for row in first["users"]} == seed_emails()
    assert [row.alias for row in sorted(first["broker_accounts"], key=lambda r: r.alias)] == [
        "acc1",
        "acc2",
    ]


async def test_a_seed_brings_back_what_the_seed_users_changed(engine: AsyncEngine) -> None:
    await run()
    demo = demo_email()
    async with engine.begin() as conn:
        changed = {"display_name": "Другое имя", "status": "disabled"}
        await conn.execute(
            update(User)
            .where(User.email == demo)
            .values(password_hash=hash_password("another-password-1"), **changed)
        )
        await conn.execute(update(BrokerConnection).values(status="invalid", last_error_code="x"))
        await conn.execute(
            update(BrokerAccount)
            .where(BrokerAccount.alias == "acc2")
            .values(name="Старое имя", is_hidden=True)
        )
    token = await stored_token(engine)

    await run()

    found = (await users(engine))[demo]
    [expected] = [user for user in seed_users() if user.email == demo]
    assert verify_password(found.password_hash, DEV_PASSWORD)
    assert (found.display_name, found.status) == (expected.display_name, "active")
    connection, accounts = await broker(engine)
    assert (connection.status, connection.last_error_code) == ("active", None)
    assert await stored_token(engine) == token  # the token still opened: no new seal
    by_opening = sorted(
        TypeAdapter(list[TAccount]).validate_python(read_yaml(SEED / "tinvest" / "accounts.yaml")),
        key=lambda account: account.opened_date or date.max,
    )
    assert [(a.alias, a.name, a.is_hidden) for a in accounts] == [
        (f"acc{n}", account.name, False) for n, account in enumerate(by_opening, 1)
    ]


async def test_a_seed_reseals_the_token_the_keys_no_longer_open(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    await run()
    monkeypatch.setenv("TINVEST_TOKEN_KEYS", key_pair("k2", 2))
    monkeypatch.setenv("TINVEST_TOKEN_ACTIVE_KEY", "k2")

    await run()

    sealed = await stored_token(engine)
    demo = (await users(engine))[demo_email()]
    keys = Settings(_env_file=None, TINVEST_TOKEN_KEYS=key_pair("k2", 2)).TINVEST_TOKEN_KEYS
    [expected] = [user.broker_token for user in seed_users() if user.broker_token is not None]
    assert sealed.key_id == "k2"
    assert open_token(sealed, demo.id, keys).get_secret_value() == expected.get_secret_value()


async def test_reset_wipes_every_table_back_to_the_seed(engine: AsyncEngine) -> None:
    await run()
    async with engine.begin() as conn:
        stranger = await conn.scalar(
            insert(User).values(email="stranger@example.test", password_hash="x").returning(User.id)
        )
        await conn.execute(insert(Thread).values(user_id=stranger, title="Чужой тред"))

    await run("--reset")

    assert set(await users(engine)) == seed_emails()
    async with engine.connect() as conn:
        assert await conn.scalar(select(func.count()).select_from(Thread)) == 0


@pytest.mark.parametrize("app_env", ["ci", "staging", "prod"])
async def test_reset_is_refused_outside_dev(
    app_env: str,
    engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("SEED_OWNER_PASSWORD", "staging-password-1")
    await run()
    before = await snapshot(engine, TABLES)
    monkeypatch.setenv("APP_ENV", app_env)
    # The settings of staging and prod demand what a VPS has.
    monkeypatch.setenv("COOKIE_SECURE", "true")
    if app_env == "prod":  # every client on its real adapter (memory is the fake of Qdrant)
        for name, field in Settings.model_fields.items():
            if field.default in ("fake", "memory"):
                monkeypatch.setenv(name, "qdrant" if field.default == "memory" else "real")

    with pytest.raises(SystemExit) as stop:
        await run("--reset")

    assert stop.value.code == 1
    assert "APP_ENV=dev" in capsys.readouterr().err
    assert await snapshot(engine, TABLES) == before


async def test_staging_takes_the_password_of_its_settings_only(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("COOKIE_SECURE", "true")

    with pytest.raises(SystemExit) as stop:
        await run()

    assert stop.value.code == 1
    assert "SEED_OWNER_PASSWORD" in capsys.readouterr().err
    assert await users(engine) == {}

    monkeypatch.setenv("SEED_OWNER_PASSWORD", "staging-password-1")
    await run()

    found = await users(engine)
    assert set(found) == seed_emails()
    assert all(verify_password(user.password_hash, "staging-password-1") for user in found.values())


async def test_the_owner_takes_the_address_of_seed_owner_email(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SEED_OWNER_EMAIL", " Boss@Example.TEST ")

    await run()

    found = await users(engine)
    assert {email: user.role for email, user in found.items()} == {
        "boss@example.test": "owner",
        demo_email(): "user",
    }
