"""The broker connection over HTTP (F-01 AC 1-8; tech.md §3.5, §5.2, §6.3).

The T-Invest fake lists the two read-only accounts of seed/tinvest/accounts.yaml for any token; a
test that needs other accounts swaps in a port that lists them.
"""

import json
from collections.abc import Awaitable, Callable
from datetime import date, timedelta
from typing import Any, Literal
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr, TypeAdapter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from app.contracts.api.auth import MeOut
from app.contracts.api.broker import BrokerAccountOut, BrokerConnectionOut
from app.contracts.api.portfolio import PortfolioOut
from app.contracts.common import ErrorOut
from app.contracts.faults import FaultRule
from app.contracts.tinvest import TAccount
from app.core import time
from app.core.crypto import SealedToken, TokenKeyError, open_token
from app.db.schema.broker import BrokerAccount, BrokerConnection
from app.db.schema.users import AuditEvent
from app.gateways.factory import Gateways, override_gateways
from app.gateways.fakes import Fake
from app.gateways.fixtures import SEED, load
from tests.support.api import sign_up
from tests.support.seed import TOKEN_KEYS

TOKEN = "t.f01-contract-token-Kx9a"
NEW_TOKEN = "t.f01-contract-token-Zq4b"
NOT_CONNECTED = BrokerConnectionOut(
    connected=False, status=None, token_hint=None, last_verified_at=None, accounts=[]
)

type Faults = Any  # tests/support/faults.py: faults(*rules) -> FaultPlan
type Level = Literal["full_access", "no_access", "unspecified"]


class Listed:
    """A T-Invest port whose token reaches the given accounts."""

    def __init__(self, *accounts: TAccount) -> None:
        self.accounts = list(accounts)

    async def get_accounts(self, token: SecretStr) -> list[TAccount]:
        return list(self.accounts)


@pytest.fixture(autouse=True)
def _token_keys(app: FastAPI) -> None:
    # The key the seed seals the demo token with (tests/support/seed.py).
    app.state.settings = app.state.settings.model_copy(update={"TINVEST_TOKEN_KEYS": TOKEN_KEYS})


def seed_accounts() -> list[TAccount]:
    return load(SEED / "tinvest" / "accounts.yaml", TypeAdapter(list[TAccount]))


def opened(external_id: str, day: date | None, name: str | None = None) -> TAccount:
    return TAccount(
        id=external_id,
        name=name or f"Счёт {external_id}",
        type="broker",
        status="open",
        opened_date=day,
        access_level="read_only",
    )


def with_level(level: Level) -> Listed:
    """The seed accounts with the second one reachable at another level than read-only."""
    [first, second] = seed_accounts()
    return Listed(first, second.model_copy(update={"access_level": level}))


async def connect(api: httpx.AsyncClient, token: str) -> httpx.Response:
    return await api.put("/api/broker/connection", json={"token": token})


async def verify(api: httpx.AsyncClient) -> httpx.Response:
    return await api.post("/api/broker/connection/verify")


def connection_of(reply: httpx.Response) -> BrokerConnectionOut:
    assert reply.status_code == 200, reply.text
    return BrokerConnectionOut.model_validate(reply.json())


def account_of(reply: httpx.Response) -> BrokerAccountOut:
    assert reply.status_code == 200, reply.text
    return BrokerAccountOut.model_validate(reply.json())


def error_of(reply: httpx.Response, status: int) -> ErrorOut:
    assert reply.status_code == status, reply.text
    return ErrorOut.model_validate(reply.json())


def shown(found: BrokerConnectionOut) -> list[tuple[str, str, bool]]:
    return [(a.alias, a.name, a.is_hidden) for a in found.accounts]


async def user_of(api: httpx.AsyncClient) -> UUID:
    return MeOut.model_validate((await api.get("/api/auth/me")).json()).user.id


def db(app: FastAPI) -> AsyncConnection:
    conn: AsyncConnection = app.state.engine  # the test transaction (tests/support/api.py)
    return conn


type Rows = list[dict[str, Any]]


