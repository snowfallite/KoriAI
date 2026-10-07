"""The media proxy (tech.md §3.5, §6.4, AD-09): the SPA shows images only through the backend.
Instrument logos come from the T-Invest CDN once and then from the media cache on disk, which
maintenance.cleanup empties after 30 days."""

import hashlib

from app.core.errors import AppError, PermanentGatewayError
from app.domains.instruments.service import InstrumentsService, logo_source
from app.gateways.fetch.port import FetchPort
from app.gateways.files.port import FilesPort

PNG = "image/png"
NO_LOGO = "Логотип не найден"


def cache_key(url: str) -> str:
    """The FilesPort key of a fetched image (§8.7)."""
    digest = hashlib.sha256(url.encode()).hexdigest()
    return f"media/{digest[:2]}/{digest}"


class MediaService:
    def __init__(
        self, files: FilesPort, fetch: FetchPort, instruments: InstrumentsService, max_bytes: int
    ) -> None:
        self._files = files
        self._fetch = fetch
        self._instruments = instruments
        self._max_bytes = max_bytes

    async def logo(self, logo_base: str, size: int) -> bytes:
        """The PNG logo of a known instrument in one of the CDN sizes (§8.2)."""
        url = logo_source(logo_base, size)
        if url is None:
            raise AppError("not_found", NO_LOGO)
        key = cache_key(url)
        try:
            return b"".join([chunk async for chunk in self._files.open(key)])
        except FileNotFoundError:
            pass  # not fetched yet, or the cleanup took it
        # The proxy fetches only logos of instruments it knows, never any name it is given.
        if not await self._instruments.has_logo(logo_base):
            raise AppError("not_found", NO_LOGO)
        try:
            image = await self._fetch.fetch_image(url, max_bytes=self._max_bytes)
        except PermanentGatewayError:
            raise AppError("not_found", NO_LOGO) from None
        if image.content_type.partition(";")[0].strip().lower() != PNG:
            raise AppError("not_found", NO_LOGO)
        await self._files.put(key, image.data)
        return image.data
