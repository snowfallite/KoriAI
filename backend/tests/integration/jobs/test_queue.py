"""The queue on a real Postgres (S1-07 AC 1, 3, 4; tech.md §10): the demo job through the API and
the workers, restarts, retries, idempotency of the service tasks."""

import asyncio
import os
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import httpx
import pytest
from alembic import command
from fastapi import FastAPI
from procrastinate.jobs import Job
from sqlalchemy import create_engine, insert, select, text
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.datastructures import State

from app.config import Settings
from app.contracts.api.health import DemoJobOut
from app.contracts.jobs import DemoEchoPayload, Payload
from app.core.errors import TransientGatewayError
from app.db.schema.system import JobMarker, WebCache
from app.db.schema.users import User, UserSession
from app.jobs import app as queue
from app.jobs.app import defer, procrastinate_app, task
from app.jobs.builtin import cleanup, demo_echo
from app.main import create_app
from tests.support.api import HEADERS, sign_up
from tests.support.db import alembic_config, scratch_database
from tests.support.jobs import run_twice

DEMO = "/api/dev/jobs/demo"
TOUCHED = ("procrastinate_jobs", "procrastinate_workers", "job_markers", "users", "web_cache")
# Jobs of the cleanup test by their final state; the old ones finished 8 days ago.
OLD_AND_NEW_JOBS = {
    "old-succeeded": "succeeded",
    "old-failed": "failed",
    "new-succeeded": "succeeded",
    "waiting": "todo",
}
CACHE_ROW = {"kind": "search", "request": {}, "response": {}, "credits": 1}


class FlakyPayload(Payload):
    error: Literal["outage", "bug"]


@task("test.flaky", FlakyPayload)
async def flaky(payload: FlakyPayload, state: State) -> None:
    if payload.error == "outage":
        raise TransientGatewayError("tinvest_unavailable")
    raise ValueError("a bug, not an outage")


class HeldPayload(Payload):
    key: str


# Each test creates the event of its key in its own loop.
RELEASED: dict[str, asyncio.Event] = {}


@task("test.held", HeldPayload)
async def held(payload: HeldPayload, state: State) -> None:
    """Waits for the release of its key, then marks the key done."""
    await RELEASED[payload.key].wait()
    await demo_echo(DemoEchoPayload(key=payload.key, value="done"), state)


@pytest.fixture(scope="module")
def database_url() -> Iterator[str]:
    with scratch_database() as url:
        command.upgrade(alembic_config(url), "head")
        yield url


@pytest.fixture(autouse=True)
def _empty_tables(database_url: str) -> None:
    # Workers and snapshots of one test must not meet what another test left.
    engine = create_engine(database_url)
    with engine.begin() as conn:
        conn.execute(text(f"truncate {', '.join(TOUCHED)} cascade"))
    engine.dispose()


@asynccontextmanager
async def started(url: str, *, jobs: bool, **settings: Any) -> AsyncIterator[FastAPI]:
    config = Settings(
        _env_file=None, DATABASE_URL=url, JOBS_ENABLED=jobs, REGISTRATION_MODE="open", **settings
    )
    app = create_app(config)
    async with app.router.lifespan_context(app):
        yield app


@asynccontextmanager
async def signed_in(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", headers=HEADERS
    ) as api:
        await sign_up(api)
        yield api


async def until[T](probe: Callable[[], Awaitable[T]], within: float = 5) -> T:
    """The first truthy answer of the probe, or its last answer at the deadline."""
    deadline = time.monotonic() + within
    while not (answer := await probe()) and time.monotonic() < deadline:  # noqa: ASYNC110 - polls the database
        await asyncio.sleep(0.02)
    return answer


def marker(engine: AsyncEngine, key: str) -> Callable[[], Awaitable[str | None]]:
    async def value() -> str | None:
        async with engine.connect() as conn:
            found: str | None = await conn.scalar(
                select(JobMarker.value).where(JobMarker.key == key)
            )
            return found

    return value


def job(job_id: int, ready: Callable[[Job], bool]) -> Callable[[], Awaitable[Job | None]]:
    async def found() -> Job | None:
        [row] = await procrastinate_app.job_manager.list_jobs_async(id=job_id)
        return row if ready(row) else None

    return found


async def test_demo_job_writes_its_marker_within_5_seconds(database_url: str) -> None:
    async with started(database_url, jobs=True) as app, signed_in(app) as api:
        reply = await api.post(DEMO, json={"key": "ac1", "value": "v1"})
        assert reply.status_code == 202, reply.text
        DemoJobOut.model_validate(reply.json())

        assert await until(marker(app.state.engine, "ac1"), within=5) == "v1"


async def test_demo_echo_has_one_effect(database_url: str) -> None:
    async with started(database_url, jobs=False) as app:
        engine = app.state.engine
        payload = DemoEchoPayload(key="ac3", value="v1")

        rows = await run_twice(lambda: demo_echo(payload, app.state), engine, "job_markers")

        assert [(row.key, row.value) for row in rows["job_markers"]] == [("ac3", "v1")]
        # An upsert: a new value of the key replaces the old one (§10.2).
        await demo_echo(DemoEchoPayload(key="ac3", value="v2"), app.state)
        assert await marker(engine, "ac3")() == "v2"


