"""The run event stream and the echo stream (S1-08 AC 1-4; tech.md §6.7, §7). ASGITransport
returns a reply only when its stream ends; tests/integration/http reads a live one."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from pydantic import JsonValue

from app.contracts.api.auth import MeOut
from app.contracts.api.health import EchoOut
from app.contracts.common import ErrorOut
from app.contracts.stream import DevEchoEvent, RunFinishedEvent
from app.http import sse
from app.http.events import RunEventBus
from tests.support.api import sign_up
from tests.support.sse import PING, events_url, frames, sse_collect

ECHO = "/api/dev/echo"


async def echo(api: httpx.AsyncClient, payload: dict[str, JsonValue]) -> UUID:
    reply = await api.post(ECHO, json={"payload": payload})
    assert reply.status_code == 202, reply.text
    return EchoOut.model_validate(reply.json()).stream_id


def error(reply: httpx.Response) -> tuple[int, str]:
    return reply.status_code, ErrorOut.model_validate(reply.json()).code


async def test_echo_streams_the_payload_back(user_api: httpx.AsyncClient) -> None:
    payload: dict[str, JsonValue] = {"text": "Привет, Kōri", "list": [1, 2.5, None, True]}

    stream_id = await echo(user_api, payload)
    events = await sse_collect(user_api, stream_id)

    assert [type(event) for event in events] == [DevEchoEvent, RunFinishedEvent]
    echoed, finished = events
    assert isinstance(echoed, DevEchoEvent) and echoed.payload == payload
    assert isinstance(finished, RunFinishedEvent)
    assert (finished.status, finished.message_id, finished.error) == ("done", None, None)


async def test_reconnect_gets_only_events_after_last_event_id(user_api: httpx.AsyncClient) -> None:
    stream_id = await echo(user_api, {"n": 1})
    events = await sse_collect(user_api, stream_id)

    assert await sse_collect(user_api, stream_id, last_event_id=1) == events[1:]
    assert await sse_collect(user_api, stream_id, last_event_id=2) == []


async def test_stream_of_another_user_is_not_found(
    user_api: httpx.AsyncClient,
    new_client: Callable[[], httpx.AsyncClient],
    make_invite: Callable[[], Awaitable[str]],
) -> None:
    stream_id = await echo(user_api, {})

    async with new_client() as stranger:
        await sign_up(stranger, await make_invite())
        assert error(await stranger.get(events_url(stream_id))) == (404, "not_found")
    assert error(await user_api.get(events_url(uuid.uuid4()))) == (404, "not_found")


async def test_expired_stream_is_gone_for_its_owner_only(
    app: FastAPI,
    user_api: httpx.AsyncClient,
    new_client: Callable[[], httpx.AsyncClient],
    make_invite: Callable[[], Awaitable[str]],
) -> None:
    app.state.events = RunEventBus(ttl_s=0)  # a finished stream expires at once
    stream_id = await echo(user_api, {})
    await sse_collect(user_api, stream_id)  # waits for run.finished
    await asyncio.sleep(0.01)

    assert error(await user_api.get(events_url(stream_id))) == (410, "gone")
    async with new_client() as stranger:
        await sign_up(stranger, await make_invite())
        assert error(await stranger.get(events_url(stream_id))) == (404, "not_found")


async def test_idle_stream_pings(
    app: FastAPI, user_api: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert sse.PING_S == 15  # §7
    monkeypatch.setattr(sse, "PING_S", 0.02)
    me = MeOut.model_validate((await user_api.get("/api/auth/me")).json())
    bus: RunEventBus = app.state.events
    run_id = uuid.uuid4()
    bus.open(run_id, me.user.id)

    stream = asyncio.create_task(user_api.get(events_url(run_id)))
    await asyncio.sleep(0.3)
    bus.publish(run_id, RunFinishedEvent, status="done", message_id=None, error=None)
    reply = await asyncio.wait_for(stream, 5)

    assert reply.status_code == 200, reply.text
    assert frames(reply.text.splitlines()).count(PING) >= 3


async def test_last_event_id_must_be_a_seq(user_api: httpx.AsyncClient) -> None:
    stream_id = await echo(user_api, {})

    reply = await user_api.get(events_url(stream_id), headers={"Last-Event-ID": "abc"})

    assert error(reply) == (422, "validation_error")


@pytest.mark.parametrize(("env", "status"), [("ci", 202), ("staging", 404), ("prod", 404)])
async def test_echo_lives_in_dev_and_ci_only(
    app: FastAPI, user_api: httpx.AsyncClient, env: str, status: int
) -> None:
    app.state.settings = app.state.settings.model_copy(update={"APP_ENV": env})

    reply = await user_api.post(ECHO, json={"payload": {}})

    assert reply.status_code == status, reply.text
    if status == 404:
        assert error(reply) == (404, "not_found")
