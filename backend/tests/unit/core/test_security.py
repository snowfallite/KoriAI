"""Passwords, tokens and the rate limit (S1-05 AC 4; tech.md §3.5)."""

import hashlib
import re

from app.core.security import (
    RateLimiter,
    hash_password,
    new_token,
    token_digest,
    verify_password,
)


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_a_key_gets_its_limit_a_window_and_no_more() -> None:
    clock = Clock()
    limiter = RateLimiter(window_s=60, clock=clock)

    assert all(limiter.hit("ip:10.0.0.1", 10) for _ in range(10))
    assert not limiter.hit("ip:10.0.0.1", 10)
    assert limiter.hit("ip:10.0.0.2", 10)  # every key counts on its own


def test_hits_leave_the_window_after_a_minute() -> None:
    clock = Clock()
    limiter = RateLimiter(window_s=60, clock=clock)
    for _ in range(5):
        limiter.hit("email:a@example.test", 5)

    clock.now += 59.9
    assert not limiter.hit("email:a@example.test", 5)  # a refused hit does not count
    clock.now += 0.1
    assert all(limiter.hit("email:a@example.test", 5) for _ in range(5))
    assert not limiter.hit("email:a@example.test", 5)


def test_idle_keys_are_forgotten() -> None:
    clock = Clock()
    limiter = RateLimiter(window_s=60, clock=clock)
    limiter.hit("ip:10.0.0.1", 10)

    clock.now += 60
    limiter.hit("ip:10.0.0.2", 10)

    assert set(limiter._hits) == {"ip:10.0.0.2"}


def test_a_password_hash_is_argon2id_and_takes_only_its_password() -> None:
    stored = hash_password("correct-horse-1")

    assert stored.startswith("$argon2id$")
    assert verify_password(stored, "correct-horse-1")
    assert not verify_password(stored, "correct-horse-2")
    assert not verify_password("not-a-hash", "correct-horse-1")


def test_tokens_are_random_url_safe_and_kept_as_sha256() -> None:
    token = new_token()

    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", token)  # 32 bytes: a cookie value without quotes
    assert token != new_token()
    assert token_digest(token) == hashlib.sha256(token.encode()).digest()
