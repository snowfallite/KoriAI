"""Safe fetch port behind the media proxy (tech.md §8.8)."""

from typing import Protocol

from app.contracts.fetch import FetchedImage


class FetchPort(Protocol):
    async def fetch_image(self, url: str, *, max_bytes: int) -> FetchedImage: ...