async def snapshot(app: FastAPI, user_id: UUID) -> tuple[Rows, Rows]:
    """Every column of the user's connection and accounts, to compare before and after."""
    connections, accounts = BrokerConnection.__table__, BrokerAccount.__table__
    rows = await db(app).execute(select(connections).where(connections.c.user_id == user_id))
    found = [dict(row) for row in rows.mappings()]
    query = (
        select(accounts)
        .where(accounts.c.connection_id.in_([row["id"] for row in found]))
        .order_by(accounts.c.alias)
    )
    return found, [dict(row) for row in (await db(app).execute(query)).mappings()]


async def audit(app: FastAPI, user_id: UUID) -> list[tuple[str, str, dict[str, Any]]]:
    rows = await db(app).execute(
        select(AuditEvent.kind, AuditEvent.ip, AuditEvent.meta)
        .where(AuditEvent.user_id == user_id, AuditEvent.kind.startswith("broker_"))
        .order_by(AuditEvent.id)
    )
    return [(kind, str(ip), meta) for kind, ip, meta in rows]


def tinvest_calls(app: FastAPI) -> list[str]:
    gateways: Gateways = app.state.gateways
    assert isinstance(gateways.tinvest, Fake)
    return [call.method for call in gateways.tinvest.calls]


# AC 1: a read-only token


async def test_a_read_only_token_connects_with_its_accounts_by_opening_day(
    user_api: httpx.AsyncClient,
) -> None:
    found = connection_of(await connect(user_api, TOKEN))

    assert (found.connected, found.status, found.token_hint) == (True, "active", TOKEN[-4:])
    assert found.last_verified_at is not None
    by_opening = sorted(seed_accounts(), key=lambda a: a.opened_date or date.max)
    assert found.accounts == [
        BrokerAccountOut(
            alias=f"acc{n}",
            name=a.name,
            type=a.type,
            status=a.status,
            opened_at=a.opened_date,
            is_hidden=False,
        )
        for n, a in enumerate(by_opening, 1)
    ]
    assert connection_of(await user_api.get("/api/broker/connection")) == found
    me = MeOut.model_validate((await user_api.get("/api/auth/me")).json())
    assert me.broker == found


async def test_the_token_is_kept_sealed_for_its_user_only(
    app: FastAPI, user_api: httpx.AsyncClient
) -> None:
    # A paste brings spaces and a line break around the token.
    await connect(user_api, f"  {TOKEN}\n")
    user_id = await user_of(user_api)

    [row], _ = await snapshot(app, user_id)
    sealed = SealedToken(row["token_ciphertext"], row["token_nonce"], row["token_key_id"])
    keys = app.state.settings.TINVEST_TOKEN_KEYS
    assert TOKEN.encode() not in row["token_ciphertext"]
    assert len(row["token_nonce"]) == 12
    assert row["token_key_id"] == app.state.settings.TINVEST_TOKEN_ACTIVE_KEY
    assert row["token_hint"] == TOKEN[-4:]
    assert open_token(sealed, user_id, keys).get_secret_value() == TOKEN
    # The user id is the AAD (§3.5): the row opens for nobody else.
    with pytest.raises(TokenKeyError):
        open_token(sealed, uuid4(), keys)


# AC 2, 3: refused tokens


@pytest.mark.parametrize("level", ["full_access", "no_access", "unspecified"])
async def test_a_token_that_does_more_than_read_is_refused_and_nothing_is_kept(
    app: FastAPI, user_api: httpx.AsyncClient, level: Level
) -> None:
    with override_gateways(app.state, tinvest=with_level(level)):
        reply = await connect(user_api, TOKEN)

    assert error_of(reply, 422).code == "token_not_read_only"
    user_id = await user_of(user_api)
    assert await snapshot(app, user_id) == ([], [])
    assert await audit(app, user_id) == []


async def test_a_token_tinvest_refuses_is_invalid_and_nothing_is_kept(
    app: FastAPI, user_api: httpx.AsyncClient, faults: Faults
) -> None:
    faults(FaultRule(method="get_accounts", mode="error", error_code="token_invalid"))

    reply = await connect(user_api, TOKEN)

    refused = error_of(reply, 422)
    assert refused.code == "token_invalid"
    assert refused.message
    user_id = await user_of(user_api)
    assert await snapshot(app, user_id) == ([], [])
    assert await audit(app, user_id) == []


