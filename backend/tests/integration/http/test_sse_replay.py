"""Replay of a live run stream over a real HTTP server (S1-08 AC 2; tech.md §3.4, §7).
httpx.ASGITransport answers only after the stream ends, so these tests run uvicorn."""

import asyncio
import socket
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI

from app.contracts.api.auth import MeOut
from app.contracts.stream import (
    RunFinishedEvent,
    RunStartedEvent,
    StreamEvent,
    TextDeltaEvent,
)
from app.http.events import RunEventBus
from tests.support.api import HEADERS, sign_up
from tests.support.sse import RETRY, Frame, event_of, events_url

TIMEOUT_S = 5


@asynccontextmanager
async def serve(app: FastAPI) -> AsyncIterator[str]:
    """The app on uvicorn at a free loopback port; the fixture already ran its lifespan."""
    server = uvicorn.Server(uvicorn.Config(app, lifespan="off", log_config=None))
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        serving = asyncio.create_task(server.serve(sockets=[sock]))
        while not server.started:  # noqa: ASYNC110 uvicorn offers a flag, no event
            await asyncio.sleep(0.01)
        try:
            yield f"http://127.0.0.1:{sock.getsockname()[1]}"
        finally:
            server.should_exit = True
            await asyncio.wait_for(serving, TIMEOUT_S)


async def next_frame(lines: AsyncIterator[str]) -> Frame:
    frame: Frame = {}
    while line := await asyncio.wait_for(anext(lines), TIMEOUT_S):
        name, _, value = line.partition(":")
        frame[name] = value.removeprefix(" ")
    return frame


async def next_event(lines: AsyncIterator[str], run_id: uuid.UUID) -> StreamEvent:
    """The next event of a live stream; pings and retry frames pass by."""
    while "data" not in (frame := await next_frame(lines)):
        pass
    return event_of(frame, run_id)


async def test_reconnect_resumes_a_live_stream_after_last_event_id(
    app: FastAPI, make_invite: Callable[[], Awaitable[str]]
) -> None:
    bus: RunEventBus = app.state.events
    run_id = uuid.uuid4()
    async with serve(app) as base_url, httpx.AsyncClient(base_url=base_url, headers=HEADERS) as api:
        await sign_up(api, await make_invite())
        me = MeOut.model_validate((await api.get("/api/auth/me")).json())
        bus.open(run_id, me.user.id)
        bus.publish(run_id, RunStartedEvent)

        async with api.stream("GET", events_url(run_id)) as first:
            lines = first.aiter_lines()
            assert await next_frame(lines) == RETRY
            assert (await next_event(lines, run_id)).seq == 1
            bus.publish(run_id, TextDeltaEvent, delta="При")
            assert (await next_event(lines, run_id)).seq == 2
        # The connection broke; the run goes on without a listener.
        bus.publish(run_id, TextDeltaEvent, delta="вет")

        resume = {"Last-Event-ID": "2"}
        async with api.stream("GET", events_url(run_id), headers=resume) as second:
            lines = second.aiter_lines()
            missed = await next_event(lines, run_id)
            bus.publish(run_id, RunFinishedEvent, status="done", message_id=None, error=None)
            last = await next_event(lines, run_id)
            rest = [line async for line in lines]  # the server closes after run.finished

    assert (missed.seq, missed.type, last.seq, last.type) == (3, "text.delta", 4, "run.finished")
    assert isinstance(missed, TextDeltaEvent) and missed.delta == "вет"
    assert rest == []
