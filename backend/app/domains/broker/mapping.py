"""Accounts of T-Invest as rows of broker_accounts (tech.md §5.2): pure functions."""

from collections.abc import Mapping, Sequence
from datetime import date

from app.contracts.tinvest import TAccount

ALIAS_PREFIX = "acc"


def alias_number(alias: str) -> int:
    return int(alias.removeprefix(ALIAS_PREFIX))


def aliases(known: Mapping[str, str], accounts: Sequence[TAccount]) -> dict[str, str]:
    """The alias of every account T-Invest listed, by its id.

    `known` maps the ids of the stored accounts, hidden ones included, to their aliases. A known
    account keeps its alias; new ones take the numbers after the highest stored one by opening
    day, so no alias ever goes to a second account (§5.2).
    """
    found = {a.id: known[a.id] for a in accounts if a.id in known}
    new = sorted(
        (a for a in accounts if a.id not in known),
        key=lambda a: (a.opened_date or date.max, a.id),
    )
    highest = max((alias_number(alias) for alias in known.values()), default=0)
    for number, account in enumerate(new, highest + 1):
        found[account.id] = f"{ALIAS_PREFIX}{number}"
    return found


def account_values(account: TAccount) -> dict[str, object]:
    """The columns T-Invest owns; the alias and is_hidden belong to the connection."""
    return {
        "name": account.name,
        "type": account.type,
        "status": account.status,
        "opened_at": account.opened_date,
        "access_level": account.access_level,
    }
