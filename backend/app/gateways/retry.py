"""Retries of reads (tech.md §8.1): at most 2 more tries, the pause from retry_after_s or an
exponent with jitter."""

import asyncio
import random
from collections.abc import Awaitable, Callable

from app.core.errors import GatewayError

MAX_PAUSE_S = 30.0


def backoff(attempt: int, retry_after_s: float | None, base_s: float = 0.5) -> float:
    if retry_after_s is not None:
        return min(retry_after_s, MAX_PAUSE_S)
    return min(base_s * 2.0**attempt, MAX_PAUSE_S) * random.uniform(0.5, 1.5)  # noqa: S311


async def with_retries[T](
    call: Callable[[], Awaitable[T]], *, retries: int = 2, base_s: float = 0.5
) -> T:
    """Runs the call again after a retryable GatewayError; anything else goes up at once."""
    attempt = 0
    while True:
        try:
            return await call()
        except GatewayError as error:
            if not error.retryable or attempt >= retries:
                raise
            await asyncio.sleep(backoff(attempt, error.retry_after_s, base_s))
            attempt += 1
