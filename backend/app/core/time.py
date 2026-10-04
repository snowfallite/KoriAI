"""The clock of the app (tech.md §16.1): code asks now() here, so tests can swap it."""

from datetime import UTC, datetime


def now() -> datetime:
    return datetime.now(UTC)
