"""The SSE stream of a run (tech.md §7); the chat domain owns the rest of /api/chat/runs."""

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Request
from sse_starlette import EventSourceResponse, ServerSentEvent

from app.http.deps import CurrentUser
from app.http.events import RunEventBus

router = APIRouter(prefix="/api/chat/runs", tags=["chat"])

RETRY_MS = 3000
PING_S = 15.0


@router.get(
    "/{run_id}/events",
    response_class=EventSourceResponse,
    # The class sets its media type per instance, so FastAPI cannot see it.
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def run_events(
    run_id: UUID,
    request: Request,
    user: CurrentUser,
    last_event_id: Annotated[int, Header(ge=0)] = 0,
) -> EventSourceResponse:
    """Events after Last-Event-ID, which the browser sends on a reconnect."""
    bus: RunEventBus = request.app.state.events
    events = bus.subscribe(run_id, user.user_id, after=last_event_id)

    async def frames() -> AsyncIterator[ServerSentEvent]:
        yield ServerSentEvent(retry=RETRY_MS)
        async for event in events:
            yield ServerSentEvent(event.model_dump_json(), id=str(event.seq), event=event.type)

    return EventSourceResponse(
        frames(), ping=PING_S, ping_message_factory=lambda: ServerSentEvent(comment="ping")
    )
