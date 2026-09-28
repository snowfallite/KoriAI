"""JSON logs to stdout without secrets (tech.md §3.5, §3.6)."""

import logging
import re
from collections.abc import Mapping, MutableMapping
from typing import Any

import structlog

# Whole snake or kebab words only: prompt_tokens and tokens_billable are metrics, not secrets.
SECRET_KEY = re.compile(
    r"(?:^|[_-])"
    r"(?:token|passwords?|authorization|secrets?|cookies?|sid|credentials?|api[_-]key)"
    r"(?:$|[_-])",
    re.IGNORECASE,
)
MASK = "***"


def _redact(key: object, value: object) -> object:
    if isinstance(key, str) and SECRET_KEY.search(key):
        return MASK
    if isinstance(value, Mapping):
        return {k: _redact(k, v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_redact(None, v) for v in value]
    return value


def redact_secrets(
    _logger: object, _method: str, event_dict: MutableMapping[str, Any]
) -> Mapping[str, Any]:
    return {key: _redact(key, value) for key, value in event_dict.items()}


def configure_logging(level: str) -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True, key="ts"),
            structlog.processors.format_exc_info,
            redact_secrets,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelNamesMapping()[level]),
        # WriteLogger resolves sys.stdout per logger, so test capture sees it.
        logger_factory=structlog.WriteLoggerFactory(),
    )
