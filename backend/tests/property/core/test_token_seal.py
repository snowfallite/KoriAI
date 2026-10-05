"""AES-256-GCM of the T-Invest token (tech.md §3.5): a round trip for its user, nothing else."""

import uuid
from dataclasses import replace

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st
from pydantic import SecretBytes, SecretStr

from app.core.crypto import SealedToken, TokenKeyError, open_token, seal_token

tokens = st.text(min_size=1, max_size=200).map(SecretStr)
keys = st.binary(min_size=32, max_size=32).map(SecretBytes)
key_ids = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=8)


@given(tokens, st.uuids(), keys, key_ids)
def test_the_token_survives_the_round_trip(
    token: SecretStr, user: uuid.UUID, key: SecretBytes, key_id: str
) -> None:
    sealed = seal_token(token, user, {key_id: key}, key_id)

    assert open_token(sealed, user, {key_id: key}).get_secret_value() == token.get_secret_value()


@given(tokens, st.uuids(), st.uuids(), keys)
def test_another_user_never_opens_the_token(
    token: SecretStr, owner: uuid.UUID, stranger: uuid.UUID, key: SecretBytes
) -> None:
    assume(owner != stranger)
    sealed = seal_token(token, owner, {"k1": key}, "k1")

    with pytest.raises(TokenKeyError):
        open_token(sealed, stranger, {"k1": key})


@given(tokens, st.uuids(), keys, st.data())
def test_a_changed_bit_of_the_ciphertext_or_nonce_is_refused(
    token: SecretStr, user: uuid.UUID, key: SecretBytes, data: st.DataObject
) -> None:
    sealed = seal_token(token, user, {"k1": key}, "k1")
    field = data.draw(st.sampled_from(["ciphertext", "nonce"]))
    value: bytes = getattr(sealed, field)
    bit = data.draw(st.integers(0, len(value) * 8 - 1))
    flipped = bytearray(value)
    flipped[bit // 8] ^= 1 << (bit % 8)
    changed: SealedToken = (
        replace(sealed, ciphertext=bytes(flipped))
        if field == "ciphertext"
        else replace(sealed, nonce=bytes(flipped))
    )

    with pytest.raises(TokenKeyError):
        open_token(changed, user, {"k1": key})
