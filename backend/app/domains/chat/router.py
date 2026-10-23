"""The chat tab (tech.md §6.5): questions, threads and runs; the stream of a run lives in
app/http/sse.py."""

from uuid import UUID

from fastapi import APIRouter

from app.contracts.api.chat import MessageAcceptedOut, MessageIn, RunOut, ThreadDetailOut
from app.domains.chat.deps import ChatServiceDep, lifespan
from app.http.deps import CurrentUser

router = APIRouter(prefix="/api/chat", tags=["chat"], lifespan=lifespan)


@router.post("/messages", status_code=202)
async def send(body: MessageIn, user: CurrentUser, chat: ChatServiceDep) -> MessageAcceptedOut:
    """A question without thread_id starts a thread; the answer streams from
    GET /api/chat/runs/{run_id}/events."""
    return await chat.send(user.user_id, user.role, body)


@router.get("/threads/{thread_id}")
async def thread(thread_id: UUID, user: CurrentUser, chat: ChatServiceDep) -> ThreadDetailOut:
    return await chat.thread(user.user_id, thread_id)


@router.get("/runs/{run_id}")
async def run(run_id: UUID, user: CurrentUser, chat: ChatServiceDep) -> RunOut:
    return await chat.run(user.user_id, run_id)


@router.post("/runs/{run_id}/cancel", status_code=202)
async def cancel(run_id: UUID, user: CurrentUser, chat: ChatServiceDep) -> RunOut:
    """The run stops after its current step and keeps what it wrote as a partial answer."""
    return await chat.cancel(user.user_id, run_id)
