"""The clock of the app (tech.md §16.1): code asks now() here, so tests can swap it."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

# Trading days, usage days and what users see run on Moscow time (§5, §12.2).
MSK = ZoneInfo("Europe/Moscow")


def now() -> datetime:
    return datetime.now(UTC)


def msk_day(moment: datetime | None = None) -> date:
    return (moment or now()).astimezone(MSK).date()
