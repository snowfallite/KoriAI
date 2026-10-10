"""The seed in contract tests (tech.md §15.2): the users of seed/users.yaml and the demo broker in
the test transaction, and a client signed in as the demo. tests/conftest.py loads it as a plugin."""

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretBytes

from app.cli import seed
from app.gateways.fixtures import SeedUser, seed_users

# §15.2: the password of the seed users in dev and ci.
SEED_PASSWORD = "dev-password-123"
# The seed seals the demo token with the active key k1; the app opens it with the same key.
TOKEN_KEYS = {"k1": SecretBytes(bytes(range(32)))}


def seed_user(role: str) -> SeedUser:
    [user] = [user for user in seed_users() if user.role == role]
    return user


async def sign_in(client: httpx.AsyncClient, email: str) -> None:
    reply = await client.post("/api/auth/login", json={"email": email, "password": SEED_PASSWORD})
    assert reply.status_code == 200, reply.text


@pytest.fixture
async def seeded(app: FastAPI) -> None:
    """Runs cli seed on the test transaction with a token key the app knows too."""
    app.state.settings = app.state.settings.model_copy(update={"TINVEST_TOKEN_KEYS": TOKEN_KEYS})
    await seed(app.state.engine, app.state.settings)


@pytest.fixture
async def demo_api(api: httpx.AsyncClient, seeded: None) -> httpx.AsyncClient:
    """The api client signed in as the seed demo: the broker of the fake with acc1 and acc2."""
    await sign_in(api, seed_user("user").email)
    return api
