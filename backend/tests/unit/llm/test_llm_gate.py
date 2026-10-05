"""The LLM gate (S1-09 AC 3; tech.md §3.3): interactive before background, FIFO inside a class,
places in the queue, llm_busy once the wait runs out."""

import asyncio

import pytest

from app.contracts.llm import Priority
from app.core.errors import TransientGatewayError
from app.gateways.llm.gate import InProcessPriorityGate


async def test_three_interactive_and_two_background_get_slots_in_order() -> None:
    gate = InProcessPriorityGate(capacity=1, timeout_s=5)
    granted: list[str] = []
    places: dict[str, list[int]] = {}
    release = asyncio.Event()

    async def holder() -> None:
        async with gate.slot("interactive", "holder"):
            await release.wait()

    async def caller(name: str, priority: Priority) -> None:
        async with gate.slot(priority, name, on_queue=places.setdefault(name, []).append):
            granted.append(name)

    tasks = [asyncio.create_task(holder())]
    await asyncio.sleep(0)
    arrivals: list[tuple[str, Priority]] = [
        ("b1", "background"),
        ("i1", "interactive"),
        ("b2", "background"),
        ("i2", "interactive"),
        ("i3", "interactive"),
    ]
    for name, priority in arrivals:
        tasks.append(asyncio.create_task(caller(name, priority)))
        await asyncio.sleep(0)  # each caller queues before the next one comes
    assert gate.stats().waiting == 5

    release.set()
    await asyncio.wait_for(asyncio.gather(*tasks), 1)

    assert granted == ["i1", "i2", "i3", "b1", "b2"]
    # A newcomer of the interactive class moves the background callers back.
    assert places == {
        "b1": [1, 2, 3, 4, 3, 2, 1],
        "i1": [1],
        "b2": [3, 4, 5, 4, 3, 2, 1],
        "i2": [2, 1],
        "i3": [3, 2, 1],
    }
    assert gate.stats().model_dump() == {"capacity": 1, "in_use": 0, "waiting": 0}


async def test_a_free_slot_goes_without_a_queue() -> None:
    gate = InProcessPriorityGate(capacity=2, timeout_s=5)
    places: list[int] = []

    async with (
        gate.slot("background", "job:1", on_queue=places.append) as first,
        gate.slot("background", "job:2", on_queue=places.append),
    ):
        assert gate.stats().model_dump() == {"capacity": 2, "in_use": 2, "waiting": 0}

    assert places == []
    assert (first.owner, first.priority) == ("job:1", "background")
    assert gate.stats().in_use == 0


async def test_the_wait_ends_with_llm_busy_and_frees_the_place() -> None:
    gate = InProcessPriorityGate(capacity=1, timeout_s=0.05)

    async with gate.slot("interactive", "run:1"):
        with pytest.raises(TransientGatewayError) as busy:
            async with gate.slot("interactive", "run:2"):
                pytest.fail("the slot is taken")
        assert gate.stats().waiting == 0

    assert busy.value.code == "llm_busy"
    assert gate.stats().in_use == 0


async def test_a_cancelled_caller_leaves_the_queue_and_keeps_no_slot() -> None:
    gate = InProcessPriorityGate(capacity=1, timeout_s=5)
    granted: list[str] = []

    async def caller(name: str) -> None:
        async with gate.slot("interactive", name):
            granted.append(name)

    async with gate.slot("interactive", "holder"):
        gone = asyncio.create_task(caller("gone"))
        stays = asyncio.create_task(caller("stays"))
        await asyncio.sleep(0)
        gone.cancel()
        await asyncio.sleep(0)
        assert gate.stats().waiting == 1

    await asyncio.wait_for(stays, 1)
    assert granted == ["stays"]
    assert gate.stats().in_use == 0


async def test_the_ticket_tells_how_long_the_caller_waited() -> None:
    gate = InProcessPriorityGate(capacity=1, timeout_s=5)
    waits: list[int] = []

    async def caller() -> None:
        async with gate.slot("background", "job:1") as ticket:
            waits.append(ticket.wait_ms)

    async with gate.slot("interactive", "run:1") as first:
        task = asyncio.create_task(caller())
        await asyncio.sleep(0.05)
    await asyncio.wait_for(task, 1)

    assert first.wait_ms < 50
    assert waits[0] >= 40
