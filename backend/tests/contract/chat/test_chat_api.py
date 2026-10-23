"""Chat threads and runs over HTTP and SSE (F-03 AC 1-6, 9; tech.md §3.4, §6.5, §6.6, §7).

Expected texts come from seed/llm/f03_basic.yaml. Contract tests share one database connection,
so a test lets the run finish (settle) before it reads anything over HTTP.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from langchain_core.callbacks import AsyncCallbackManagerForLLMRun, CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from sqlalchemy import insert, select

from app.contracts.api.chat import MarkdownBlock, RunOut
from app.contracts.common import ErrorOut
from app.contracts.faults import FaultPlan, FaultRule
from app.contracts.stream import (
    RunFinishedEvent,
    RunQueuedEvent,
    TextDeltaEvent,
)
from app.db.schema.agent import AgentRun, LlmCall
from app.db.schema.chat import Message, Thread
from app.gateways.factory import Gateways, override_gateways
from app.gateways.fixtures import SEED, read_yaml
from app.gateways.llm.fake import FakeLlm
from app.gateways.llm.metering import Metering
from tests.support.api import sign_up
from tests.support.chat import ask, settle, thread_of, user_id_of, wait_for_event
from tests.support.sse import sse_collect

DURATION = "Что такое дюрация облигации?"
FIRST_PIECE = "Первая часть ответа. "

type Faults = Callable[..., FaultPlan]


def scenario_text(pattern: str) -> str:
    """The text answer of the f03 scenario that matches the regex."""
    for scenario in read_yaml(SEED / "llm" / "f03_basic.yaml"):
        if scenario["match"]["user_regex"] == pattern:
            text: str = scenario["steps"][0]["text"]
            return text
    raise AssertionError(pattern)


def scenario_tokens(pattern: str) -> int:
    for scenario in read_yaml(SEED / "llm" / "f03_basic.yaml"):
        if scenario["match"]["user_regex"] == pattern:
            usage = scenario["usage"]
            return int(usage["prompt_tokens"]) + int(usage["completion_tokens"])
    raise AssertionError(pattern)


def gateways(app: FastAPI) -> Gateways:
    found: Gateways = app.state.gateways
    return found


def error_of(reply: httpx.Response) -> ErrorOut:
    return ErrorOut.model_validate(reply.json())


async def rows(app: FastAPI, model: Any, *where: Any) -> list[Any]:
    found = await app.state.engine.execute(select(model).where(*where))
    return list(found.all())


class StallingModel(BaseChatModel):
    """Streams one piece and then waits for good: only a cancel ends its answer."""

    @property
    def _llm_type(self) -> str:
        return "stalling"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        raise NotImplementedError

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        yield ChatGenerationChunk(message=AIMessageChunk(content=FIRST_PIECE))
        await asyncio.Event().wait()


class StallingLlm:
    def chat_model(self, model_id: str, *, streaming: bool) -> BaseChatModel:
        return StallingModel()

    async def count_tokens(self, texts: list[str], model_id: str) -> list[int]:
        return [len(text) for text in texts]

    async def list_models(self) -> list[str]:
        return []


@pytest.fixture
def no_backoff(app: FastAPI) -> Iterator[None]:
    """Metering retries 5xx without the pauses between tries."""
    metering = Metering(
        gateways(app).gate, lambda: app.state.engine, app.state.settings, backoff_s=0
    )
    with override_gateways(app.state, metering=metering):
        yield


# AC 1


async def test_a_message_without_a_thread_starts_a_thread_and_a_run(
    app: FastAPI, user_api: httpx.AsyncClient
) -> None:
    accepted = await ask(user_api, DURATION)
    await settle(app)

    detail = await thread_of(user_api, accepted.thread_id)
    assert detail.thread.id == accepted.thread_id
    assert [(m.id, m.role, m.content) for m in detail.messages[:1]] == [
        (accepted.message_id, "user", DURATION)
    ]
    assert detail.thread.message_count == len(detail.messages) == 2
    assert detail.thread.last_message_at == detail.messages[-1].created_at
    [run] = await rows(app, AgentRun, AgentRun.id == accepted.run_id)
    assert (run.thread_id, run.user_message_id) == (accepted.thread_id, accepted.message_id)


async def test_a_message_into_a_thread_of_someone_else_is_not_found(
    app: FastAPI,
    user_api: httpx.AsyncClient,
    new_client: Callable[[], httpx.AsyncClient],
    make_invite: Callable[[], Any],
) -> None:
    mine = await ask(user_api, DURATION)
    await settle(app)
    async with new_client() as other:
        await sign_up(other, await make_invite())

        reply = await other.post(
            "/api/chat/messages", json={"thread_id": str(mine.thread_id), "text": DURATION}
        )
        seen = await other.get(f"/api/chat/threads/{mine.thread_id}")

    assert (reply.status_code, error_of(reply).code) == (404, "not_found")
    assert (seen.status_code, error_of(seen).code) == (404, "not_found")
    assert len(await rows(app, Message, Message.thread_id == mine.thread_id)) == 2


async def test_an_unknown_thread_is_not_found(user_api: httpx.AsyncClient) -> None:
    unknown = str(uuid.uuid4())

    posted = await user_api.post("/api/chat/messages", json={"thread_id": unknown, "text": "Да?"})
    read = await user_api.get(f"/api/chat/threads/{unknown}")

    assert (posted.status_code, error_of(posted).code) == (404, "not_found")
    assert (read.status_code, error_of(read).code) == (404, "not_found")


@pytest.mark.parametrize("text", ["", "   \n\t", "я" * 4001])
async def test_an_empty_or_too_long_question_is_refused(
    app: FastAPI, user_api: httpx.AsyncClient, text: str
) -> None:
    reply = await user_api.post("/api/chat/messages", json={"thread_id": None, "text": text})

    assert (reply.status_code, error_of(reply).code) == (422, "validation_error")
    assert await rows(app, Thread) == []


# AC 2 and AC 6


async def test_a_busy_gate_queues_the_run_and_a_second_message_gets_run_active(
    app: FastAPI, user_api: httpx.AsyncClient
) -> None:
    user = await user_id_of(user_api)
    async with gateways(app).gate.slot("interactive", "another run"):
        first = await ask(user_api, DURATION)
        queued = await wait_for_event(app, first.run_id, user, "run.queued")

        again = await user_api.post(
            "/api/chat/messages", json={"thread_id": str(first.thread_id), "text": DURATION}
        )
        fresh = await user_api.post("/api/chat/messages", json={"thread_id": None, "text": "Ещё"})
    await settle(app)
    events = await sse_collect(user_api, first.run_id)

    assert isinstance(queued, RunQueuedEvent) and queued.position == 1
    for reply in (again, fresh):
        assert (reply.status_code, error_of(reply).code) == (409, "run_active")
    assert len(await rows(app, Thread)) == 1
    assert len(await rows(app, Message, Message.thread_id == first.thread_id)) == 2
    assert [e.type for e in events[:3]] == ["run.queued", "run.started", "step.started"]
    assert events[-1].type == "run.finished"


# AC 3 and AC 9


async def test_the_answer_streams_and_the_thread_returns_it_in_blocks(
    app: FastAPI, user_api: httpx.AsyncClient
) -> None:
    accepted = await ask(user_api, DURATION)
    await settle(app)
    events = await sse_collect(user_api, accepted.run_id)
    detail = await thread_of(user_api, accepted.thread_id)

    text = scenario_text("(?i)дюраци")
    types = [event.type for event in events]
    assert types[:2] == ["run.started", "step.started"]
    assert set(types[2:-1]) == {"text.delta"} and types[-1] == "run.finished"
    assert "".join(e.delta for e in events if isinstance(e, TextDeltaEvent)) == text
    finished = events[-1]
    assert isinstance(finished, RunFinishedEvent)
    assert (finished.status, finished.error) == ("done", None)

    question, answer = detail.messages
    assert (answer.id, answer.role, answer.status) == (finished.message_id, "assistant", "complete")
    assert answer.content == text
    # Paragraphs without a placeholder stay one block (seed/blocks_cases.json).
    assert answer.blocks == [MarkdownBlock(text=text)]
    assert (answer.meta.model_family, answer.meta.model_id) == ("lite", "GigaChat-2")
    assert answer.meta.tokens_billable == scenario_tokens("(?i)дюраци")
    assert (answer.artifacts, answer.sources, answer.meta.warnings) == ([], [], [])
    assert question.blocks == [MarkdownBlock(text=DURATION)]
    assert detail.active_run is None


async def test_the_model_gets_the_thread_as_its_session(
    app: FastAPI, user_api: httpx.AsyncClient
) -> None:
    llm = gateways(app).llm
    assert isinstance(llm, FakeLlm)

    accepted = await ask(user_api, DURATION)
    await settle(app)

    sessions = [call.args["session_id"] for call in llm.calls if call.method == "chat_model"]
    assert sessions == [str(accepted.thread_id)]


async def test_the_run_reports_its_end_and_model(app: FastAPI, user_api: httpx.AsyncClient) -> None:
    accepted = await ask(user_api, DURATION)
    await settle(app)

    reply = await user_api.get(f"/api/chat/runs/{accepted.run_id}")

    assert reply.status_code == 200, reply.text
    run = RunOut.model_validate(reply.json())
    assert (run.id, run.thread_id, run.status, run.error) == (
        accepted.run_id,
        accepted.thread_id,
        "done",
        None,
    )
    assert (run.model_family, run.model_id, run.steps) == ("lite", "GigaChat-2", 1)
    assert run.finished_at is not None and run.finished_at >= run.created_at


async def test_a_run_of_someone_else_is_not_found(
    app: FastAPI,
    user_api: httpx.AsyncClient,
    new_client: Callable[[], httpx.AsyncClient],
    make_invite: Callable[[], Any],
) -> None:
    accepted = await ask(user_api, DURATION)
    await settle(app)
    async with new_client() as other:
        await sign_up(other, await make_invite())
        read = await other.get(f"/api/chat/runs/{accepted.run_id}")
        cancel = await other.post(f"/api/chat/runs/{accepted.run_id}/cancel")
        unknown = await other.get(f"/api/chat/runs/{uuid.uuid4()}")

    for reply in (read, cancel, unknown):
        assert (reply.status_code, error_of(reply).code) == (404, "not_found")


# AC 4


async def test_a_cancel_during_the_stream_keeps_the_text_so_far_as_partial(
    app: FastAPI, user_api: httpx.AsyncClient
) -> None:
    user = await user_id_of(user_api)
    with override_gateways(app.state, llm=StallingLlm()):
        accepted = await ask(user_api, DURATION)
        await wait_for_event(app, accepted.run_id, user, "text.delta")

        reply = await user_api.post(f"/api/chat/runs/{accepted.run_id}/cancel")
        await settle(app)

    assert reply.status_code == 202, reply.text
    assert RunOut.model_validate(reply.json()).id == accepted.run_id
    events = await sse_collect(user_api, accepted.run_id)
    finished = events[-1]
    assert isinstance(finished, RunFinishedEvent)
    assert (finished.status, finished.error) == ("cancelled", None)
    detail = await thread_of(user_api, accepted.thread_id)
    answer = detail.messages[-1]
    assert (answer.id, answer.status, answer.content) == (
        finished.message_id,
        "partial",
        FIRST_PIECE,
    )
    assert detail.active_run is None
    [run] = await rows(app, AgentRun, AgentRun.id == accepted.run_id)
    assert (run.status, run.cancel_requested) == ("cancelled", True)
    [call] = await rows(app, LlmCall, LlmCall.run_id == accepted.run_id)
    assert call.status == "cancelled"


async def test_a_cancel_of_a_finished_run_is_a_conflict(
    app: FastAPI, user_api: httpx.AsyncClient
) -> None:
    accepted = await ask(user_api, DURATION)
    await settle(app)

    reply = await user_api.post(f"/api/chat/runs/{accepted.run_id}/cancel")

    assert (reply.status_code, error_of(reply).code) == (409, "conflict")


# AC 5


@pytest.mark.usefixtures("no_backoff")
async def test_a_model_that_fails_every_try_fails_the_run_with_an_error(
    app: FastAPI, user_api: httpx.AsyncClient, faults: Faults
) -> None:
    # Metering tries a 5xx once and retries it three times (§3.3, §8.3): all four fail here.
    faults(FaultRule(method="chat_model", mode="error", times=4))

    accepted = await ask(user_api, DURATION)
    await settle(app)
    events = await sse_collect(user_api, accepted.run_id)
    detail = await thread_of(user_api, accepted.thread_id)
    run = RunOut.model_validate((await user_api.get(f"/api/chat/runs/{accepted.run_id}")).json())

    finished = events[-1]
    assert isinstance(finished, RunFinishedEvent)
    assert finished.status == "failed"
    assert finished.error is not None and finished.error.code == "llm_busy"
    assert finished.error.message and finished.error.request_id
    answer = detail.messages[-1]
    assert (answer.id, answer.role, answer.status) == (finished.message_id, "assistant", "failed")
    assert run.status == "failed"
    assert run.error is not None and run.error.code == "llm_busy"
    [call] = await rows(app, LlmCall, LlmCall.run_id == accepted.run_id)
    assert (call.status, call.error_code) == ("error", "llm_busy")


async def test_three_failures_then_an_answer_still_finish_the_run(
    app: FastAPI, user_api: httpx.AsyncClient, faults: Faults, no_backoff: None
) -> None:
    faults(FaultRule(method="chat_model", mode="error", times=3))

    accepted = await ask(user_api, DURATION)
    await settle(app)
    events = await sse_collect(user_api, accepted.run_id)

    finished = events[-1]
    assert isinstance(finished, RunFinishedEvent) and finished.status == "done"


# A run no task of this process owns: the process that started it is gone (§3.4, AD-02).


async def orphan_run(app: FastAPI, api: httpx.AsyncClient, status: str) -> tuple[UUID, UUID]:
    user = await user_id_of(api)
    engine = app.state.engine
    thread = await engine.execute(insert(Thread).values(user_id=user).returning(Thread.id))
    thread_id: UUID = thread.scalar_one()
    message = await engine.execute(
        insert(Message)
        .values(thread_id=thread_id, user_id=user, role="user", content="Вопрос до рестарта")
        .returning(Message.id)
    )
    run = await engine.execute(
        insert(AgentRun)
        .values(
            thread_id=thread_id,
            user_id=user,
            user_message_id=message.scalar_one(),
            status=status,
        )
        .returning(AgentRun.id)
    )
    return thread_id, run.scalar_one()


@pytest.mark.parametrize("status", ["queued", "running"])
async def test_a_run_without_its_task_blocks_no_new_question(
    app: FastAPI, user_api: httpx.AsyncClient, status: str
) -> None:
    _, stale = await orphan_run(app, user_api, status)

    await ask(user_api, DURATION)
    await settle(app)

    [run] = await rows(app, AgentRun, AgentRun.id == stale)
    assert run.status == "interrupted" and run.finished_at is not None


async def test_a_thread_shows_no_active_run_for_a_run_without_its_task(
    app: FastAPI, user_api: httpx.AsyncClient
) -> None:
    thread_id, stale = await orphan_run(app, user_api, "running")

    detail = await thread_of(user_api, thread_id)
    cancel = await user_api.post(f"/api/chat/runs/{stale}/cancel")

    assert detail.active_run is None
    assert [m.role for m in detail.messages] == ["user"]
    assert (cancel.status_code, error_of(cancel).code) == (409, "conflict")
    [run] = await rows(app, AgentRun, AgentRun.id == stale)
    assert run.status == "interrupted"
