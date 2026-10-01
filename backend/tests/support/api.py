"""HTTP contract fixtures (tech.md §14.3): the app on a migrated scratch Postgres, a transaction
per test rolled back at its end. tests/conftest.py loads them as a plugin."""

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator

import httpx
import pytest
from alembic import command
from fastapi import FastAPI

from app.config import Settings
from app.db.base import UnitOfWork
from app.domains.auth.service import AuthService
from app.main import create_app
from tests.support.db import alembic_config, scratch_database

# The default of APP_ALLOWED_ORIGINS. A browser sends Origin with every POST, and the API takes
# mutations only as JSON (§3.5), so every test client sends both.
ORIGIN = "http://localhost:5173"
HEADERS = {"Origin": ORIGIN, "Content-Type": "application/json"}
PASSWORD = "correct-horse-1"


async def sign_up(api: httpx.AsyncClient, invite: str | None = None) -> None:
    """Registers a new user; the client keeps the session cookie."""
    body = {
        "email": f"{uuid.uuid4().hex}@example.test",
        "password": PASSWORD,
        "invite_code": invite,
        "display_name": None,
    }
    reply = await api.post("/api/auth/register", json=body)
    assert reply.status_code == 201, reply.text


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    with scratch_database() as url:
        command.upgrade(alembic_config(url), "head")
        yield url


@pytest.fixture
async def app(database_url: str) -> AsyncIterator[FastAPI]:
    """Tests change app.state.settings with model_copy(update=...) to try other config.

    No workers: they would run jobs on the shared connection; tests/integration/jobs runs them.
    """
    app = create_app(Settings(_env_file=None, DATABASE_URL=database_url, JOBS_ENABLED=False))
    async with app.router.lifespan_context(app):
        engine = app.state.engine
        async with engine.connect() as conn:
            transaction = await conn.begin()
            # Every UnitOfWork of the test joins this transaction through savepoints, and tests
            # read and seed rows through app.state.engine too.
            app.state.engine = conn
            try:
                yield app
            finally:
                app.state.engine = engine
                await transaction.rollback()


@pytest.fixture
def new_client(app: FastAPI) -> Callable[[], httpx.AsyncClient]:
    """Another browser of the same app: `async with new_client() as phone:`."""

    def client() -> httpx.AsyncClient:
        transport = httpx.ASGITransport(app=app)
        return httpx.AsyncClient(transport=transport, base_url="http://test", headers=HEADERS)

    return client


@pytest.fixture
async def api(new_client: Callable[[], httpx.AsyncClient]) -> AsyncIterator[httpx.AsyncClient]:
    async with new_client() as client:
        yield client


@pytest.fixture
async def user_api(
    api: httpx.AsyncClient, make_invite: Callable[[], Awaitable[str]]
) -> httpx.AsyncClient:
    """The api client signed in as a new user."""
    await sign_up(api, await make_invite())
    return api


@pytest.fixture
def make_invite(app: FastAPI) -> Callable[[], Awaitable[str]]:
    async def make() -> str:
        service = AuthService(UnitOfWork(app.state.engine), app.state.settings, app.state.limiter)
        [code] = await service.create_invites(1)
        return code

    return make
