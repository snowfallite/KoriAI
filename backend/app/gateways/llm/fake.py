"""LLM fake (tech.md §8.1, §8.3): ScriptedChatModel plays the scenarios of seed/llm/*.yaml.

A scenario matches by the purpose of the call and a regex on the last user message; each call
of the model takes the next step: the AI messages after that user message count the steps.
Faults of `chat_model` hit the calls of the model it gave and raise what the SDK raises.
"""

import functools
import json
import re
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import httpx
from gigachat.context import session_id_cvar
from gigachat.exceptions import RateLimitError, ServerError
from langchain_core.callbacks import AsyncCallbackManagerForLLMRun, CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    ToolCall,
)
from langchain_core.messages.ai import UsageMetadata
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import BaseModel, ConfigDict, PrivateAttr, TypeAdapter, model_validator

from app.contracts.faults import FaultRule
from app.contracts.llm import LlmPurpose, ModelFamily
from app.core.errors import ContractViolation
from app.gateways.fakes import Fake, port_method
from app.gateways.fixtures import SEED, read_yaml
from app.gateways.llm.metering import current_call

FALLBACK = "Тестовый ответ фейковой модели."
API = "https://gigachat.fake/api/v1/chat/completions"


class _Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Match(_Scenario):
    purpose: LlmPurpose | None = None
    user_regex: str | None = None


class ScriptedToolCall(_Scenario):
    name: str
    args: dict[str, Any] = {}


class Step(_Scenario):
    """One call of the model: text, a call of a function, or text before a call."""

    text: str | None = None
    tool_call: ScriptedToolCall | None = None


class Usage(_Scenario):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    precached_prompt_tokens: int = 0


class Scenario(_Scenario):
    match: Match = Match()
    steps: list[Step] = []
    structured: dict[str, Any] | None = None  # the answer of structured output
    usage: Usage | None = None

    @model_validator(mode="after")
    def _one_kind(self) -> "Scenario":
        if bool(self.steps) == (self.structured is not None):
            raise ValueError("a scenario has either steps or structured")
        return self


SCENARIOS: TypeAdapter[list[Scenario]] = TypeAdapter(list[Scenario])


def load_scenarios(paths: Sequence[Path]) -> list[Scenario]:
    return [s for path in paths for s in SCENARIOS.validate_python(read_yaml(path) or [])]


@functools.cache
def seed() -> list[Scenario]:
    return load_scenarios(sorted((SEED / "llm").glob("*.yaml")))


def _text_of(message: BaseMessage) -> str:
    return message.content if isinstance(message.content, str) else str(message.text)


def _usage(
    scenario: Scenario | None, messages: Sequence[BaseMessage], answer: str
) -> UsageMetadata:
    if scenario is not None and scenario.usage is not None:
        u = scenario.usage
        prompt, completion, precached = (
            u.prompt_tokens,
            u.completion_tokens,
            u.precached_prompt_tokens,
        )
    else:  # about four characters a token
        prompt = sum(len(_text_of(m)) for m in messages) // 4 + 1
        completion, precached = len(answer) // 4 + 1, 0
    return UsageMetadata(
        input_tokens=prompt,
        output_tokens=completion,
        total_tokens=prompt + completion,
        input_token_details={"cache_read": precached},
    )


