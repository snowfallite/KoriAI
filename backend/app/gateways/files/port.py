"""File store port (tech.md §8.7): keys under DATA_DIR."""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Protocol

from app.contracts.files import StoredFile


class FilesPort(Protocol):
    async def put(self, key: str, data: bytes | AsyncIterator[bytes]) -> StoredFile: ...
    def open(self, key: str) -> AsyncIterator[bytes]: ...
    def local_path(self, key: str) -> Path: ...  # no IO: where the key lives
    async def exists(self, key: str) -> bool: ...
    async def delete(self, key: str) -> None: ...
