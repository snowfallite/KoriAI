"""The T-Invest token at rest (tech.md §3.5, AD-10): AES-256-GCM with the user id as AAD."""

import uuid

import pytest
from pydantic import SecretBytes, SecretStr

from app.core.crypto import NONCE_BYTES, TokenKeyError, open_token, seal_token, token_hint

TOKEN = SecretStr("t.read-only-token-4242")
K1 = SecretBytes(bytes(range(32)))
K2 = SecretBytes(bytes(range(32, 64)))


def test_a_sealed_token_opens_for_its_user_only() -> None:
    owner, stranger = uuid.uuid4(), uuid.uuid4()
    sealed = seal_token(TOKEN, owner, {"k1": K1}, "k1")

    assert open_token(sealed, owner, {"k1": K1}).get_secret_value() == TOKEN.get_secret_value()
    with pytest.raises(TokenKeyError):
        open_token(sealed, stranger, {"k1": K1})


def test_the_active_key_seals_with_a_fresh_twelve_byte_nonce() -> None:
    user = uuid.uuid4()
    keys = {"k1": K1, "k2": K2}

    first, second = (seal_token(TOKEN, user, keys, "k2") for _ in range(2))

    assert (first.key_id, len(first.nonce)) == ("k2", NONCE_BYTES)
    assert first.nonce != second.nonce
    assert first.ciphertext != second.ciphertext
    assert TOKEN.get_secret_value().encode() not in first.ciphertext


def test_an_old_key_still_opens_its_tokens_after_the_active_key_changes() -> None:
    user = uuid.uuid4()
    sealed = seal_token(TOKEN, user, {"k1": K1}, "k1")

    opened = open_token(sealed, user, {"k1": K1, "k2": K2})

    assert opened.get_secret_value() == TOKEN.get_secret_value()


def test_a_missing_key_refuses_without_echoing_secrets() -> None:
    user = uuid.uuid4()
    sealed = seal_token(TOKEN, user, {"k1": K1}, "k1")

    with pytest.raises(TokenKeyError) as no_active:
        seal_token(TOKEN, user, {}, "k1")
    with pytest.raises(TokenKeyError) as dropped:
        open_token(sealed, user, {"k2": K2})

    for error in (no_active.value, dropped.value):
        assert "k1" in str(error)
        assert TOKEN.get_secret_value() not in str(error)
        assert K1.get_secret_value().hex() not in str(error)


def test_a_key_of_another_length_is_refused() -> None:
    with pytest.raises(TokenKeyError):
        seal_token(TOKEN, uuid.uuid4(), {"k1": SecretBytes(bytes(16))}, "k1")


@pytest.mark.parametrize(
    ("token", "hint"),
    [("t.read-only-token-4242", "4242"), ("abcd", "abcd"), ("xyz", "xyz")],
)
def test_the_hint_is_the_last_four_characters(token: str, hint: str) -> None:
    assert token_hint(SecretStr(token)) == hint
