"""GigaChat behind LlmPort (tech.md §8.3): models of langchain-gigachat, one per id and mode."""

from collections.abc import Awaitable
from typing import Literal

import httpx
from gigachat.exceptions import RateLimitError, ResponseError, ServerError
from langchain_core.language_models import BaseChatModel
from langchain_gigachat import GigaChat

from app.config import Settings
from app.core.errors import GatewayError, PermanentGatewayError, TransientGatewayError
from app.gateways.retry import with_retries

# llm_calls.status of a failed call.
type FailedStatus = Literal["error", "timeout", "rate_limited"]


def call_error(exc: BaseException) -> tuple[FailedStatus, GatewayError] | None:
    """How a failed call of a model counts and whether a retry may help; None: not ours."""
    match exc:
        case RateLimitError():
            return "rate_limited", TransientGatewayError("llm_busy", exc.retry_after or None)
        case ServerError():
            return "error", TransientGatewayError("llm_busy")
        case ResponseError():  # 4xx: a request or credentials the API refuses
            return "error", PermanentGatewayError("internal")
        case httpx.TimeoutException() | TimeoutError():
            return "timeout", TransientGatewayError("llm_busy")
        case httpx.TransportError():
            return "error", TransientGatewayError("llm_busy")
        case GatewayError():
            return "error", exc
    return None


async def _guarded[T](pending: Awaitable[T]) -> T:
    try:
        return await pending
    except Exception as exc:
        failure = call_error(exc)
        if failure is None:
            raise
        raise failure[1] from exc


class GigaChatLlm:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        # Every model logs in on its own: one per id and mode keeps the logins few.
        self._models: dict[tuple[str, bool], GigaChat] = {}

    def chat_model(self, model_id: str, *, streaming: bool) -> BaseChatModel:
        return self._model(model_id, streaming=streaming)

    async def count_tokens(self, texts: list[str], model_id: str) -> list[int]:
        model = self._model(model_id)

        async def call() -> list[int]:
            return [count.tokens for count in await _guarded(model.atokens_count(texts))]

        return await with_retries(call)

    async def list_models(self) -> list[str]:
        model = self._model(self._settings.LLM_MODELS["lite"])

        async def call() -> list[str]:
            return [m.id_ for m in (await _guarded(model.aget_models())).data]

        return await with_retries(call)

    def _model(self, model_id: str, *, streaming: bool = False) -> GigaChat:
        key = (model_id, streaming)
        if key not in self._models:
            s = self._settings
            self._models[key] = GigaChat(
                credentials=s.GIGACHAT_CREDENTIALS.get_secret_value(),
                scope=s.GIGACHAT_SCOPE,
                base_url=s.GIGACHAT_BASE_URL,
                model=model_id,
                ca_bundle_file=str(s.GIGACHAT_CA_BUNDLE),
                timeout=s.GIGACHAT_TIMEOUT_S,
                streaming=streaming,
                max_retries=0,  # metering retries inside the slot of the gate (§3.3)
            )
        return self._models[key]
