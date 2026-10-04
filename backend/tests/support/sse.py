"""The SSE stream of a run read the way EventSource reads it, checked against tech.md §7."""

from collections.abc import Iterable
from uuid import UUID

import httpx
from pydantic import TypeAdapter

from app.contracts.stream import StreamEvent

EVENT: TypeAdapter[StreamEvent] = TypeAdapter(StreamEvent)
RETRY = {"retry": "3000"}
PING = {"": "ping"}  # a comment line has no field name

type Frame = dict[str, str]


def events_url(run_id: UUID) -> str:
    return f"/api/chat/runs/{run_id}/events"


def frames(lines: Iterable[str]) -> list[Frame]:
    """The frames a blank line ends; an unfinished last frame is dropped, as EventSource does."""
    done: list[Frame] = []
    frame: Frame = {}
    for line in lines:
        if line:
            name, _, value = line.partition(":")
            frame[name] = value.removeprefix(" ")
        elif frame:
            done.append(frame)
            frame = {}
    return done


def event_of(frame: Frame, run_id: UUID) -> StreamEvent:
    """The event of a data frame: id is its seq, event is its type (§7)."""
    event = EVENT.validate_json(frame["data"])
    assert (frame["id"], frame["event"], event.run_id) == (str(event.seq), event.type, run_id)
    return event


async def sse_collect(
    api: httpx.AsyncClient, run_id: UUID, last_event_id: int | None = None
) -> list[StreamEvent]:
    """Every event of a stream that ends, after `last_event_id` when given."""
    headers = {} if last_event_id is None else {"Last-Event-ID": str(last_event_id)}
    reply = await api.get(events_url(run_id), headers=headers)
    assert reply.status_code == 200, reply.text
    assert reply.headers["content-type"].startswith("text/event-stream")

    got = frames(reply.text.splitlines())
    assert got[0] == RETRY  # the first frame (§7)
    events = [event_of(frame, run_id) for frame in got if "data" in frame]
    first = (last_event_id or 0) + 1
    assert [event.seq for event in events] == list(range(first, first + len(events)))
    # run.finished closes the stream, so a stream that ended sent it last.
    assert [event.type for event in events[-1:]] in ([], ["run.finished"])
    return events
