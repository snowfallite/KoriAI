"""Every error leaves the API as ErrorOut (tech.md §6.1, §6.7)."""

import math
from collections.abc import Mapping

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import JsonValue
from starlette.exceptions import HTTPException

from app.contracts.common import ErrorCode, ErrorOut
from app.core.errors import AppError, GatewayError

log = structlog.get_logger(__name__)

STATUS: dict[ErrorCode, int] = {
    "unauthorized": 401,
    "invalid_credentials": 401,
    "forbidden": 403,
    "registration_closed": 403,
    "not_found": 404,
    "conflict": 409,
    "run_active": 409,
    "email_taken": 409,
    "broker_not_connected": 409,
    "gone": 410,
    "validation_error": 422,
    "invite_required": 422,
    "invite_invalid": 422,
    "token_invalid": 422,
    "token_not_read_only": 422,
    "rate_limited": 429,
    "user_budget_exhausted": 429,
    "llm_busy": 503,
    "llm_quota_exhausted": 503,
    "tinvest_unavailable": 503,
    "tinvest_rate_limited": 503,
    "web_unavailable": 503,
    "web_credits_exhausted": 503,
    "disclosure_unavailable": 503,
    "internal": 500,
}

# Routing raises only these; domains raise AppError.
HTTP_ERRORS: dict[int, tuple[ErrorCode, str]] = {
    404: ("not_found", "Адрес не найден"),
    405: ("not_found", "Метод не поддерживается"),
}
INTERNAL_MESSAGE = "Внутренняя ошибка сервера"
TINVEST = "Т-Инвестиции"  # noqa: RUF001 - the brand starts with a Cyrillic letter
# What the reader sees when an external client fails and no domain says it better.
GATEWAY_MESSAGES: dict[ErrorCode, str] = {
    "not_found": "Ничего не найдено",
    "token_invalid": "Токен брокера не подходит: подключите брокера заново в Настройках",
    "tinvest_unavailable": f"{TINVEST} не отвечают, попробуйте позже",
    "tinvest_rate_limited": f"{TINVEST} просят подождать, повторите через минуту",
    "web_unavailable": "Внешний сайт не отвечает, попробуйте позже",
    "web_credits_exhausted": "Кредиты веб-поиска закончились",
    "disclosure_unavailable": "Сайт раскрытия информации не отвечает, попробуйте позже",
    "llm_busy": "Модель занята, попробуйте позже",
    "llm_quota_exhausted": "Квота модели исчерпана",
}
GATEWAY_FALLBACK = "Внешний сервис не ответил, попробуйте позже"


def error_response(
    request_id: str,
    status: int,
    code: ErrorCode,
    message: str,
    details: dict[str, JsonValue] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    body = ErrorOut(code=code, message=message, details=details, request_id=request_id)
    return JSONResponse(body.model_dump(mode="json"), status_code=status, headers=headers)


def install(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError) -> JSONResponse:
        return error_response(
            request.state.request_id, STATUS[exc.code], exc.code, exc.message, exc.details
        )

    @app.exception_handler(GatewayError)
    async def gateway_error(request: Request, exc: GatewayError) -> JSONResponse:
        log.warning("gateway_failed", code=exc.code, retryable=exc.retryable)
        headers = None
        if exc.retry_after_s is not None:
            headers = {"Retry-After": str(max(1, math.ceil(exc.retry_after_s)))}
        return error_response(
            request.state.request_id,
            STATUS[exc.code],
            exc.code,
            GATEWAY_MESSAGES.get(exc.code, GATEWAY_FALLBACK),
            headers=headers,
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        fallback: tuple[ErrorCode, str] = (
            ("internal", INTERNAL_MESSAGE)
            if exc.status_code >= 500
            else ("validation_error", "Некорректный запрос")
        )
        code, message = HTTP_ERRORS.get(exc.status_code, fallback)
        return error_response(
            request.state.request_id, exc.status_code, code, message, headers=exc.headers
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Drop input and ctx: input may hold a password, ctx may hold exception objects.
        errors: list[JsonValue] = [
            {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
        return error_response(
            request.state.request_id,
            422,
            "validation_error",
            "Проверьте введённые данные",
            {"errors": errors},
        )
