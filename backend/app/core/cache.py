"""TTL cache in the memory of the one API process (tech.md §8.2, AD-02)."""

import time
from collections.abc import Awaitable, Callable, Hashable


class TtlCache[V]:
    def __init__(
        self,
        ttl_s: float,
        *,
        max_items: int = 10_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl_s = ttl_s
        self._max_items = max_items
        self._clock = clock
        self._items: dict[Hashable, tuple[float, V]] = {}

    def get(self, key: Hashable) -> V | None:
        found = self._items.get(key)
        return found[1] if found is not None and found[0] > self._clock() else None

    def put(self, key: Hashable, value: V) -> V:
        if len(self._items) >= self._max_items:
            # ponytail: a full cache starts over; an LRU if the hit rate ever matters.
            self._items.clear()
        self._items[key] = (self._clock() + self._ttl_s, value)
        return value

    async def get_or_load(self, key: Hashable, load: Callable[[], Awaitable[V]]) -> V:
        found = self.get(key)
        return found if found is not None else self.put(key, await load())