async def test_a_refused_token_leaves_the_connection_as_it_was(
    app: FastAPI, user_api: httpx.AsyncClient, faults: Faults
) -> None:
    await connect(user_api, TOKEN)
    user_id = await user_of(user_api)
    before = await snapshot(app, user_id)

    with override_gateways(app.state, tinvest=with_level("full_access")):
        not_read_only = await connect(user_api, NEW_TOKEN)
    faults(FaultRule(method="get_accounts", mode="error", error_code="token_invalid"))
    refused = await connect(user_api, NEW_TOKEN)
    faults(FaultRule(method="get_accounts", mode="timeout", times=100))
    unavailable = await connect(user_api, NEW_TOKEN)

    assert error_of(not_read_only, 422).code == "token_not_read_only"
    assert error_of(refused, 422).code == "token_invalid"
    assert error_of(unavailable, 503).code == "tinvest_unavailable"
    assert await snapshot(app, user_id) == before


async def test_a_busy_tinvest_answers_503_with_retry_after(
    user_api: httpx.AsyncClient, faults: Faults
) -> None:
    faults(FaultRule(method="get_accounts", mode="rate_limit", latency_ms=20_000, times=100))

    reply = await connect(user_api, TOKEN)

    assert error_of(reply, 503).code == "tinvest_rate_limited"
    assert reply.headers["retry-after"] == "20"


@pytest.mark.parametrize(
    ("pasted", "code"),
    [
        ("", "validation_error"),
        (" \n\t", "validation_error"),
        ("t.токен", "token_invalid"),
        ("t.two words", "token_invalid"),
        ("t." + "a" * 600, "token_invalid"),
    ],
)
async def test_what_can_be_no_token_never_reaches_tinvest(
    app: FastAPI, user_api: httpx.AsyncClient, pasted: str, code: str
) -> None:
    reply = await connect(user_api, pasted)

    assert error_of(reply, 422).code == code
    assert "get_accounts" not in tinvest_calls(app)


# AC 4: aliases


async def test_a_new_token_keeps_the_aliases_of_known_accounts(
    app: FastAPI, user_api: httpx.AsyncClient
) -> None:
    first, second = opened("100", date(2021, 3, 15)), opened("200", date(2023, 1, 20))
    # Opened before both, the third account comes with the second token: it takes the next number.
    third = opened("300", date(2020, 6, 1))

    with override_gateways(app.state, tinvest=Listed(second, first)):
        before = connection_of(await connect(user_api, TOKEN))
    renamed = first.model_copy(update={"name": "Основной"})
    with override_gateways(app.state, tinvest=Listed(third, renamed, second)):
        after = connection_of(await connect(user_api, NEW_TOKEN))

    assert shown(before) == [("acc1", "Счёт 100", False), ("acc2", "Счёт 200", False)]
    assert shown(after) == [
        ("acc1", "Основной", False),
        ("acc2", "Счёт 200", False),
        ("acc3", "Счёт 300", False),
    ]


async def test_an_account_a_new_token_misses_stays_hidden_under_its_alias(
    app: FastAPI, user_api: httpx.AsyncClient
) -> None:
    first, second = opened("100", date(2021, 3, 15)), opened("200", date(2023, 1, 20))
    third = opened("300", None)

    with override_gateways(app.state, tinvest=Listed(first, second)):
        await connect(user_api, TOKEN)
    # A token of one account (developer.tbank.ru: GetAccounts lists what the token reaches).
    with override_gateways(app.state, tinvest=Listed(second)):
        narrower = connection_of(await connect(user_api, NEW_TOKEN))
    with override_gateways(app.state, tinvest=Listed(third, second, first)):
        wider = connection_of(await connect(user_api, TOKEN))

    assert shown(narrower) == [("acc1", "Счёт 100", True), ("acc2", "Счёт 200", False)]
    # The account comes back under its alias and stays hidden until the user shows it.
    assert shown(wider) == [
        ("acc1", "Счёт 100", True),
        ("acc2", "Счёт 200", False),
        ("acc3", "Счёт 300", False),
    ]


async def test_a_new_token_keeps_the_accounts_the_user_hid(demo_api: httpx.AsyncClient) -> None:
    await demo_api.patch("/api/broker/accounts/acc1", json={"is_hidden": True})

    found = connection_of(await connect(demo_api, NEW_TOKEN))

    assert [(a.alias, a.is_hidden) for a in found.accounts] == [("acc1", True), ("acc2", False)]


