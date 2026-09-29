"""Broker connection DTOs (tech.md §6.3)."""

from datetime import date
from typing import Annotated, Literal

from pydantic import StringConstraints

from app.contracts.common import AccountStatus, AccountType, Contract, UtcDatetime

# Accounts go to the LLM and the UI only by alias (tech.md §3.5, §5.2).
AccountAlias = Annotated[str, StringConstraints(pattern=r"^acc[0-9]+$")]


class BrokerConnectIn(Contract):
    token: str


class BrokerAccountOut(Contract):
    alias: AccountAlias
    name: str
    type: AccountType
    status: AccountStatus
    opened_at: date | None
    is_hidden: bool


class BrokerConnectionOut(Contract):
    connected: bool
    status: Literal["active", "invalid"] | None
    token_hint: str | None  # the last 4 characters
    last_verified_at: UtcDatetime | None
    accounts: list[BrokerAccountOut]


class AccountPatchIn(Contract):
    is_hidden: bool
