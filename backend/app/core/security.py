"""Passwords, session tokens and the in-process rate limit (tech.md §3.5)."""

import hashlib
import secrets
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

# argon2id with the RFC 9106 low-memory profile of argon2-cffi: 64 MiB a hash.
_hasher = PasswordHasher()
# ponytail: two hashes at a time hold a login burst to 128 MiB in the one API process (AD-02);
# a queue of logins is the price, raise the count with the RAM.
_hash_slots = threading.BoundedSemaphore(2)


@dataclass(frozen=True, slots=True)
class Principal:
    """The signed-in user of a request."""

    user_id: UUID
    session_id: UUID
    role: str  # users.role: user or owner (§5.1)


def hash_password(password: str) -> str:
    with _hash_slots:
        return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        with _hash_slots:
            return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def new_token(nbytes: int = 32) -> str:
    """Random bytes in URL-safe base64: a cookie value or a link parameter without quoting."""
    return secrets.token_urlsafe(nbytes)


def token_digest(token: str) -> bytes:
    """The database keeps this instead of a session token or an invite code."""
    return hashlib.sha256(token.encode()).digest()


class RateLimiter:
    """Hits per key in a sliding window, in the memory of the one API process (AD-02)."""

    def __init__(self, window_s: float = 60, clock: Callable[[], float] = time.monotonic) -> None:
        self._window = window_s
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._swept = clock()

    def hit(self, key: str, limit: int) -> bool:
        """Counts a hit of the key; refuses it once the window holds `limit` hits."""
        now = self._clock()
        start = now - self._window
        if now - self._swept >= self._window:
            # Keys idle for a whole window count nothing: forget them to bound the memory.
            self._hits = {k: hits for k, hits in self._hits.items() if hits and hits[-1] > start}
            self._swept = now
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= start:
            hits.popleft()
        if len(hits) >= limit:
            return False
        hits.append(now)
        return True
