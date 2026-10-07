"""Providers of the media domain (tech.md §16.1)."""

from typing import Annotated

from fastapi import Depends
from starlette.requests import HTTPConnection

from app.db.base import UnitOfWork
from app.domains.instruments.service import InstrumentsService
from app.domains.media.service import MediaService
from app.gateways.factory import Gateways


def media_service(conn: HTTPConnection) -> MediaService:
    state = conn.app.state
    gateways: Gateways = state.gateways
    instruments = InstrumentsService(UnitOfWork(state.engine), gateways.tinvest)
    return MediaService(gateways.files, gateways.fetch, instruments, state.settings.MEDIA_MAX_BYTES)


MediaServiceDep = Annotated[MediaService, Depends(media_service)]
