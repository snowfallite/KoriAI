"""LLM port (tech.md §8.3): every call of a model goes through metering.py."""

from typing import Protocol

from langchain_core.language_models import BaseChatModel


class LlmPort(Protocol):
    def chat_model(self, model_id: str, *, streaming: bool) -> BaseChatModel: ...
    async def count_tokens(self, texts: list[str], model_id: str) -> list[int]: ...
    async def list_models(self) -> list[str]: ...
