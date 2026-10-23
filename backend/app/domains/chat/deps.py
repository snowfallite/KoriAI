"""Providers of the chat domain (tech.md §16.1) and the run tasks of the process."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from starlette.requests import HTTPConnection

from app.db.base import UnitOfWork
from app.domains.agent.service import AgentService
from app.domains.chat.service import ChatService, LiveRuns, recover


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """The router joins the lifespan of the app inside it (FastAPI include_router), after the
    database and the clients exist: main.py stays the same for every slice (§16.1)."""
    runs = LiveRuns()
    app.state.chat_runs = runs
    await recover(app.state.engine)
    try:
        yield
    finally:
        await runs.aclose()


def chat_service(conn: HTTPConnection) -> ChatService:
    state = conn.app.state
    return ChatService(
        UnitOfWork(state.engine), state.events, state.chat_runs, AgentService.of(state)
    )


ChatServiceDep = Annotated[ChatService, Depends(chat_service)]
