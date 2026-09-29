"""DTO of the file store port (tech.md §8.7)."""

from app.contracts.common import Contract, Sha256


class StoredFile(Contract):
    key: str
    size: int
    sha256: Sha256
