"""The LLM gate hands slots out by priority, then by arrival (S1-09; tech.md §3.3)."""

import asyncio

from hypothesis import given
from hypothesis import strategies as st

from app.contracts.llm import Priority
from app.gateways.llm.gate import InProcessPriorityGate

priorities: st.SearchStrategy[Priority] = st.sampled_from(["interactive", "background"])


async def grant_order(arrivals: list[Priority], capacity: int) -> list[int]:
    gate = InProcessPriorityGate(capacity, timeout_s=5)
    order: list[int] = []
    release = asyncio.Event()

    async def holder() -> None:
        async with gate.slot("interactive", "holder"):
            await release.wait()

    async def caller(index: int, priority: Priority) -> None:
        async with gate.slot(priority, f"caller:{index}"):
            order.append(index)

    tasks = [asyncio.create_task(holder()) for _ in range(capacity)]
    await asyncio.sleep(0)  # the holders take every slot
    for index, priority in enumerate(arrivals):
        tasks.append(asyncio.create_task(caller(index, priority)))
        await asyncio.sleep(0)
    release.set()
    await asyncio.gather(*tasks)
    assert gate.stats().in_use == 0
    return order


@given(st.lists(priorities, min_size=1, max_size=12), st.integers(1, 3))
def test_slots_go_by_priority_then_by_arrival(arrivals: list[Priority], capacity: int) -> None:
    expected = sorted(range(len(arrivals)), key=lambda i: (arrivals[i] == "background", i))

    assert asyncio.run(grant_order(arrivals, capacity)) == expected
