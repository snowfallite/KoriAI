"""Fakes run the FaultPlan of tech.md §8.1: which calls break, how, and what they record."""

import time
from uuid import UUID

import pytest
from pydantic import SecretStr

from app.contracts.faults import FaultPlan, FaultRule
from app.contracts.vectors import ChunkQuery, SparseVec
from app.contracts.web import WebSearchQuery
from app.core.errors import (
    GatewayError,
    PermanentGatewayError,
    QuotaExhaustedError,
    TransientGatewayError,
)
from app.gateways.fakes import RecordedCall
from app.gateways.tinvest.fake import FakeTInvest
from app.gateways.vectors.memory import MemoryVectorStore
from app.gateways.web.fake import FakeWebSearch

TOKEN = SecretStr("t.fake")
SBER = UUID("ab9bea9c-dda2-5b58-94a5-474347be4e9d")
QUERY = WebSearchQuery(
    query="сбербанк новости",
    topic="news",
    depth="basic",
    time_range=None,
    max_results=5,
    include_domains=[],
    exclude_domains=[],
    include_images=False,
)


def tinvest(*rules: FaultRule) -> FakeTInvest:
    return FakeTInvest(plan=FaultPlan(rules=list(rules)))


async def outcome(fake: FakeTInvest) -> str:
    try:
        await fake.get_accounts(TOKEN)
    except GatewayError as error:
        return error.code
    return "ok"


async def test_a_rule_breaks_its_window_of_calls() -> None:
    fake = tinvest(FaultRule(method="get_accounts", mode="error", times=2, after_calls=1))

    assert [await outcome(fake) for _ in range(4)] == [
        "ok",
        "tinvest_unavailable",
        "tinvest_unavailable",
        "ok",
    ]


async def test_match_picks_the_calls_by_their_arguments() -> None:
    fake = tinvest(
        FaultRule(
            method="get_portfolio",
            mode="error",
            error_code="not_found",
            times=10,
            match={"account_id": "2000000002"},
        )
    )

    assert (await fake.get_portfolio(TOKEN, "2000000001")).account_id == "2000000001"
    with pytest.raises(PermanentGatewayError):
        await fake.get_portfolio(TOKEN, "2000000002")


@pytest.mark.parametrize(
    ("rule", "error", "code", "retry_after_s"),
    [
        (
            FaultRule(method="get_accounts", mode="timeout"),
            TransientGatewayError,
            "tinvest_unavailable",
            None,
        ),
        (
            FaultRule(method="get_accounts", mode="rate_limit", latency_ms=1500),
            TransientGatewayError,
            "tinvest_rate_limited",
            1.5,
        ),
        (
            FaultRule(method="get_accounts", mode="error", error_code="token_invalid"),
            PermanentGatewayError,
            "token_invalid",
            None,
        ),
        (
            FaultRule(method="get_accounts", mode="error"),
            TransientGatewayError,
            "tinvest_unavailable",
            None,
        ),
    ],
    ids=["timeout", "rate limit", "permanent error", "default error"],
)
async def test_a_failure_is_what_the_real_adapter_raises(
    rule: FaultRule, error: type[GatewayError], code: str, retry_after_s: float | None
) -> None:
    with pytest.raises(error) as raised:
        await tinvest(rule).get_accounts(TOKEN)

    assert (raised.value.code, raised.value.retry_after_s) == (code, retry_after_s)


async def test_a_quota_code_raises_quota_exhausted() -> None:
    fake = FakeWebSearch(
        plan=FaultPlan(
            rules=[FaultRule(method="search", mode="error", error_code="web_credits_exhausted")]
        )
    )

    with pytest.raises(QuotaExhaustedError):
        await fake.search(QUERY)


async def test_empty_answers_with_nothing_or_not_found() -> None:
    fake = tinvest(
        FaultRule(method="get_accounts", mode="empty"),
        FaultRule(method="get_instrument", mode="empty"),
    )

    assert await fake.get_accounts(TOKEN) == []
    with pytest.raises(PermanentGatewayError) as missing:
        await fake.get_instrument(TOKEN, SBER)
    assert missing.value.code == "not_found"


async def test_latency_slows_the_call_down() -> None:
    fake = tinvest(FaultRule(method="get_accounts", mode="latency", latency_ms=50))

    started = time.monotonic()
    await fake.get_accounts(TOKEN)

    assert time.monotonic() - started >= 0.045


async def test_a_qualified_name_breaks_only_its_port() -> None:
    plan = FaultPlan(rules=[FaultRule(method="vectors.search", mode="error", times=5)])
    web, store = FakeWebSearch(plan=plan), MemoryVectorStore(384, plan=plan)
    query = ChunkQuery(
        text="q",
        dense=[1.0] + [0.0] * 383,
        sparse=SparseVec(indices=[], values=[]),
        issuer_id=None,
        kinds=None,
        years=None,
        top_k=1,
    )

    assert (await web.search(QUERY)).hits
    with pytest.raises(TransientGatewayError):
        await store.search(query)


async def test_calls_are_recorded_with_their_defaults() -> None:
    fake = tinvest()

    await fake.find_instruments(TOKEN, "SBER")

    assert fake.calls == [
        RecordedCall("find_instruments", {"token": TOKEN, "query": "SBER", "limit": 20})
    ]
