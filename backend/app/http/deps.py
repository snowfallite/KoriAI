"""What every router needs: the signed-in user, the client and the session cookie (tech.md §3.5)."""

from ipaddress import IPv4Address, IPv6Address, ip_address
from typing import Annotated

from fastapi import Depends, Request
from starlette.requests import HTTPConnection

from app.config import Settings
from app.core.errors import AppError
from app.core.security import Principal

SESSION_COOKIE = "sid"
UNAUTHORIZED = "Войдите в аккаунт"


def current_user(request: Request) -> Principal:
    # GuardMiddleware sets it on every /api request off the public routes (§6.1).
    principal: Principal | None = getattr(request.state, "principal", None)
    if principal is None:
        raise AppError("unauthorized", UNAUTHORIZED)
    return principal


CurrentUser = Annotated[Principal, Depends(current_user)]


def client_ip(conn: HTTPConnection) -> IPv4Address | IPv6Address | None:
    """Behind Caddy uvicorn takes the address from X-Forwarded-For (backend/Dockerfile)."""
    try:
        return ip_address(conn.client.host) if conn.client else None
    except ValueError:
        return None


def session_cookie(token: str, settings: Settings) -> str:
    """Set-Cookie of the session (§3.5); an empty token deletes the cookie."""
    max_age = settings.SESSION_TTL_DAYS * 86400 if token else 0
    cookie = f"{SESSION_COOKIE}={token}; Max-Age={max_age}; Path=/; HttpOnly; SameSite=Lax"
    return f"{cookie}; Secure" if settings.COOKIE_SECURE else cookie
