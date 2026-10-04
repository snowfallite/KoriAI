"""Image fetch fake (tech.md §8.1, §8.8): one transparent pixel for any http(s) URL."""

import base64
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import Field

from app.contracts.fetch import FetchedImage
from app.core.errors import PermanentGatewayError
from app.gateways.fakes import Fake, port_method

PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


class FakeFetch(Fake):
    port = "fetch"
    unavailable = "web_unavailable"
    rate_limited = "web_unavailable"

    @port_method()
    async def fetch_image(
        self, url: str, *, max_bytes: Annotated[int, Field(ge=1)]
    ) -> FetchedImage:
        # The rules of the real one that do not need a network: the scheme and the size.
        if urlsplit(url).scheme not in {"http", "https"} or len(PIXEL) > max_bytes:
            raise PermanentGatewayError("not_found")
        return FetchedImage(content_type="image/png", data=PIXEL, final_url=url)
