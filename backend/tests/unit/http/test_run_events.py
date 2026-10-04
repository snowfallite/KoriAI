"""RunEventBus (S1-08 AC 2 and 3; tech.md §3.4, §7): seq, replay, live follow, owner, TTL."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from uuid import UUID

import pytest

from app.contracts.stream import (
    RunFinishedEvent,
    RunStartedEvent,
    StreamEvent,
    TextDeltaEvent,
)
from app.core.errors import AppError
from app.http.events import RunEventBus

OWNER, STRANGER = uuid.uuid4(), uuid.uuid4()


def opened(ttl_s: float = 60) -> tuple[RunEventBus, UUID]:
    bus, run_id = RunEventBus(ttl_s), uuid.uuid4()
    bus.open(run_id, OWNER)
    return bus, run_id


def finish(bus: RunEventBus, run_id: UUID) -> None:
    bus.publish(run_id, RunFinishedEvent, status="done", message_id=None, error=None)


async def collect(events: AsyncIterator[StreamEvent]) -> list[StreamEvent]:
    return [event async for event in events]


def refusal(bus: RunEventBus, run_id: UUID, user_id: UUID) -> str:
    with pytest.raises(AppError) as refused:
        bus.subscribe(run_id, user_id)
    return refused.value.code


async def test_seq_starts_at_one_and_grows_by_one() -> None:
    bus, run_id = opened()
    for delta in ("При", "в", "ет"):
        bus.publish(run_id, TextDeltaEvent, delta=delta)
    finish(bus, run_id)

    events = await collect(bus.subscribe(run_id, OWNER))

    assert [event.seq for event in events] == [1, 2, 3, 4]
    assert {event.run_id for event in events} == {run_id}
    assert events[-1].type == "run.finished"


async def test_follower_gets_events_published_after_it_joined() -> None:
    bus, run_id = opened()
    bus.publish(run_id, RunStartedEvent)
    follower = asyncio.create_task(collect(bus.subscribe(run_id, OWNER)))
    await asyncio.sleep(0)  # the follower drains the buffer and waits

    bus.publish(run_id, TextDeltaEvent, delta="a")
    await asyncio.sleep(0)
    bus.publish(run_id, TextDeltaEvent, delta="b")
    finish(bus, run_id)

    events = await asyncio.wait_for(follower, 1)
    assert [event.seq for event in events] == [1, 2, 3, 4]


async def test_subscribe_after_a_seq_replays_only_newer_events() -> None:
    bus, run_id = opened()
    bus.publish(run_id, RunStartedEvent)
    bus.publish(run_id, TextDeltaEvent, delta="a")
    finish(bus, run_id)

    assert [e.seq for e in await collect(bus.subscribe(run_id, OWNER, after=1))] == [2, 3]
    assert await collect(bus.subscribe(run_id, OWNER, after=3)) == []


async def test_run_finished_is_the_last_event() -> None:
    bus, run_id = opened()
    finish(bus, run_id)

    with pytest.raises(RuntimeError):
        bus.publish(run_id, TextDeltaEvent, delta="late")


def test_stream_of_another_user_looks_missing() -> None:
    bus, run_id = opened()

    assert refusal(bus, run_id, STRANGER) == "not_found"
    assert refusal(bus, uuid.uuid4(), OWNER) == "not_found"


async def test_finished_stream_is_gone_after_its_ttl() -> None:
    bus, run_id = opened(ttl_s=0.01)
    finish(bus, run_id)
    assert [e.seq for e in await collect(bus.subscribe(run_id, OWNER))] == [1]

    await asyncio.sleep(0.05)

    assert refusal(bus, run_id, OWNER) == "gone"
    assert refusal(bus, run_id, STRANGER) == "not_found"


async def test_live_stream_never_expires() -> None:
    bus, run_id = opened(ttl_s=0)
    bus.publish(run_id, RunStartedEvent)

    await asyncio.sleep(0.01)

    assert (await anext(bus.subscribe(run_id, OWNER))).seq == 1
