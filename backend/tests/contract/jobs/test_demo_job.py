"""POST /api/dev/jobs/demo (S1-07 AC 2; tech.md §6.7, §10.2). No workers run here: queued jobs
stay waiting. tests/contract/auth covers the 401 of every private route."""

import uuid

import httpx
import pytest
from fastapi import FastAPI

from app.contracts.api.health import DemoJobOut
from app.contracts.common import ErrorOut
from app.jobs.app import procrastinate_app

DEMO = "/api/dev/jobs/demo"


async def test_repeat_of_a_waiting_key_gets_the_same_job(user_api: httpx.AsyncClient) -> None:
    key = uuid.uuid4().hex

    first = await user_api.post(DEMO, json={"key": key, "value": "a"})
    second = await user_api.post(DEMO, json={"key": key, "value": "b"})

    assert (first.status_code, second.status_code) == (202, 202), second.text
    job = DemoJobOut.model_validate(first.json())
    assert DemoJobOut.model_validate(second.json()) == job
    jobs = await procrastinate_app.job_manager.list_jobs_async(queueing_lock=f"demo:{key}")
    assert [(j.id, j.task_name, j.status, j.task_kwargs) for j in jobs] == [
        (job.job_id, "demo.echo", "todo", {"key": key, "value": "a"})
    ]


async def test_other_keys_get_their_own_jobs(user_api: httpx.AsyncClient) -> None:
    replies = [
        await user_api.post(DEMO, json={"key": uuid.uuid4().hex, "value": "v"}) for _ in "ab"
    ]

    ids = {DemoJobOut.model_validate(reply.json()).job_id for reply in replies}
    assert len(ids) == 2


@pytest.mark.parametrize(("env", "status"), [("ci", 202), ("staging", 404), ("prod", 404)])
async def test_demo_job_lives_in_dev_and_ci_only(
    app: FastAPI, user_api: httpx.AsyncClient, env: str, status: int
) -> None:
    app.state.settings = app.state.settings.model_copy(update={"APP_ENV": env})

    reply = await user_api.post(DEMO, json={"key": uuid.uuid4().hex, "value": "v"})

    assert reply.status_code == status, reply.text
    if status == 404:
        assert ErrorOut.model_validate(reply.json()).code == "not_found"
