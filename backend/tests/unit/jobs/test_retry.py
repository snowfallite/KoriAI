"""Retries of tech.md §10.1 and the S1-07 rows of the §10.2 task table."""

import asyncio
from datetime import UTC, datetime

import pytest
from procrastinate.jobs import Job
from sqlalchemy.exc import OperationalError

from app.contracts.jobs import DemoEchoPayload
from app.core.errors import TransientGatewayError
from app.jobs.app import RETRY, TASKS, procrastinate_app

JOB = Job(queue="default", lock=None, queueing_lock=None, task_name="demo.echo")
OUTAGES = [
    TransientGatewayError("tinvest_unavailable"),
    OperationalError("select 1", {}, ConnectionError("server closed the connection")),
]


def wait_s(error: BaseException, attempts: int) -> float | None:
    decision = RETRY.get_retry_decision(exception=error, job=JOB.evolve(attempts=attempts))
    if decision is None:
        return None
    retry_at = decision.retry_at or datetime.now(UTC)
    return (retry_at - datetime.now(UTC)).total_seconds()


@pytest.mark.parametrize("error", OUTAGES)
def test_outage_is_retried_with_exponential_wait(error: Exception) -> None:
    # exponential_wait=5: 5 ** (attempts + 1) seconds.
    assert wait_s(error, 0) == pytest.approx(5, abs=1)
    assert wait_s(error, 1) == pytest.approx(25, abs=1)


@pytest.mark.parametrize("error", OUTAGES)
def test_outage_stops_after_five_retries(error: Exception) -> None:
    assert wait_s(error, 4) is not None
    assert wait_s(error, 5) is None


def test_other_errors_are_not_retried() -> None:
    assert wait_s(ValueError("a bug, not an outage"), 0) is None


def test_job_cut_short_by_shutdown_runs_again_at_once() -> None:
    assert wait_s(asyncio.CancelledError(), 4) == pytest.approx(0, abs=1)


def test_job_that_keeps_cancelling_itself_stops() -> None:
    assert wait_s(asyncio.CancelledError(), 5) is None


def test_tasks_follow_the_core_table() -> None:
    procrastinate_app.perform_import_paths()  # type: ignore[no-untyped-call]

    echo = TASKS[DemoEchoPayload]
    assert (echo.name, echo.queue, echo.lock, echo.retry_strategy) == (
        "demo.echo",
        "default",
        None,
        RETRY,
    )
    [cleanup] = [
        periodic
        for periodic in procrastinate_app.periodic_registry.periodic_tasks.values()
        if periodic.task.name == "maintenance.cleanup"
    ]
    assert (cleanup.cron, cleanup.task.queue, cleanup.task.lock) == (
        "30 1 * * *",
        "periodic",
        "cleanup",
    )
    assert cleanup.task.retry_strategy == RETRY