class ScriptedChatModel(BaseChatModel):
    scenarios: list[Scenario]
    model_id: str = "fake"
    streaming: bool = False
    strict: bool = True
    _fake: "FakeLlm | None" = PrivateAttr(default=None)

    @classmethod
    def from_file(cls, path: Path, *, strict: bool = True) -> "ScriptedChatModel":
        """A test feeds its own scenarios this way (§8.3)."""
        return cls(scenarios=load_scenarios([path]), strict=strict)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(
        self,
        tools: Sequence[Mapping[str, Any] | type | Callable[..., Any] | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        if tool_choice == "any":  # as langchain-gigachat refuses it
            raise ContractViolation("GigaChat API does not support tool_choice='any' (§8.3)")
        formatted = [convert_to_openai_tool(tool) for tool in tools]
        return self.bind(tools=formatted, tool_choice=tool_choice, **kwargs)

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        raise NotImplementedError("metering calls models asynchronously")

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        answer = await self._answer(messages, kwargs.get("tools") or [])
        return ChatResult(generations=[ChatGeneration(message=answer)])

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        answer = await self._answer(messages, kwargs.get("tools") or [])
        words = re.findall(r"\S+\s*", answer.text)
        size = max(1, len(words) // 3)  # three pieces or so, like a slow network
        for start in range(0, len(words), size):
            piece = "".join(words[start : start + size])
            if run_manager is not None:
                await run_manager.on_llm_new_token(piece)
            yield ChatGenerationChunk(message=AIMessageChunk(content=piece))
        calls = [
            {
                "name": c["name"],
                "args": json.dumps(c["args"], ensure_ascii=False),
                "id": c["id"],
                "index": n,
            }
            for n, c in enumerate(answer.tool_calls)
        ]
        last = AIMessageChunk(
            content="", tool_call_chunks=calls, usage_metadata=answer.usage_metadata
        )
        yield ChatGenerationChunk(message=last)

    async def _answer(
        self, messages: Sequence[BaseMessage], tools: list[dict[str, Any]]
    ) -> AIMessage:
        call = current_call.get()
        if call is None:
            raise ContractViolation("models are called through metering (§8.3)")
        users = [n for n, m in enumerate(messages) if isinstance(m, HumanMessage)]
        last_user = users[-1] if users else -1
        user_text = _text_of(messages[last_user]) if users else ""
        if self._fake is not None:
            arguments = {
                "model_id": self.model_id,
                "purpose": call.purpose,
                "session_id": session_id_cvar.get(),
                "user_message": user_text,
            }
            if await self._fake.enter("chat_model", arguments):
                return AIMessage(content="", usage_metadata=_usage(None, messages, ""))
        scenario = next(
            (
                s
                for s in self.scenarios
                if s.match.purpose in {None, call.purpose}
                and (s.match.user_regex is None or re.search(s.match.user_regex, user_text))
            ),
            None,
        )
        if scenario is None:
            if self.strict:
                raise ContractViolation(f"no scenario for {call.purpose}: {user_text[:80]!r}")
            return AIMessage(content=FALLBACK, usage_metadata=_usage(None, messages, FALLBACK))
        if scenario.structured is not None:
            return self._structured(scenario, messages, tools)
        step_index = sum(isinstance(m, AIMessage) for m in messages[last_user + 1 :])
        if step_index >= len(scenario.steps) and self.strict:
            raise ContractViolation(
                f"the scenario has {len(scenario.steps)} steps, call {step_index + 1}"
            )
        step = scenario.steps[min(step_index, len(scenario.steps) - 1)]
        tool_calls = (
            [
                ToolCall(
                    name=step.tool_call.name, args=step.tool_call.args, id=f"call_{step_index + 1}"
                )
            ]
            if step.tool_call
            else []
        )
        text = step.text or ""
        return AIMessage(
            content=text, tool_calls=tool_calls, usage_metadata=_usage(scenario, messages, text)
        )

    @staticmethod
    def _structured(
        scenario: Scenario, messages: Sequence[BaseMessage], tools: list[dict[str, Any]]
    ) -> AIMessage:
        data = scenario.structured or {}
        usage = _usage(scenario, messages, json.dumps(data, ensure_ascii=False))
        if not tools:  # json mode: the object as text
            return AIMessage(content=json.dumps(data, ensure_ascii=False), usage_metadata=usage)
        name = tools[0]["function"]["name"]
        return AIMessage(
            content="",
            tool_calls=[ToolCall(name=name, args=data, id="call_1")],
            usage_metadata=usage,
        )


def _nothing(arguments: dict[str, Any]) -> list[Any]:
    return []


class FakeLlm(Fake):
    port = "llm"
    unavailable = "llm_busy"
    rate_limited = "llm_busy"

    def __init__(self, models: Mapping[ModelFamily, str], **options: Any) -> None:
        super().__init__(**options)
        self.models = dict(models)
        self.scenarios = seed()

    def chat_model(self, model_id: str, *, streaming: bool) -> BaseChatModel:
        if model_id not in self.models.values():
            raise ContractViolation(f"FakeLlm.chat_model: unknown model {model_id!r}")
        model = ScriptedChatModel(
            scenarios=self.scenarios, model_id=model_id, streaming=streaming, strict=self.strict
        )
        model._fake = self
        return model

    @port_method(empty=_nothing)
    async def count_tokens(self, texts: list[str], model_id: str) -> list[int]:
        return [len(text) // 4 + 1 for text in texts]

    @port_method(empty=_nothing)
    async def list_models(self) -> list[str]:
        return list(self.models.values())

    def failure(self, rule: FaultRule) -> Exception:
        if rule.method not in {"chat_model", "llm.chat_model"}:
            return super().failure(rule)
        # What the SDK raises, so metering meets the same errors as with GigaChat.
        match rule.mode:
            case "timeout":
                return httpx.ReadTimeout("the fake model timed out")
            case "rate_limit":
                headers = httpx.Headers({"retry-after": str(rule.latency_ms / 1000)})
                return RateLimitError(API, 429, b'{"message": "Too Many Requests"}', headers)
            case _:
                return ServerError(API, 500, b'{"message": "Internal Server Error"}', None)
