"""A restart interrupts the runs the last process left (F-03 AC 7; tech.md §3.4): the event bus
and the run tasks lived in its memory, so nobody finishes those runs any more."""

from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import delete, insert, select

from app.config import Settings
from app.contracts.api.chat import ThreadDetailOut
from app.db.schema.agent import AgentRun
from app.db.schema.chat import Message, Thread
from app.db.schema.users import User
from app.main import create_app
from tests.support.api import HEADERS, sign_up
from tests.support.chat import user_id_of


def app_on(database_url: str, data_dir: Path) -> FastAPI:
    settings = Settings(
        _env_file=None,
        DATABASE_URL=database_url,
        JOBS_ENABLED=False,
        FAKE_STRICT=True,
        DATA_DIR=data_dir,
        REGISTRATION_MODE="open",
    )
    return create_app(settings)


def client(app: FastAPI, cookies: httpx.Cookies | None = None) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(
        transport=transport, base_url="http://test", headers=HEADERS, cookies=cookies
    )


async def add(app: FastAPI, model: Any, **values: Any) -> UUID:
    async with app.state.engine.begin() as conn:
        found: UUID = (
            await conn.execute(insert(model).values(**values).returning(model.id))
        ).scalar_one()
    return found


@pytest.mark.parametrize("status", ["queued", "running"])
async def test_a_restart_interrupts_the_runs_of_the_last_process(
    database_url: str, tmp_path: Path, status: str
) -> None:
    before = app_on(database_url, tmp_path)
    async with before.router.lifespan_context(before), client(before) as api:
        await sign_up(api)
        user = await user_id_of(api)
        thread = await add(before, Thread, user_id=user)
        answered = await add(
            before, Message, thread_id=thread, user_id=user, role="user", content="Раз"
        )
        done = await add(
            before,
            AgentRun,
            thread_id=thread,
            user_id=user,
            user_message_id=answered,
            status="done",
        )
        await add(
            before,
            Message,
            thread_id=thread,
            user_id=user,
            role="assistant",
            content="Ответ",
            run_id=done,
        )
        asked = await add(
            before, Message, thread_id=thread, user_id=user, role="user", content="Два"
        )
        left = await add(
            before, AgentRun, thread_id=thread, user_id=user, user_message_id=asked, status=status
        )
        cookies = api.cookies

    after = app_on(database_url, tmp_path)
    async with after.router.lifespan_context(after), client(after, cookies) as api:
        try:
            async with after.state.engine.connect() as conn:
                found = await conn.execute(select(AgentRun).where(AgentRun.thread_id == thread))
                runs = {row.id: row for row in found}
            reply = await api.get(f"/api/chat/threads/{thread}")
        finally:
            async with after.state.engine.begin() as conn:
                await conn.execute(delete(User).where(User.id == user))

    assert runs[left].status == "interrupted" and runs[left].finished_at is not None
    assert runs[done].status == "done"
    assert reply.status_code == 200, reply.text
    detail = ThreadDetailOut.model_validate(reply.json())
    assert detail.active_run is None
    # The last question has no answer: the chat shows «Ответ прерван» under it.
    assert [(m.role, m.content) for m in detail.messages] == [
        ("user", "Раз"),
        ("assistant", "Ответ"),
        ("user", "Два"),
    ]
