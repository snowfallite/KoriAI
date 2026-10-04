"""The external clients of the process (tech.md §8.1): a real adapter or a fake per *_MODE.

Real adapters load on demand: the SDKs of fakes-only runs stay out of memory.
"""

import dataclasses
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any

from starlette.datastructures import State

from app.config import Settings
from app.contracts.faults import FaultPlan
from app.gateways.disclosure.port import DisclosurePort
from app.gateways.embeddings.port import EmbeddingsPort
from app.gateways.fetch.port import FetchPort
from app.gateways.files.local import LocalFiles
from app.gateways.files.port import FilesPort
from app.gateways.fixtures import read_yaml
from app.gateways.llm.gate import InProcessPriorityGate, LlmGate
from app.gateways.llm.metering import Metering
from app.gateways.llm.port import LlmPort
from app.gateways.tinvest.port import TInvestPort
from app.gateways.vectors.port import VectorStorePort
from app.gateways.web.cache import MeteredWebSearch
from app.gateways.web.port import WebSearchPort

type Closer = Callable[[], Awaitable[None]]


@dataclasses.dataclass(frozen=True)
class Gateways:
    tinvest: TInvestPort
    llm: LlmPort
    web: WebSearchPort  # budgets and web_cache around Tavily or its fake
    disclosure: DisclosurePort
    embeddings: EmbeddingsPort
    vectors: VectorStorePort
    files: FilesPort
    fetch: FetchPort
    gate: LlmGate
    metering: Metering


def fault_plan(settings: Settings) -> FaultPlan:
    """FAKE_FAULTS (dev and ci): a FaultPlan file for e2e runs."""
    if settings.FAKE_FAULTS is None:
        return FaultPlan()
    return FaultPlan.model_validate(read_yaml(settings.FAKE_FAULTS))


def _tinvest(settings: Settings, fake: dict[str, Any], closers: list[Closer]) -> TInvestPort:
    if settings.TINVEST_MODE == "fake":
        from app.gateways.tinvest.fake import FakeTInvest

        return FakeTInvest(**fake)
    from app.gateways.tinvest.real import RealTInvest

    adapter = RealTInvest(settings)
    closers.append(adapter.aclose)
    return adapter


def _llm(settings: Settings, fake: dict[str, Any]) -> LlmPort:
    if settings.LLM_MODE == "fake":
        from app.gateways.llm.fake import FakeLlm

        return FakeLlm(settings.LLM_MODELS, **fake)
    from app.gateways.llm.gigachat import GigaChatLlm

    return GigaChatLlm(settings)


def _web(settings: Settings, fake: dict[str, Any], closers: list[Closer]) -> WebSearchPort:
    if settings.WEB_MODE == "fake":
        from app.gateways.web.fake import FakeWebSearch

        return FakeWebSearch(**fake)
    from app.gateways.web.tavily import TavilyWebSearch

    adapter = TavilyWebSearch(settings)
    closers.append(adapter.aclose)
    return adapter


def _disclosure(
    settings: Settings, files: FilesPort, fake: dict[str, Any], closers: list[Closer]
) -> DisclosurePort:
    if settings.DISCLOSURE_MODE == "fake":
        from app.gateways.disclosure.fake import FakeDisclosure

        return FakeDisclosure(files, **fake)
    from app.gateways.disclosure.edisclosure.adapter import EDisclosure

    adapter = EDisclosure(settings, files)
    closers.append(adapter.aclose)
    return adapter


def _embeddings(settings: Settings, fake: dict[str, Any]) -> EmbeddingsPort:
    if settings.EMBEDDINGS_MODE == "fake":
        from app.gateways.embeddings.fake import FakeEmbeddings

        return FakeEmbeddings(**fake)
    from app.gateways.embeddings.fastembed import FastEmbedEmbeddings

    return FastEmbedEmbeddings(settings)


def _vectors(
    settings: Settings, dim: int, fake: dict[str, Any], closers: list[Closer]
) -> VectorStorePort:
    if settings.VECTORS_MODE == "memory":
        from app.gateways.vectors.memory import MemoryVectorStore

        return MemoryVectorStore(dim, **fake)
    from app.gateways.vectors.qdrant import QdrantVectorStore

    adapter = QdrantVectorStore(settings, dim)
    closers.append(adapter.aclose)
    return adapter


def _fetch(settings: Settings, fake: dict[str, Any], closers: list[Closer]) -> FetchPort:
    if settings.FETCH_MODE == "fake":
        from app.gateways.fetch.fake import FakeFetch

        return FakeFetch(**fake)
    from app.gateways.fetch.safe_httpx import SafeHttpxFetch

    adapter = SafeHttpxFetch()
    closers.append(adapter.aclose)
    return adapter


@asynccontextmanager
async def open_gateways(state: State) -> AsyncIterator[Gateways]:
    """Builds the clients of state.settings; closes the real ones on the way out."""
    settings: Settings = state.settings
    fake = {"plan": fault_plan(settings), "strict": settings.FAKE_STRICT}
    closers: list[Closer] = []

    def bind() -> Any:
        return state.engine  # read at call time: contract tests swap it for a connection

    files = LocalFiles(settings.DATA_DIR)
    embeddings = _embeddings(settings, fake)
    gate = InProcessPriorityGate(settings.LLM_MAX_CONCURRENCY, settings.LLM_QUEUE_TIMEOUT_S)
    try:
        yield Gateways(
            tinvest=_tinvest(settings, fake, closers),
            llm=_llm(settings, fake),
            web=MeteredWebSearch(_web(settings, fake, closers), bind, settings),
            disclosure=_disclosure(settings, files, fake, closers),
            embeddings=embeddings,
            vectors=_vectors(settings, embeddings.dense_dim(), fake, closers),
            files=files,
            fetch=_fetch(settings, fake, closers),
            gate=gate,
            metering=Metering(gate, bind, settings),
        )
    finally:
        for close in reversed(closers):
            await close()


@contextmanager
def override_gateways(state: State, **ports: Any) -> Iterator[Gateways]:
    """Swaps clients of the app for a test: `with override_gateways(app.state, web=...):`."""
    original: Gateways = state.gateways
    state.gateways = dataclasses.replace(original, **ports)
    try:
        yield state.gateways
    finally:
        state.gateways = original
