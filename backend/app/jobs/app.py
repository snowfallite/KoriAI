"""The queue on Postgres (tech.md §10.1): task registration, defer and the in-process workers."""

import asyncio
import importlib.util
import pkgutil
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Literal

import procrastinate
import structlog
from procrastinate.exceptions import AlreadyEnqueued
from procrastinate.job_context import JobContext
from procrastinate.jobs import Job, Status
from procrastinate.retry import RetryDecision
from procrastinate.tasks import Task
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from starlette.datastructures import State

from app import domains
from app.config import Settings
from app.contracts.jobs import Payload
from app.core.errors import TransientGatewayError

log = structlog.get_logger(__name__)

type Queue = Literal["default", "periodic", "heavy"]
# A handler gets the app state, as a route gets request.app.state.
type Handler[P: Payload] = Callable[[P, State], Awaitable[None]]
type PeriodicHandler = Callable[[State], Awaitable[None]]

MAX_ATTEMPTS = 5
STOP_TIMEOUT_S = 10.0
RESTART_DELAY_S = 5.0


class Retry(procrastinate.RetryStrategy):
    """The retries of §10.1; a job that a shutdown cut short runs again after the restart."""

    def get_retry_decision(self, *, exception: BaseException, job: Job) -> RetryDecision | None:
        if isinstance(exception, asyncio.CancelledError):
            return RetryDecision()
        return super().get_retry_decision(exception=exception, job=job)


RETRY = Retry(
    max_attempts=MAX_ATTEMPTS,
    exponential_wait=5,
    retry_exceptions={TransientGatewayError, OperationalError},
)


def _task_modules() -> list[str]:
    # Every domain with a tasks.py joins on its own: slices never edit this file (§16.1).
    names = (f"{domains.__name__}.{m.name}.tasks" for m in pkgutil.iter_modules(domains.__path__))
    return ["app.jobs.builtin", *(name for name in names if importlib.util.find_spec(name))]


# run_queue() swaps in a connector to the database of the settings.
procrastinate_app = procrastinate.App(
    connector=procrastinate.PsycopgConnector(), import_paths=_task_modules()
)
TASKS: dict[type[Payload], Task[..., Any, ...]] = {}


def task[P: Payload](
    name: str, payload: type[P], *, queue: Queue = "default", retry: Retry = RETRY
) -> Callable[[Handler[P]], Handler[P]]:
    """Registers the handler of a payload type: defer(payload) queues it (§10.1)."""

    def register(handler: Handler[P]) -> Handler[P]:
        if payload in TASKS:
            raise TypeError(f"{payload.__name__} already belongs to {TASKS[payload].name}")

        async def run(context: JobContext, **kwargs: Any) -> None:
            await handler(payload.model_validate(kwargs), context.additional_context["state"])

        job = procrastinate_app.task(name=name, queue=queue, retry=retry, pass_context=True)
        TASKS[payload] = job(run)
        return handler

    return register


def periodic(name: str, *, cron: str, lock: str) -> Callable[[PeriodicHandler], PeriodicHandler]:
    """Registers a handler of the periodic queue; the cron runs in UTC (§10.1)."""

    def register(handler: PeriodicHandler) -> PeriodicHandler:
        async def run(context: JobContext, timestamp: int) -> None:
            await handler(context.additional_context["state"])

        job = procrastinate_app.task(
            name=name, queue="periodic", lock=lock, retry=RETRY, pass_context=True
        )
        procrastinate_app.periodic(cron=cron)(job(run))
        return handler

    return register


async def defer(payload: Payload, *, schedule_at: datetime | None = None) -> int:
    """Queues the task of the payload type under the payload's locks (§10.1).

    A twin with the same queueing lock that already waits stands in for the new job; the result is
    the id of the job that does the work.
    """
    procrastinate_app.perform_import_paths()  # type: ignore[no-untyped-call] # fills TASKS
    queueing_lock = payload.queueing_lock()
    deferrer = TASKS[type(payload)].configure(
        lock=payload.lock(), queueing_lock=queueing_lock, schedule_at=schedule_at
    )
    try:
        return await deferrer.defer_async(**payload.model_dump(mode="json"))
    except AlreadyEnqueued:
        twins = await procrastinate_app.job_manager.list_jobs_async(
            queueing_lock=queueing_lock, status=Status.TODO.value
        )
    ids = [twin.id for twin in twins if twin.id is not None]
    # No twin left: it started meanwhile and freed the lock.
    return ids[0] if ids else await defer(payload, schedule_at=schedule_at)


@asynccontextmanager
async def run_queue(state: State) -> AsyncIterator[None]:
    """Opens the queue on the database of the settings; with JOBS_ENABLED runs the workers."""
    settings: Settings = state.settings
    url = make_url(settings.DATABASE_URL.get_secret_value()).set(drivername="postgresql")
    # min_size 0: the pool connects on demand, so the API starts while the database is away.
    connector = procrastinate.PsycopgConnector(
        conninfo=url.render_as_string(hide_password=False), min_size=0, max_size=4
    )
    with procrastinate_app.replace_connector(connector):
        async with procrastinate_app.open_async():
            workers = asyncio.create_task(_supervise(state)) if settings.JOBS_ENABLED else None
            try:
                yield
            finally:
                if workers is not None:
                    workers.cancel()
                    await asyncio.wait({workers})


async def _supervise(state: State) -> None:
    """Runs the two workers of §10.1 until cancelled; a failure restarts both."""
    manager = procrastinate_app.job_manager
    while True:
        try:
            # AD-02: one process, and its workers are down, so a running job was cut off.
            for job in await manager.list_jobs_async(status=Status.DOING.value):
                if job.attempts < MAX_ATTEMPTS:
                    await manager.retry_job(job)
                else:  # cut off every time: it may be what brings the process down
                    await manager.finish_job(job, status=Status.FAILED, delete_job=False)
            async with asyncio.TaskGroup() as group:
                group.create_task(_work(state, ["default", "periodic"], concurrency=2))
                group.create_task(_work(state, ["heavy"], concurrency=1))
        except Exception:
            log.exception("queue_workers_failed")
        await asyncio.sleep(RESTART_DELAY_S)


async def _work(state: State, queues: list[str], *, concurrency: int) -> None:
    await procrastinate_app.run_worker_async(
        queues=queues,
        concurrency=concurrency,
        install_signal_handlers=False,
        shutdown_graceful_timeout=STOP_TIMEOUT_S,
        additional_context={"state": state},
    )
    # A worker that waits for jobs returns only when a failure stopped it.
    raise RuntimeError(f"the worker of {', '.join(queues)} stopped")
