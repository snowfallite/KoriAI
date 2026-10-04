"""Event streams of runs (tech.md §3.4, §7): seq, the replay buffer, its TTL and the owner."""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.contracts.stream import StreamEvent
from app.core import time
from app.core.errors import AppError


@dataclass
class _Stream:
    owner: UUID
    events: list[StreamEvent] = field(default_factory=list)
    finished: bool = False
    # Set and swapped on every event: a follower waits on the one it saw before reading.
    changed: asyncio.Event = field(default_factory=asyncio.Event)


class RunEventBus:
    """Streams in the memory of the one API process (AD-02): a restart drops them all.

    The publisher of a stream ends it with run.finished; until then its followers wait.
    """

    def __init__(self, ttl_s: float) -> None:
        self._ttl_s = ttl_s
        self._streams: dict[UUID, _Stream] = {}
        # ponytail: owners of expired streams stay until a restart, a few dozen bytes a run;
        # drop the oldest if one process ever outlives millions of runs.
        self._expired: dict[UUID, UUID] = {}

    def open(self, run_id: UUID, owner: UUID) -> None:
        self._streams[run_id] = _Stream(owner)

    def publish(self, run_id: UUID, kind: type[StreamEvent], **fields: Any) -> None:
        """Adds the next event of the stream: seq starts at 1 and grows by 1."""
        stream = self._streams[run_id]
        if stream.finished:
            raise RuntimeError(f"run {run_id} already sent run.finished, the last event")
        event = kind(seq=len(stream.events) + 1, run_id=run_id, ts=time.now(), **fields)
        stream.events.append(event)
        if event.type == "run.finished":
            stream.finished = True
            asyncio.get_running_loop().call_later(self._ttl_s, self._expire, run_id)
        stream.changed.set()
        stream.changed = asyncio.Event()

    def subscribe(self, run_id: UUID, user_id: UUID, after: int = 0) -> AsyncIterator[StreamEvent]:
        """Events with seq above `after`, live until run.finished.

        Refuses before the first event, so an SSE route answers 404 or 410 instead of a 200.
        """
        stream = self._streams.get(run_id)
        if stream is not None and stream.owner == user_id:
            return _follow(stream, after)
        if self._expired.get(run_id) == user_id:
            raise AppError("gone", "Поток событий закрыт: ответ сохранён в треде")
        # Someone else's stream looks missing.
        raise AppError("not_found", "Поток событий не найден")

    def _expire(self, run_id: UUID) -> None:
        self._expired[run_id] = self._streams.pop(run_id).owner


async def _follow(stream: _Stream, after: int) -> AsyncIterator[StreamEvent]:
    sent = max(after, 0)
    while True:
        changed = stream.changed
        while sent < len(stream.events):
            sent += 1
            yield stream.events[sent - 1]
        if stream.finished:
            return
        await changed.wait()
