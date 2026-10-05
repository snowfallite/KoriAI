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


class GatewayError(Exception):
    """A call of an external client failed (tech.md §8.1)."""

    def __init__(
        self, code: ErrorCode, retryable: bool, retry_after_s: float | None = None
    ) -> None:
        super().__init__(code)
        self.code: ErrorCode = code
        self.retryable = retryable
        self.retry_after_s = retry_after_s


class TransientGatewayError(GatewayError):
    """Timeout, 5xx, 429, gRPC UNAVAILABLE: the queue retries the job (§10.1)."""

    def __init__(self, code: ErrorCode, retry_after_s: float | None = None) -> None:
        super().__init__(code, retryable=True, retry_after_s=retry_after_s)


class PermanentGatewayError(GatewayError):
    """4xx, a wrong token, not found: a retry gets the same answer."""

    def __init__(self, code: ErrorCode) -> None:
        super().__init__(code, retryable=False)


class QuotaExhaustedError(GatewayError):
    """A budget of the service ran out, so the call was not made (§8.4)."""

    def __init__(self, code: ErrorCode) -> None:
        super().__init__(code, retryable=False)


class ContractViolation(Exception):
    """A fake got input its port contract forbids, or a test lacks a fixture (§8.1)."""
