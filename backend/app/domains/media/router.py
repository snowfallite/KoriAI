"""Images through the backend (tech.md §6.4, AD-09): F-13 adds document pages, F-15 artifacts."""

from typing import Annotated

from fastapi import APIRouter, Query, Response
from pydantic import AfterValidator

from app.domains.media.deps import MediaServiceDep

router = APIRouter(prefix="/api/media", tags=["media"])

LOGO_SIZES = (160, 320, 640)  # the sizes of the T-Invest CDN (§8.2)
# A brand logo rarely changes: the browser keeps it for a day.
CACHE_CONTROL = "private, max-age=86400"


def _logo_size(size: int) -> int:
    if size not in LOGO_SIZES:
        raise ValueError(f"size is one of {', '.join(map(str, LOGO_SIZES))}")
    return size


# A Literal of ints takes no query string: the check runs after the int.
LogoSize = Annotated[
    int, AfterValidator(_logo_size), Query(json_schema_extra={"enum": list(LOGO_SIZES)})
]


@router.get(
    "/logos/{logo_base}",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
)
async def logo(logo_base: str, media: MediaServiceDep, size: LogoSize = 160) -> Response:
    data = await media.logo(logo_base, size)
    return Response(data, media_type="image/png", headers={"Cache-Control": CACHE_CONTROL})
