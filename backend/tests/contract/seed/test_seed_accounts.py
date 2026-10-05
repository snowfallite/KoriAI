"""The seed users (S1-10 AC 2-4, tech.md §15.2): the owner and the demo sign in with the seed
password; the demo has a broker connection with the made-up token, sealed for the demo only,
and the two accounts of the fake, whose portfolios are the seed files."""

from collections.abc import Callable
from datetime import date
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretBytes, SecretStr, TypeAdapter
from sqlalchemy import select

from app.cli import seed
from app.config import Settings
from app.contracts.api.auth import MeOut, UserOut
from app.contracts.tinvest import TAccount, TPortfolio
from app.core.crypto import SealedToken, TokenKeyError, open_token
from app.core.errors import AppError
from app.db.base import UnitOfWork
from app.db.schema.broker import BrokerAccount, BrokerConnection
from app.db.schema.users import User
from app.gateways.factory import Gateways
from app.gateways.fixtures import SEED, SeedUser, read_yaml, seed_users

DEV_PASSWORD = "dev-password-123"  # §15.2: the password of the seed users in dev and ci
KEYS = {"k1": SecretBytes(bytes(range(32)))}


@pytest.fixture
def settings(app: FastAPI) -> Settings:
    """The app of the test with a token key: the seed seals the demo token with it."""
    found: Settings = app.state.settings.model_copy(update={"TINVEST_TOKEN_KEYS": KEYS})
    app.state.settings = found
    return found


@pytest.fixture
async def seeded(app: FastAPI, settings: Settings) -> None:
    await seed(app.state.engine, settings)


def the(role: str) -> SeedUser:
    [user] = [user for user in seed_users() if user.role == role]
    return user


def demo_token() -> SecretStr:
    token = the("user").broker_token
    assert token is not None
    return token


async def sign_in(client: httpx.AsyncClient, email: str) -> UserOut:
    reply = await client.post("/api/auth/login", json={"email": email, "password": DEV_PASSWORD})
    assert reply.status_code == 200, reply.text
    return UserOut.model_validate(reply.json())


async def user_id(app: FastAPI, email: str) -> UUID | None:
    async with UnitOfWork(app.state.engine) as session:
        found: UUID | None = await session.scalar(select(User.id).where(User.email == email))
    return found


async def stored_token(app: FastAPI, owner: UUID) -> tuple[UUID, SealedToken]:
    """The connection id and the sealed token of a user's broker connection."""
    query = select(
        BrokerConnection.id,
        BrokerConnection.token_ciphertext,
        BrokerConnection.token_nonce,
        BrokerConnection.token_key_id,
    ).where(BrokerConnection.user_id == owner)
    async with UnitOfWork(app.state.engine) as session:
        row = (await session.execute(query)).one()
    return row.id, SealedToken(row.token_ciphertext, row.token_nonce, row.token_key_id)


@pytest.mark.usefixtures("seeded")
@pytest.mark.parametrize("role", ["owner", "user"])
async def test_the_seed_users_sign_in_with_the_seed_password(
    role: str, new_client: Callable[[], httpx.AsyncClient]
) -> None:
    user = the(role)

    async with new_client() as client:
        found = await sign_in(client, user.email)

    assert (found.email, found.role, found.display_name) == (user.email, role, user.display_name)


@pytest.mark.usefixtures("seeded")
async def test_the_demo_has_a_broker_with_both_accounts_of_the_seed(api: httpx.AsyncClient) -> None:
    accounts = TypeAdapter(list[TAccount]).validate_python(
        read_yaml(SEED / "tinvest" / "accounts.yaml")
    )
    # Aliases go by the opening day (§5.2).
    by_opening = sorted(accounts, key=lambda account: account.opened_date or date.max)

    await sign_in(api, the("user").email)
    me = MeOut.model_validate((await api.get("/api/auth/me")).json())

    assert me.broker.connected
    assert me.broker.status == "active"
    assert me.broker.token_hint == demo_token().get_secret_value()[-4:]
    assert [(a.alias, a.name, a.type, a.opened_at, a.is_hidden) for a in me.broker.accounts] == [
        (f"acc{n}", a.name, a.type, a.opened_date, False) for n, a in enumerate(by_opening, 1)
    ]


@pytest.mark.usefixtures("seeded")
async def test_the_owner_has_no_broker(api: httpx.AsyncClient) -> None:
    await sign_in(api, the("owner").email)

    me = MeOut.model_validate((await api.get("/api/auth/me")).json())

    assert not me.broker.connected


@pytest.mark.usefixtures("seeded")
async def test_the_stored_token_opens_for_the_demo_only(app: FastAPI) -> None:
    demo_id = await user_id(app, the("user").email)
    owner_id = await user_id(app, the("owner").email)
    assert demo_id is not None and owner_id is not None
    _, sealed = await stored_token(app, demo_id)

    assert demo_token().get_secret_value().encode() not in sealed.ciphertext
    assert open_token(sealed, demo_id, KEYS).get_secret_value() == (demo_token().get_secret_value())
    with pytest.raises(TokenKeyError):
        open_token(sealed, owner_id, KEYS)


@pytest.mark.usefixtures("seeded")
async def test_the_fake_gives_the_demo_accounts_the_seed_portfolios(app: FastAPI) -> None:
    demo_id = await user_id(app, the("user").email)
    assert demo_id is not None
    connection_id, sealed = await stored_token(app, demo_id)
    token = open_token(sealed, demo_id, KEYS)
    query = select(BrokerAccount.external_id).where(BrokerAccount.connection_id == connection_id)
    async with UnitOfWork(app.state.engine) as session:
        external_ids = (await session.scalars(query)).all()
    gateways: Gateways = app.state.gateways

    assert len(external_ids) == 2
    for external_id in external_ids:
        expected = TPortfolio.model_validate(
            read_yaml(SEED / "tinvest" / "portfolios" / f"{external_id}.yaml")
        )
        assert await gateways.tinvest.get_portfolio(token, external_id) == expected


async def test_without_a_token_key_the_seed_refuses_before_any_write(app: FastAPI) -> None:
    with pytest.raises(AppError) as refused:
        await seed(app.state.engine, app.state.settings)

    assert "TINVEST_TOKEN_KEYS" in refused.value.message
    for user in seed_users():  # the refusal comes before the first write
        assert await user_id(app, user.email) is None
