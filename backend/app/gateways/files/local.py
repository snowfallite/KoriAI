"""FilesPort on the disk under DATA_DIR (tech.md §8.7)."""

import asyncio
import hashlib
from collections.abc import AsyncIterator
from pathlib import Path, PurePosixPath

from app.contracts.files import StoredFile

CHUNK = 1 << 20


async def _chunks(data: bytes | AsyncIterator[bytes]) -> AsyncIterator[bytes]:
    if isinstance(data, bytes):
        yield data
    else:
        async for chunk in data:
            yield chunk


class LocalFiles:
    def __init__(self, root: Path) -> None:
        self._root = root

    def local_path(self, key: str) -> Path:
        parts = PurePosixPath(key).parts
        # Keys come from code, never from users; the check keeps a bug inside DATA_DIR.
        if not parts or key.startswith("/") or "\\" in key or ".." in parts:
            raise ValueError(f"bad file key: {key!r}")
        return self._root.joinpath(*parts)

    async def put(self, key: str, data: bytes | AsyncIterator[bytes]) -> StoredFile:
        path = self.local_path(key)
        partial = path.with_name(f"{path.name}.part")
        digest, size = hashlib.sha256(), 0
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        out = await asyncio.to_thread(partial.open, "wb")
        try:
            async for chunk in _chunks(data):
                digest.update(chunk)
                size += len(chunk)
                await asyncio.to_thread(out.write, chunk)
        except BaseException:
            await asyncio.to_thread(out.close)
            await asyncio.to_thread(partial.unlink, missing_ok=True)
            raise
        await asyncio.to_thread(out.close)
        # Readers see the whole file or the old one, never a part.
        await asyncio.to_thread(partial.replace, path)
        return StoredFile(key=key, size=size, sha256=digest.hexdigest())

    async def open(self, key: str) -> AsyncIterator[bytes]:
        source = await asyncio.to_thread(self.local_path(key).open, "rb")
        try:
            while chunk := await asyncio.to_thread(source.read, CHUNK):
                yield chunk
        finally:
            await asyncio.to_thread(source.close)

    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(self.local_path(key).is_file)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self.local_path(key).unlink, missing_ok=True)
