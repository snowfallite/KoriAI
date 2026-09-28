"""Domain errors; the HTTP layer turns them into ErrorOut (tech.md §16.1)."""

from pydantic import JsonValue

from app.contracts.common import ErrorCode


class AppError(Exception):
    def __init__(
        self, code: ErrorCode, message: str, details: dict[str, JsonValue] | None = None
    ) -> None:
        super().__init__(message)
        self.code: ErrorCode = code
        self.message = message
        self.details = details
