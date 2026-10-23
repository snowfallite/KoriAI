"""The chat in tests (tech.md §3.4, §6.5, §7): ask a question, wait for its run, read the thread
and the events of the run."""

import asyncio
from collections.abc import AsyncIterator
from uuid import UUID

import httpx
from fastapi import FastAPI

from app.contracts.api.auth import MeOut
from app.contracts.api.chat import MessageAcceptedOut, ThreadDetailOut
from app.contracts.stream import StreamEvent
from app.http.events import RunEventBus

TIMEOUT_S = 10


async def ask(
    api: httpx.AsyncClient, text: str, thread_id: UUID | None = None
) -> MessageAcceptedOut:
    body = {"thread_id": None if thread_id is None else str(thread_id), "text": text}
    reply = await api.post("/api/chat/messages", json=body)
    assert reply.status_code == 202, reply.text
    return MessageAcceptedOut.model_validate(reply.json())


async def settle(app: FastAPI) -> None:
    """Waits until every run of the app has ended. Contract tests share one connection, so a
    request that touches the database waits for the last write of the run."""
    await asyncio.wait_for(app.state.chat_runs.join(), TIMEOUT_S)


async def thread_of(api: httpx.AsyncClient, thread_id: UUID) -> ThreadDetailOut:
    reply = await api.get(f"/api/chat/threads/{thread_id}")
    assert reply.status_code == 200, reply.text
    return ThreadDetailOut.model_validate(reply.json())


async def user_id_of(api: httpx.AsyncClient) -> UUID:
    reply = await api.get("/api/auth/me")
    assert reply.status_code == 200, reply.text
    return MeOut.model_validate(reply.json()).user.id


async def wait_for_event(app: FastAPI, run_id: UUID, user_id: UUID, kind: str) -> StreamEvent:
    """The first event of a kind on the live stream of a run, read from the bus."""
    bus: RunEventBus = app.state.events
    events: AsyncIterator[StreamEvent] = bus.subscribe(run_id, user_id)

    async def first() -> StreamEvent:
        async for event in events:
            if event.type == kind:
                return event
        raise AssertionError(f"the run ended without {kind}")

    return await asyncio.wait_for(first(), TIMEOUT_S)
