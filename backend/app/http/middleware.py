"""Request id, access log, the last-resort 500 and the guard of /api (tech.md §3.5, §3.6, §6.1)."""

import time
import uuid

import structlog
from starlette.datastructures import MutableHeaders
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import Settings
from app.domains.auth.deps import auth_service
from app.http.deps import SESSION_COOKIE, UNAUTHORIZED, session_cookie
from app.http.errors import INTERNAL_MESSAGE, error_response

log = structlog.get_logger(__name__)

MUTATING = frozenset({"POST", "PUT", "PATCH", "DELETE"})
# Without a session (§6.1): GET /api/health* and these two.
PUBLIC = frozenset({("POST", "/api/auth/register"), ("POST", "/api/auth/login")})


class RequestContextMiddleware:
    """Outermost app middleware: an unhandled error still gets ErrorOut and X-Request-Id."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        started = time.perf_counter()
        status = 500
        response_started = False

        async def send_with_id(message: Message) -> None:
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                status, response_started = message["status"], True
                MutableHeaders(scope=message).append("X-Request-Id", request_id)
            await send(message)

        with structlog.contextvars.bound_contextvars(request_id=request_id):
            try:
                await self.app(scope, receive, send_with_id)
            except Exception:
                log.exception("unhandled_error")
                if not response_started:
                    response = error_response(request_id, 500, "internal", INTERNAL_MESSAGE)
                    await response(scope, receive, send_with_id)
            finally:
                route = scope.get("route")
                log.info(
                    "request_finished",
                    method=scope["method"],
                    route=getattr(route, "path", scope["path"]),
                    status=status,
                    duration_ms=round((time.perf_counter() - started) * 1000),
                )


def is_public(method: str, path: str) -> bool:
    health = path == "/api/health" or path.startswith("/api/health/")
    return (method, path) in PUBLIC or (method in {"GET", "HEAD"} and health)


def is_our_json(conn: HTTPConnection, settings: Settings) -> bool:
    """CSRF (§3.5): a cross-site form can send neither our Origin nor JSON without CORS."""
    origin = conn.headers.get("origin")
    media_type = conn.headers.get("content-type", "").partition(";")[0].strip().lower()
    return origin in settings.APP_ALLOWED_ORIGINS and media_type == "application/json"


class GuardMiddleware:
    """Refuses /api mutations from other origins and requests without a live session.

    Inside RequestContextMiddleware: its answers carry the request id. Routes read the user
    through app.http.deps.CurrentUser; every answer to a signed-in request slides the cookie.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            await self.app(scope, receive, send)
            return

        conn = HTTPConnection(scope)
        settings: Settings = conn.app.state.settings
        method, request_id = scope["method"], scope["state"]["request_id"]
        if method in MUTATING and not is_our_json(conn, settings):
            refused = error_response(request_id, 403, "forbidden", "Запрос отклонён")
            await refused(scope, receive, send)
            return
        if is_public(method, scope["path"]):
            await self.app(scope, receive, send)
            return

        token = conn.cookies.get(SESSION_COOKIE)
        principal = await auth_service(conn).authenticate(token) if token else None
        if token is None or principal is None:
            refused = error_response(request_id, 401, "unauthorized", UNAUTHORIZED)
            await refused(scope, receive, send)
            return
        scope["state"]["principal"] = principal
        slid = session_cookie(token, settings)

        async def send_with_cookie(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                cookies = headers.getlist("set-cookie")
                # Logout sets the cookie itself.
                if not any(cookie.startswith(f"{SESSION_COOKIE}=") for cookie in cookies):
                    headers.append("set-cookie", slid)
            await send(message)

        await self.app(scope, receive, send_with_cookie)