# AC 5: the check


async def test_a_check_moves_the_time_of_the_last_check(
    user_api: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    connected = connection_of(await connect(user_api, TOKEN))
    later = time.now() + timedelta(hours=3)
    monkeypatch.setattr(time, "now", lambda: later)

    checked = connection_of(await verify(user_api))

    assert connected.last_verified_at is not None
    assert connected.last_verified_at < later
    assert checked.last_verified_at == later
    assert (checked.status, checked.accounts) == ("active", connected.accounts)


async def test_a_revoked_token_turns_the_connection_invalid(
    app: FastAPI, user_api: httpx.AsyncClient, faults: Faults
) -> None:
    await connect(user_api, TOKEN)
    user_id = await user_of(user_api)
    faults(FaultRule(method="get_accounts", mode="error", error_code="token_invalid"))

    revoked = connection_of(await verify(user_api))
    [row], accounts = await snapshot(app, user_id)

    assert (revoked.connected, revoked.status, revoked.token_hint) == (True, "invalid", TOKEN[-4:])
    assert (row["status"], row["last_error_code"]) == ("invalid", "token_invalid")
    assert len(accounts) == len(seed_accounts())

    faults()  # T-Invest takes the token again
    again = connection_of(await verify(user_api))
    [row], _ = await snapshot(app, user_id)

    assert again.status == "active"
    assert row["last_error_code"] is None


async def test_a_check_that_finds_more_than_reading_turns_the_connection_invalid(
    app: FastAPI, user_api: httpx.AsyncClient
) -> None:
    await connect(user_api, TOKEN)

    with override_gateways(app.state, tinvest=with_level("full_access")):
        checked = connection_of(await verify(user_api))

    [row], _ = await snapshot(app, await user_of(user_api))
    assert checked.status == "invalid"
    assert row["last_error_code"] == "token_not_read_only"


async def test_a_check_brings_new_accounts_and_hides_missing_ones(
    app: FastAPI, user_api: httpx.AsyncClient
) -> None:
    first, second = opened("100", date(2021, 3, 15)), opened("200", date(2023, 1, 20))
    third = opened("300", date(2024, 2, 1))
    with override_gateways(app.state, tinvest=Listed(first, second)):
        await connect(user_api, TOKEN)

    with override_gateways(app.state, tinvest=Listed(third, second)):
        checked = connection_of(await verify(user_api))

    assert checked.status == "active"
    assert shown(checked) == [
        ("acc1", "Счёт 100", True),
        ("acc2", "Счёт 200", False),
        ("acc3", "Счёт 300", False),
    ]


async def test_a_check_while_tinvest_is_down_changes_nothing(
    app: FastAPI, user_api: httpx.AsyncClient, faults: Faults
) -> None:
    await connect(user_api, TOKEN)
    user_id = await user_of(user_api)
    before = await snapshot(app, user_id)
    faults(FaultRule(method="get_accounts", mode="timeout", times=100))

    reply = await verify(user_api)

    assert error_of(reply, 503).code == "tinvest_unavailable"
    assert await snapshot(app, user_id) == before


async def test_a_check_without_a_connection_is_a_conflict(user_api: httpx.AsyncClient) -> None:
    reply = await verify(user_api)

    assert error_of(reply, 409).code == "broker_not_connected"


# AC 6: disconnecting


async def test_disconnecting_drops_the_token_and_the_accounts(
    app: FastAPI, demo_api: httpx.AsyncClient
) -> None:
    user_id = await user_of(demo_api)

    reply = await demo_api.delete("/api/broker/connection")

    assert reply.status_code == 204
    assert await snapshot(app, user_id) == ([], [])
    assert connection_of(await demo_api.get("/api/broker/connection")) == NOT_CONNECTED
    portfolio = await demo_api.get("/api/portfolio")
    assert error_of(portfolio, 409).code == "broker_not_connected"
    # Nothing is left to drop the second time.
    assert (await demo_api.delete("/api/broker/connection")).status_code == 204


async def test_a_user_without_a_broker_sees_no_connection(user_api: httpx.AsyncClient) -> None:
    assert connection_of(await user_api.get("/api/broker/connection")) == NOT_CONNECTED


# AC 8: hidden accounts


async def test_a_hidden_account_leaves_the_portfolio_until_shown_again(
    demo_api: httpx.AsyncClient,
) -> None:
    [_, iis] = sorted(seed_accounts(), key=lambda a: a.opened_date or date.max)

    hidden = account_of(await demo_api.patch("/api/broker/accounts/acc2", json={"is_hidden": True}))
    without = PortfolioOut.model_validate((await demo_api.get("/api/portfolio")).json())
    back = account_of(await demo_api.patch("/api/broker/accounts/acc2", json={"is_hidden": False}))
    again = PortfolioOut.model_validate((await demo_api.get("/api/portfolio")).json())

    assert hidden == BrokerAccountOut(
        alias="acc2",
        name=iis.name,
        type=iis.type,
        status=iis.status,
        opened_at=iis.opened_date,
        is_hidden=True,
    )
    assert [a.alias for a in without.accounts] == ["acc1"]
    assert back == hidden.model_copy(update={"is_hidden": False})
    assert [a.alias for a in again.accounts] == ["acc1", "acc2"]


@pytest.mark.parametrize("alias", ["acc9", "acc", "anything"])
async def test_an_account_the_user_does_not_have_is_not_found(
    demo_api: httpx.AsyncClient, alias: str
) -> None:
    reply = await demo_api.patch(f"/api/broker/accounts/{alias}", json={"is_hidden": True})

    assert error_of(reply, 404).code == "not_found"


async def test_the_account_of_another_user_is_not_found(
    demo_api: httpx.AsyncClient,
    new_client: Callable[[], httpx.AsyncClient],
    make_invite: Callable[[], Awaitable[str]],
) -> None:
    async with new_client() as stranger:
        await sign_up(stranger, await make_invite())
        reply = await stranger.patch("/api/broker/accounts/acc1", json={"is_hidden": True})

    assert error_of(reply, 404).code == "not_found"
    demo = connection_of(await demo_api.get("/api/broker/connection"))
    assert not any(a.is_hidden for a in demo.accounts)


# AC 7 and the audit


async def test_the_token_shows_in_no_answer_log_or_audit(
    app: FastAPI,
    user_api: httpx.AsyncClient,
    faults: Faults,
    capsys: pytest.CaptureFixture[str],
) -> None:
    replies = [await connect(user_api, TOKEN)]
    with override_gateways(app.state, tinvest=with_level("full_access")):
        replies.append(await connect(user_api, NEW_TOKEN))
    faults(FaultRule(method="get_accounts", mode="error", error_code="token_invalid"))
    replies += [await connect(user_api, NEW_TOKEN), await verify(user_api)]
    faults(FaultRule(method="get_accounts", mode="timeout", times=100))
    replies += [await connect(user_api, NEW_TOKEN), await verify(user_api)]
    faults()
    replies += [
        await verify(user_api),
        await user_api.patch("/api/broker/accounts/acc1", json={"is_hidden": True}),
        await user_api.get("/api/broker/connection"),
        await user_api.get("/api/auth/me"),
        await user_api.delete("/api/broker/connection"),
    ]
    user_id = await user_of(user_api)
    logged = capsys.readouterr()
    metas = json.dumps([meta for _, _, meta in await audit(app, user_id)], ensure_ascii=False)

    assert "request_finished" in logged.out  # the logs did land here
    for secret in (TOKEN, NEW_TOKEN):
        assert secret not in logged.out + logged.err
        assert secret not in metas
        for reply in replies:
            assert secret not in reply.text
            assert secret not in str(reply.headers)


async def test_the_audit_keeps_the_broker_events(
    app: FastAPI, user_api: httpx.AsyncClient, faults: Faults
) -> None:
    await connect(user_api, TOKEN)
    await connect(user_api, NEW_TOKEN)
    faults(FaultRule(method="get_accounts", mode="error", error_code="token_invalid"))
    await verify(user_api)
    await user_api.delete("/api/broker/connection")

    accounts = len(seed_accounts())
    assert await audit(app, await user_of(user_api)) == [
        ("broker_connected", "127.0.0.1", {"accounts": accounts, "replaced": False}),
        ("broker_connected", "127.0.0.1", {"accounts": accounts, "replaced": True}),
        ("broker_verify_failed", "127.0.0.1", {"code": "token_invalid"}),
        ("broker_disconnected", "127.0.0.1", {}),
    ]
