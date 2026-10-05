"""Fakes are the test seam of the ports (S1-09 AC 2, tech.md §8.1): valid input passes, input the
port contract forbids raises ContractViolation and leaves no recorded call."""

from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from langchain_core.messages import HumanMessage
from pydantic import SecretStr

from app.config import Settings
from app.contracts.llm import LlmCallCtx
from app.contracts.tinvest import TOperationsQuery
from app.contracts.vectors import ChunkQuery, SparseVec
from app.contracts.web import WebSearchQuery
from app.core.errors import ContractViolation
from app.gateways.disclosure.fake import FakeDisclosure
from app.gateways.embeddings.fake import FakeEmbeddings
from app.gateways.fakes import Fake
from app.gateways.fetch.fake import FakeFetch
from app.gateways.files.local import LocalFiles
from app.gateways.llm.fake import FakeLlm
from app.gateways.llm.metering import current_call
from app.gateways.tinvest.fake import FakeTInvest
from app.gateways.vectors.memory import MemoryVectorStore
from app.gateways.web.fake import FakeWebSearch

TOKEN = SecretStr("t.fake")
SBER = UUID("ab9bea9c-dda2-5b58-94a5-474347be4e9d")  # seed/tinvest/instruments.yaml
NOW = datetime(2026, 10, 2, tzinfo=UTC)
MODELS = Settings.model_construct().LLM_MODELS


def search(**changes: Any) -> WebSearchQuery:
    fields: dict[str, Any] = {
        "query": "сбербанк новости",
        "topic": "news",
        "depth": "basic",
        "time_range": None,
        "max_results": 5,
        "include_domains": [],
        "exclude_domains": [],
        "include_images": False,
    }
    return WebSearchQuery(**fields | changes)


def operations(**changes: Any) -> TOperationsQuery:
    fields: dict[str, Any] = {
        "account_id": "2000000001",
        "from_": datetime(2024, 1, 1, tzinfo=UTC),
        "to": NOW,
        "kinds": None,
        "cursor": None,
        "limit": 10,
    }
    return TOperationsQuery(**fields | changes)


def chunks(dim: int) -> ChunkQuery:
    return ChunkQuery(
        text="выручка",
        dense=[1.0] + [0.0] * (dim - 1),
        sparse=SparseVec(indices=[1], values=[1.0]),
        issuer_id=None,
        kinds=None,
        years=None,
        top_k=5,
    )


# port, method, valid arguments, the same call with garbage, what is wrong
CASES: list[tuple[str, str, dict[str, Any], dict[str, Any], str]] = [
    ("tinvest", "get_accounts", {"token": TOKEN}, {"token": "t.fake"}, "a bare string token"),
    (
        "tinvest",
        "get_portfolio",
        {"token": TOKEN, "account_id": "2000000001"},
        {"token": TOKEN, "account_id": 2000000001},
        "an int account id",
    ),
    (
        "tinvest",
        "get_operations",
        {"token": TOKEN, "q": operations()},
        {"token": TOKEN, "q": {"account_id": "2000000001"}},
        "a dict for the query",
    ),
    (
        "tinvest",
        "find_instruments",
        {"token": TOKEN, "query": "SBER", "limit": 5},
        {"token": TOKEN, "query": "SBER", "limit": 0},
        "a limit below one",
    ),
    (
        "tinvest",
        "get_instrument",
        {"token": TOKEN, "uid": SBER},
        {"token": TOKEN, "uid": str(SBER)},
        "a string uid",
    ),
    (
        "tinvest",
        "list_instruments",
        {"token": TOKEN, "kind": "shares"},
        {"token": TOKEN, "kind": "stocks"},
        "an unknown list",
    ),
    (
        "tinvest",
        "get_report_schedule",
        {"token": TOKEN, "instrument_uid": SBER, "from_": date(2026, 1, 1), "to": date(2027, 1, 1)},
        {"token": TOKEN, "instrument_uid": SBER, "from_": NOW, "to": date(2027, 1, 1)},
        "a datetime for a date",
    ),
    (
        "tinvest",
        "get_candles",
        {
            "token": TOKEN,
            "instrument_uid": SBER,
            "from_": datetime(2026, 9, 1, tzinfo=UTC),
            "to": NOW,
            "interval": "day",
        },
        {
            "token": TOKEN,
            "instrument_uid": SBER,
            "from_": datetime(2026, 9, 1),  # noqa: DTZ001 - the garbage under test
            "to": NOW,
            "interval": "day",
        },
        "a naive datetime",
    ),
    (
        "tinvest",
        "get_last_prices",
        {"token": TOKEN, "instrument_uids": [SBER]},
        {"token": TOKEN, "instrument_uids": SBER},
        "one uid for a list",
    ),
    ("web", "search", {"q": search()}, {"q": search().model_dump()}, "a dict for the query"),
    (
        "disclosure",
        "list_files",
        {"company_id": 3043, "section": "ras"},
        {"company_id": 3043, "section": "rsbu"},
        "an unknown section",
    ),
    ("disclosure", "get_company", {"company_id": 3043}, {"company_id": "3043"}, "a string id"),
    ("disclosure", "download", {"file_id": 1941660}, {"file_id": 1941660.0}, "a float id"),
    ("embeddings", "embed_passages", {"texts": ["выручка"]}, {"texts": "выручка"}, "one text"),
    ("embeddings", "sparse_query", {"text": "выручка"}, {"text": ["выручка"]}, "a list"),
    ("vectors", "search", {"q": chunks(384)}, {"q": chunks(384).model_dump()}, "a dict"),
    (
        "vectors",
        "delete_document",
        {"document_id": uuid4()},
        {"document_id": "doc"},
        "a string id",
    ),
    (
        "fetch",
        "fetch_image",
        {"url": "https://example.com/a.png", "max_bytes": 1024},
        {"url": "https://example.com/a.png", "max_bytes": 0},
        "no room for an image",
    ),
    (
        "llm",
        "count_tokens",
        {"texts": ["a"], "model_id": "GigaChat-2"},
        {"texts": ["a"], "model_id": 2},
        "an int model id",
    ),
]