async def test_job_queued_before_a_restart_runs_after_it(database_url: str) -> None:
    async with started(database_url, jobs=False) as app, signed_in(app) as api:
        reply = await api.post(DEMO, json={"key": "ac4", "value": "v4"})
        assert reply.status_code == 202, reply.text

    async with started(database_url, jobs=True) as app:
        assert await until(marker(app.state.engine, "ac4")) == "v4"


async def test_job_cut_short_by_a_shutdown_runs_after_the_restart(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(queue, "STOP_TIMEOUT_S", 0.1)
    release = RELEASED["cut"] = asyncio.Event()
    async with started(database_url, jobs=True):
        job_id = await defer(HeldPayload(key="cut"))
        assert await until(job(job_id, lambda j: j.status == "doing"))
    release.set()

    async with started(database_url, jobs=True) as app:
        assert await until(marker(app.state.engine, "cut")) == "done"


async def test_job_left_running_by_a_crash_runs_after_the_restart(database_url: str) -> None:
    async with started(database_url, jobs=False) as app:
        job_id = await defer(DemoEchoPayload(key="crash", value="v"))
        # A killed process leaves its job running with no worker to finish it.
        async with app.state.engine.begin() as conn:
            update = text("update procrastinate_jobs set status = 'doing' where id = :id")
            await conn.execute(update, {"id": job_id})

    async with started(database_url, jobs=True) as app:
        assert await until(marker(app.state.engine, "crash")) == "v"


async def test_outage_is_retried_and_a_bug_fails_the_job(database_url: str) -> None:
    async with started(database_url, jobs=True):
        outage = await defer(FlakyPayload(error="outage"))
        bug = await defer(FlakyPayload(error="bug"))

        retried = await until(job(outage, lambda j: j.attempts == 1))
        failed = await until(job(bug, lambda j: j.status == "failed"))

    assert retried is not None and retried.status == "todo"
    # exponential_wait=5 puts the first retry 5 s later.
    assert retried.scheduled_at is not None
    assert retried.scheduled_at > datetime.now(UTC) + timedelta(seconds=3)
    # attempts counts the runs: the bug ran once.
    assert failed is not None and failed.attempts == 1


async def test_workers_start_once_the_queue_schema_appears(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(queue, "RESTART_DELAY_S", 0.1)
    with scratch_database() as url:
        async with started(url, jobs=True) as app:
            await asyncio.sleep(0.3)  # the workers fail on the missing tables and wait
            await asyncio.to_thread(command.upgrade, alembic_config(url), "head")
            await defer(DemoEchoPayload(key="late", value="v"))

            assert await until(marker(app.state.engine, "late")) == "v"


async def test_cleanup_drops_expired_rows_old_media_and_old_jobs(
    database_url: str, tmp_path: Path
) -> None:
    media = tmp_path / "media" / "ab"
    media.mkdir(parents=True)
    old_file, fresh_file = media / "old", media / "fresh"
    old_file.write_bytes(b"old")
    fresh_file.write_bytes(b"fresh")
    month_ago = time.time() - 31 * 24 * 3600
    os.utime(old_file, (month_ago, month_ago))
    now = datetime.now(UTC)

    async with started(database_url, jobs=False, DATA_DIR=tmp_path) as app:
        engine = app.state.engine
        jobs = {key: await defer(DemoEchoPayload(key=key, value="v")) for key in OLD_AND_NEW_JOBS}
        async with engine.begin() as conn:
            user = await conn.scalar(
                insert(User)
                .values(email="cleanup@example.test", password_hash="x")
                .returning(User.id)
            )
            await conn.execute(
                insert(UserSession),
                [
                    {
                        "user_id": user,
                        "token_hash": b"expired",
                        "expires_at": now - timedelta(minutes=1),
                    },
                    {"user_id": user, "token_hash": b"live", "expires_at": now + timedelta(days=1)},
                ],
            )
            await conn.execute(
                insert(WebCache),
                [
                    {**CACHE_ROW, "key_hash": b"expired", "expires_at": now - timedelta(minutes=1)},
                    {**CACHE_ROW, "key_hash": b"live", "expires_at": now + timedelta(days=1)},
                ],
            )
            for key, status in OLD_AND_NEW_JOBS.items():
                if status != "todo":
                    finish = text("update procrastinate_jobs set status = :status where id = :id")
                    await conn.execute(finish, {"status": status, "id": jobs[key]})
            # Their last event, the finish, was 8 days ago.
            backdate = text(
                "update procrastinate_events set at = now() - interval '8 days'"
                " where job_id = any(:ids)"
            )
            await conn.execute(backdate, {"ids": [jobs["old-succeeded"], jobs["old-failed"]]})

        tables = await run_twice(
            lambda: cleanup(app.state), engine, "sessions", "web_cache", "procrastinate_jobs"
        )

    assert [row.token_hash for row in tables["sessions"]] == [b"live"]
    assert [row.key_hash for row in tables["web_cache"]] == [b"live"]
    left = {row.id for row in tables["procrastinate_jobs"]}
    assert left == {jobs["new-succeeded"], jobs["waiting"]}
    assert (old_file.exists(), fresh_file.exists()) == (False, True)
