"""The T-Invest token at rest (tech.md §3.5, AD-10): AES-256-GCM, the user id as AAD.

TINVEST_TOKEN_KEYS maps key ids to 32-byte keys; new tokens take TINVEST_TOKEN_ACTIVE_KEY, and a
token opens with the key it names, so an old key keeps its tokens readable after a rotation.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import SecretBytes, SecretStr

NONCE_BYTES = 12
KEY_BYTES = 32
HINT_CHARS = 4


@dataclass(frozen=True, slots=True)
class SealedToken:
    """The columns of broker_connections that hold the token (§5.2)."""

    ciphertext: bytes
    nonce: bytes
    key_id: str


class TokenKeyError(Exception):
    """No key opens the token: the key is gone, or the bytes or the user differ."""


def _cipher(keys: Mapping[str, SecretBytes], key_id: str) -> AESGCM:
    key = keys.get(key_id)
    # The messages name the key id only: never the key or the token.
    if key is None:
        raise TokenKeyError(f"TINVEST_TOKEN_KEYS has no key {key_id}")
    if len(key.get_secret_value()) != KEY_BYTES:
        raise TokenKeyError(f"key {key_id} is not 32 bytes")
    return AESGCM(key.get_secret_value())


def seal_token(
    token: SecretStr, user_id: UUID, keys: Mapping[str, SecretBytes], key_id: str
) -> SealedToken:
    """Encrypts the token for this user with the key `key_id`."""
    nonce = os.urandom(NONCE_BYTES)
    data = token.get_secret_value().encode()
    ciphertext = _cipher(keys, key_id).encrypt(nonce, data, user_id.bytes)
    return SealedToken(ciphertext=ciphertext, nonce=nonce, key_id=key_id)


def open_token(sealed: SealedToken, user_id: UUID, keys: Mapping[str, SecretBytes]) -> SecretStr:
    try:
        data = _cipher(keys, sealed.key_id).decrypt(sealed.nonce, sealed.ciphertext, user_id.bytes)
    except (InvalidTag, ValueError):  # ValueError: a nonce of another length
        raise TokenKeyError(f"key {sealed.key_id} does not open the token") from None
    return SecretStr(data.decode())


def token_hint(token: SecretStr) -> str:
    """What the API shows of a token: its last characters (§3.5)."""
    return token.get_secret_value()[-HINT_CHARS:]