@pytest.fixture
def fakes(tmp_path: Path) -> dict[str, Fake]:
    return {
        "tinvest": FakeTInvest(),
        "web": FakeWebSearch(),
        "disclosure": FakeDisclosure(LocalFiles(tmp_path)),
        "embeddings": FakeEmbeddings(),
        "vectors": MemoryVectorStore(384),
        "fetch": FakeFetch(),
        "llm": FakeLlm(MODELS),
    }


@pytest.mark.parametrize(
    ("port", "method", "valid", "garbage"),
    [case[:4] for case in CASES],
    ids=[f"{case[0]}.{case[1]}: {case[4]}" for case in CASES],
)
async def test_valid_input_passes_and_garbage_is_a_contract_violation(
    fakes: dict[str, Fake],
    port: str,
    method: str,
    valid: dict[str, Any],
    garbage: dict[str, Any],
) -> None:
    call: Callable[..., Any] = getattr(fakes[port], method)
    await call(**valid)
    recorded = len(fakes[port].calls)

    with pytest.raises(ContractViolation):
        await call(**garbage)
    assert len(fakes[port].calls) == recorded  # a refused call never reached the fake


async def test_a_vector_of_another_size_is_a_contract_violation() -> None:
    store = MemoryVectorStore(384)

    with pytest.raises(ContractViolation):
        await store.search(chunks(3))


def test_an_unknown_model_is_a_contract_violation(fakes: dict[str, Fake]) -> None:
    llm = fakes["llm"]
    assert isinstance(llm, FakeLlm)

    llm.chat_model("GigaChat-2-Max", streaming=True)
    with pytest.raises(ContractViolation):
        llm.chat_model("gpt-5", streaming=True)


def test_tool_choice_any_is_refused_as_gigachat_refuses_it(fakes: dict[str, Fake]) -> None:
    llm = fakes["llm"]
    assert isinstance(llm, FakeLlm)
    model = llm.chat_model("GigaChat-2", streaming=False)
    tool = {"type": "function", "function": {"name": "calc", "parameters": {"type": "object"}}}

    model.bind_tools([tool], tool_choice="auto")
    with pytest.raises(ContractViolation):
        model.bind_tools([tool], tool_choice="any")  # §8.3


async def test_a_model_called_past_metering_is_a_contract_violation(
    fakes: dict[str, Fake],
) -> None:
    llm = fakes["llm"]
    assert isinstance(llm, FakeLlm)
    model = llm.chat_model("GigaChat-2", streaming=False)
    ctx = LlmCallCtx(
        purpose="agent_step", priority="interactive", family="lite", model_id="GigaChat-2"
    )

    with pytest.raises(ContractViolation):
        await model.ainvoke([HumanMessage("Привет!")])  # §8.3: no ainvoke past metering
    token = current_call.set(ctx)  # what metering does around the call
    try:
        assert "Здравствуйте" in (await model.ainvoke([HumanMessage("Привет!")])).text
    finally:
        current_call.reset(token)


async def test_a_request_without_a_fixture_fails_only_in_strict_mode() -> None:
    query = search(query="запрос без фикстуры")

    with pytest.raises(ContractViolation):
        await FakeWebSearch(strict=True).search(query)
    assert (await FakeWebSearch(strict=False).search(query)).hits == []
