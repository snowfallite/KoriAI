"""HTTP contract of the skeleton: health, request id, ErrorOut (S1-02 AC 1 and 5, tech.md §6)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, get_args

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

from app.config import Settings
from app.contracts.api.health import HealthOut, ReadyOut
from app.contracts.common import ErrorCode, ErrorOut
from app.core.errors import AppError
from app.http.errors import STATUS
from app.main import create_app
from tests.support.db import scratch_database

CLOSED = "127.0.0.1:1"  # nothing listens on port 1


def make_app(**overrides: Any) -> FastAPI:
    return create_app(Settings(_env_file=None, **{"JOBS_ENABLED": False, **overrides}))


@asynccontextmanager
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with app.router.lifespan_context(app):
        # The middleware answers unhandled errors; let the client see that answer.
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as api:
            yield api


async def test_health_is_ok() -> None:
    async with client(make_app()) as api:
        reply = await api.get("/api/health")

    assert reply.status_code == 200
    assert HealthOut.model_validate(reply.json()) == HealthOut(status="ok")
    assert reply.headers["X-Request-Id"]


async def test_ready_with_database(database_url: str) -> None:
    async with client(make_app(DATABASE_URL=database_url)) as api:
        reply = await api.get("/api/health/ready")

    assert reply.status_code == 200, reply.text
    ready = ReadyOut.model_validate(reply.json())
    assert (ready.db, ready.qdrant, ready.queue) == (True, True, True)
    assert ready.llm_gate.capacity == 1


async def test_ready_is_503_without_database() -> None:
    app = make_app(DATABASE_URL=f"postgresql+psycopg://app:app@{CLOSED}/app")

    async with client(app) as api:
        reply = await api.get("/api/health/ready")

    assert reply.status_code == 503
    assert ReadyOut.model_validate(reply.json()).db is False


async def test_ready_is_503_without_the_queue_schema() -> None:
    with scratch_database() as url:  # not migrated
        async with client(make_app(DATABASE_URL=url)) as api:
            reply = await api.get("/api/health/ready")

    assert reply.status_code == 503
    ready = ReadyOut.model_validate(reply.json())
    assert (ready.db, ready.queue) == (True, False)


async def test_ready_is_503_without_qdrant() -> None:
    app = make_app(VECTORS_MODE="qdrant", QDRANT_URL=f"http://{CLOSED}")

    async with client(app) as api:
        reply = await api.get("/api/health/ready")

    assert reply.status_code == 503
    assert ReadyOut.model_validate(reply.json()).qdrant is False


# The routes these tests add live outside /api: there every route but the public ones needs a
# session (tests/contract/auth).


async def test_unhandled_error_is_internal_with_request_id() -> None:
    app = make_app()

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("boom")

    async with client(app) as api:
        reply = await api.get("/boom")

    assert reply.status_code == 500
    error = ErrorOut.model_validate(reply.json())
    assert error.code == "internal"
    assert error.request_id == reply.headers["X-Request-Id"]


async def test_app_error_keeps_its_code_and_status() -> None:
    app = make_app()

    @app.get("/busy")
    async def busy() -> None:
        raise AppError("run_active", "Ответ ещё готовится", {"run_id": "r1"})

    async with client(app) as api:
        reply = await api.get("/busy")

    assert reply.status_code == 409
    assert ErrorOut.model_validate(reply.json()) == ErrorOut(
        code="run_active",
        message="Ответ ещё готовится",
        details={"run_id": "r1"},
        request_id=reply.headers["X-Request-Id"],
    )


async def test_unknown_route_is_not_found() -> None:
    async with client(make_app()) as api:
        reply = await api.get("/nope")

    assert reply.status_code == 404
    assert ErrorOut.model_validate(reply.json()).code == "not_found"


async def test_invalid_body_is_validation_error_without_input() -> None:
    app = make_app()

    class LoginIn(BaseModel):
        password: str
        attempts: int

    @app.post("/login")
    async def login(body: LoginIn) -> None: ...

    async with client(app) as api:
        reply = await api.post("/login", json={"password": "hunter2-x", "attempts": "many"})

    assert reply.status_code == 422
    assert ErrorOut.model_validate(reply.json()).code == "validation_error"
    assert "hunter2-x" not in reply.text


def test_every_error_code_has_a_status() -> None:
    assert set(STATUS) == set(get_args(ErrorCode.__value__))
