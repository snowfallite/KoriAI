"""DTO of the safe fetch port behind the media proxy (tech.md §8.8)."""

from app.contracts.common import Contract


class FetchedImage(Contract):
    content_type: str
    data: bytes
    final_url: str
