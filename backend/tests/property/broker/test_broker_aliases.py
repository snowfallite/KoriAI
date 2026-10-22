"""Aliases of broker accounts (tech.md §5.2, F-01 AC 1 and 4) and the token as a user pastes it.

A known account keeps its alias in whatever order T-Invest lists the accounts; a new one takes the
next number after the highest alias the connection holds, hidden accounts included, by opening
day. No alias goes to a second account.
"""

import re
import string
from datetime import date

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.contracts.tinvest import TAccount
from app.core.errors import AppError
from app.domains.broker.mapping import aliases
from app.domains.broker.service import read_token

ALIAS = re.compile(r"acc[1-9][0-9]*")
VISIBLE_ASCII = "".join(chr(code) for code in range(0x21, 0x7F))
SPACES = " \t\r\n" + chr(0xA0)  # a paste from a page may bring a no-break space


def account(external_id: str, opened: date | None) -> TAccount:
    return TAccount(
        id=external_id,
        name=f"Счёт {external_id}",
        type="broker",
        status="open",
        opened_date=opened,
        access_level="read_only",
    )


def number(alias: str) -> int:
    return int(alias.removeprefix("acc"))


@st.composite
def connections(draw: st.DrawFn) -> tuple[dict[str, str], list[TAccount]]:
    """Stored aliases and the accounts a token lists: some known, some gone, some new."""
    ids = draw(st.lists(st.text(string.digits, min_size=1, max_size=10), unique=True, max_size=14))
    roles = [draw(st.sampled_from(["listed", "gone", "new"])) for _ in ids]
    stored = [i for i, role in zip(ids, roles, strict=True) if role != "new"]
    numbers = draw(
        st.lists(st.integers(1, 120), unique=True, min_size=len(stored), max_size=len(stored))
    )
    known = {i: f"acc{n}" for i, n in zip(stored, numbers, strict=True)}
    days = st.none() | st.dates(date(2000, 1, 1), date(2030, 12, 31))
    listed = [account(i, draw(days)) for i, role in zip(ids, roles, strict=True) if role != "gone"]
    return known, draw(st.permutations(listed))


@given(connections())
def test_a_known_account_keeps_its_alias(connection: tuple[dict[str, str], list[TAccount]]) -> None:
    known, listed = connection

    found = aliases(known, listed)

    assert found.keys() == {a.id for a in listed}
    for a in listed:
        if a.id in known:
            assert found[a.id] == known[a.id]


@given(connections(), st.data())
def test_the_order_of_the_list_changes_no_alias(
    connection: tuple[dict[str, str], list[TAccount]], data: st.DataObject
) -> None:
    known, listed = connection

    assert aliases(known, data.draw(st.permutations(listed))) == aliases(known, listed)


@given(connections())
def test_new_accounts_take_the_numbers_after_the_highest_by_opening_day(
    connection: tuple[dict[str, str], list[TAccount]],
) -> None:
    known, listed = connection
    highest = max((number(alias) for alias in known.values()), default=0)
    new = sorted(
        (a for a in listed if a.id not in known),
        key=lambda a: (a.opened_date or date.max, a.id),
    )

    found = aliases(known, listed)

    assert [found[a.id] for a in new] == [
        f"acc{n}" for n in range(highest + 1, highest + 1 + len(new))
    ]


@given(connections())
def test_no_alias_goes_to_a_second_account(
    connection: tuple[dict[str, str], list[TAccount]],
) -> None:
    known, listed = connection

    found = aliases(known, listed)
    taken = set(known.values())

    assert len(set(found.values())) == len(found)
    assert all(ALIAS.fullmatch(alias) for alias in found.values())
    for external_id, alias in found.items():
        # An alias of another account, a hidden one included, is never given again.
        assert alias not in taken or known.get(external_id) == alias


def test_a_first_connection_numbers_the_accounts_by_opening_day() -> None:
    listed = [
        account("2000000002", date(2023, 1, 20)),
        account("2000000003", None),
        account("2000000001", date(2021, 3, 15)),
    ]

    assert aliases({}, listed) == {
        "2000000001": "acc1",
        "2000000002": "acc2",
        "2000000003": "acc3",
    }


@given(
    st.text(VISIBLE_ASCII, min_size=1, max_size=512),
    st.text(SPACES, max_size=4),
    st.text(SPACES, max_size=4),
)
def test_a_pasted_token_loses_the_spaces_around_it(token: str, before: str, after: str) -> None:
    assert read_token(before + token + after).get_secret_value() == token


@given(st.text(SPACES, max_size=6))
def test_an_empty_paste_asks_for_the_token(blank: str) -> None:
    with pytest.raises(AppError) as refused:
        read_token(blank)

    assert refused.value.code == "validation_error"


@given(
    st.text(VISIBLE_ASCII, max_size=40),
    st.characters(exclude_characters=VISIBLE_ASCII),
    st.text(VISIBLE_ASCII, max_size=40),
)
def test_a_token_with_a_character_no_header_carries_is_refused(
    head: str, odd: str, tail: str
) -> None:
    pasted = f"t{head}{odd}{tail}t"

    with pytest.raises(AppError) as refused:
        read_token(pasted)

    assert refused.value.code == "token_invalid"
    assert pasted not in refused.value.message


def test_a_token_longer_than_any_tinvest_gives_is_refused() -> None:
    with pytest.raises(AppError) as refused:
        read_token("t." + "a" * 600)

    assert refused.value.code == "token_invalid"


@given(st.text())
def test_any_paste_gives_a_token_or_a_refusal(pasted: str) -> None:
    try:
        token = read_token(pasted)
    except AppError as refused:
        assert refused.code in {"validation_error", "token_invalid"}
    else:
        assert token.get_secret_value() == pasted.strip()
