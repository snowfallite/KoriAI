"""Request id, access log and the last-resort 500 (tech.md §3.6, §6.1)."""

import time
import uuid

import structlog
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.http.errors import INTERNAL_MESSAGE, error_response

log = structlog.get_logger(__name__)


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
