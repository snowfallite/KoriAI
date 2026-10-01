"""Providers of the auth domain (tech.md §16.1)."""

from typing import Annotated

from fastapi import Depends
from starlette.requests import HTTPConnection

from app.db.base import UnitOfWork
from app.domains.auth.service import AuthService


def auth_service(conn: HTTPConnection) -> AuthService:
    state = conn.app.state
    return AuthService(UnitOfWork(state.engine), state.settings, state.limiter)


AuthServiceDep = Annotated[AuthService, Depends(auth_service)]
