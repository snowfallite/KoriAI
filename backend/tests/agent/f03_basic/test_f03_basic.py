"""Scenario f03_basic (F-03; tech.md §9.1, §9.6, §9.9, §9.12): the minimal graph load_context →
agent → postprocess answers with text from seed/llm/f03_basic.yaml. A recording model shows what
the model read on each call."""

# ruff: noqa: RUF001  (Russian test data)

from collections.abc import AsyncIterator
from typing import Any

import httpx
from fastapi import FastAPI
from langchain_core.callbacks import AsyncCallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGenerationChunk
from pydantic import PrivateAttr

from app.contracts.api.chat import MarkdownBlock
from app.gateways.factory import override_gateways
from app.gateways.fixtures import SEED, read_yaml
from app.gateways.llm.fake import ScriptedChatModel, seed
from tests.support.chat import ask, settle, thread_of

DURATION = "Что такое дюрация облигации?"
DRAW = "Нарисуй график стоимости"


class RecordingModel(ScriptedChatModel):
    _seen: list[list[BaseMessage]] = PrivateAttr(default_factory=list)

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        self._seen.append(list(messages))
        async for chunk in super()._astream(messages, stop, run_manager, **kwargs):
            yield chunk


class RecordingLlm:
    """The seed scenarios behind LlmPort, remembering the messages of every call."""

    def __init__(self) -> None:
        self.seen: list[list[BaseMessage]] = []

    def chat_model(self, model_id: str, *, streaming: bool) -> BaseChatModel:
        model = RecordingModel(scenarios=seed(), model_id=model_id, streaming=streaming)
        model._seen = self.seen
        return model

    async def count_tokens(self, texts: list[str], model_id: str) -> list[int]:
        return [len(text) // 4 + 1 for text in texts]

    async def list_models(self) -> list[str]:
        return []


def answer_of(pattern: str) -> str:
    for scenario in read_yaml(SEED / "llm" / "f03_basic.yaml"):
        if scenario["match"]["user_regex"] == pattern:
            text: str = scenario["steps"][0]["text"]
            return text
    raise AssertionError(pattern)


def text_of(message: BaseMessage) -> str:
    assert isinstance(message.content, str)
    return message.content


async def test_the_model_reads_the_prompt_the_context_and_then_the_question(
    app: FastAPI, demo_api: httpx.AsyncClient
) -> None:
    llm = RecordingLlm()
    with override_gateways(app.state, llm=llm):
        await ask(demo_api, DURATION)
        await settle(app)

    [messages] = llm.seen
    system, question = messages
    assert isinstance(system, SystemMessage) and isinstance(question, HumanMessage)
    asked = text_of(question)
    assert asked.endswith(DURATION)
    # Accounts go by alias and name, never by the T-Invest id (§3.5, §9.12).
    for account in read_yaml(SEED / "tinvest" / "accounts.yaml"):
        assert account["id"] not in asked
    assert "acc1 «Брокерский счёт»" in asked and "acc2 «ИИС»" in asked
    assert "МСК" in asked


async def test_the_next_question_reads_the_turn_before_it(
    app: FastAPI, user_api: httpx.AsyncClient
) -> None:
    llm = RecordingLlm()
    with override_gateways(app.state, llm=llm):
        first = await ask(user_api, DURATION)
        await settle(app)
        await ask(user_api, DRAW, first.thread_id)
        await settle(app)

    second = llm.seen[1]
    assert [type(m) for m in second] == [SystemMessage, HumanMessage, AIMessage, HumanMessage]
    assert text_of(second[0]) == text_of(llm.seen[0][0])  # the cached prefix stays the same
    assert text_of(second[1]) == DURATION
    assert text_of(second[2]) == answer_of("(?i)дюраци")
    assert text_of(second[3]).endswith(DRAW)


async def test_an_unknown_placeholder_drops_out_of_the_blocks_with_a_warning(
    app: FastAPI, user_api: httpx.AsyncClient
) -> None:
    accepted = await ask(user_api, DRAW)
    await settle(app)

    answer = (await thread_of(user_api, accepted.thread_id)).messages[-1]

    lead = answer_of("(?i)нарисуй").split("\n\n")[0]
    assert answer.status == "complete"
    assert answer.blocks == [MarkdownBlock(text=lead)]
    assert [warning.code for warning in answer.meta.warnings] == ["unknown_placeholder"]
