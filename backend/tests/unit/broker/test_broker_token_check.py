"""The check of a new T-Invest token (tech.md §3.5, F-01 AC 2, 3, 7): only a token that reads
every account it reaches passes, and the token shows in no log line and no refusal."""

from typing import Literal

import pytest
from pydantic import SecretStr

from app.contracts.faults import FaultPlan, FaultRule
from app.contracts.tinvest import TAccount
from app.core.errors import AppError, TransientGatewayError
from app.core.logging import configure_logging
from app.domains.broker.service import read_only_accounts
from app.gateways.tinvest.fake import FakeTInvest, seed

TOKEN = SecretStr("t.f01-unit-token-7Hq2")


class Listed(FakeTInvest):
    """The T-Invest fake with a token that reaches the given accounts."""

    def __init__(self, *accounts: TAccount) -> None:
        super().__init__()
        self.accounts = list(accounts)

    async def get_accounts(self, token: SecretStr) -> list[TAccount]:
        return list(self.accounts)


def failing(rule: FaultRule) -> FakeTInvest:
    return FakeTInvest(plan=FaultPlan(rules=[rule.model_copy(update={"times": 100})]))


@pytest.fixture(autouse=True)
def _json_logs() -> None:
    configure_logging("DEBUG")


def assert_no_token(capsys: pytest.CaptureFixture[str], *texts: str) -> None:
    captured = capsys.readouterr()
    for text in (captured.out, captured.err, *texts):
        assert TOKEN.get_secret_value() not in text


async def test_a_read_only_token_gives_its_accounts(capsys: pytest.CaptureFixture[str]) -> None:
    found = await read_only_accounts(FakeTInvest(), TOKEN)

    assert found == seed().accounts
    assert_no_token(capsys)


@pytest.mark.parametrize("level", ["full_access", "no_access", "unspecified"])
async def test_an_account_that_is_not_read_only_refuses_the_token(
    capsys: pytest.CaptureFixture[str],
    level: Literal["full_access", "no_access", "unspecified"],
) -> None:
    [first, second] = seed().accounts
    tinvest = Listed(first, second.model_copy(update={"access_level": level}))

    with pytest.raises(AppError) as refused:
        await read_only_accounts(tinvest, TOKEN)

    assert refused.value.code == "token_not_read_only"
    assert_no_token(capsys, refused.value.message, str(refused.value.details))


async def test_a_token_tinvest_refuses_is_invalid(capsys: pytest.CaptureFixture[str]) -> None:
    tinvest = failing(FaultRule(method="get_accounts", mode="error", error_code="token_invalid"))

    with pytest.raises(AppError) as refused:
        await read_only_accounts(tinvest, TOKEN)

    assert refused.value.code == "token_invalid"
    assert_no_token(capsys, refused.value.message, str(refused.value.details))


async def test_a_token_without_accounts_is_invalid(capsys: pytest.CaptureFixture[str]) -> None:
    # Nothing to tell a read-only token by (§3.5): the token gets no place in the database.
    tinvest = failing(FaultRule(method="get_accounts", mode="empty"))

    with pytest.raises(AppError) as refused:
        await read_only_accounts(tinvest, TOKEN)

    assert refused.value.code == "token_invalid"
    assert_no_token(capsys, refused.value.message)


async def test_an_unavailable_tinvest_stays_a_gateway_failure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    tinvest = failing(FaultRule(method="get_accounts", mode="timeout"))

    with pytest.raises(TransientGatewayError) as failed:
        await read_only_accounts(tinvest, TOKEN)

    assert failed.value.code == "tinvest_unavailable"
    assert_no_token(capsys, repr(failed.value), str(failed.value))
