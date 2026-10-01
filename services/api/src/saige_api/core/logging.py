"""Structured JSON logging with defensive redaction.

Log events must never carry secrets, tokens or document content. The
redaction processor is a safety net, not a licence to log sensitive data.
"""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import Mapping, MutableMapping
from typing import Any

import structlog

SENSITIVE_KEY_PATTERN = re.compile(
    r"(pass(word)?|secret|token|authorization|cookie|api[_-]?key|credential|"
    r"refresh|access[_-]?code|content|text|body|ocr|prompt|query)",
    re.IGNORECASE,
)
BEARER_PATTERN = re.compile(r"(?i)bearer\s+[a-z0-9._~+/=-]+")
REDACTED = "[REDACTED]"
_RESERVED_KEYS = frozenset({"event", "level", "timestamp", "logger", "request_id"})


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return BEARER_PATTERN.sub("Bearer " + REDACTED, value)
    if isinstance(value, Mapping):
        return redact_mapping(value)
    if isinstance(value, list | tuple):
        return [_redact_value(item) for item in value]
    return value


def redact_mapping(data: Mapping[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in data.items():
        if key not in _RESERVED_KEYS and SENSITIVE_KEY_PATTERN.search(key):
            redacted[key] = REDACTED
        else:
            redacted[key] = _redact_value(value)
    return redacted


def _redaction_processor(
    _logger: Any, _method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    return redact_mapping(event_dict)


def configure_logging(level: str = "INFO", *, json_output: bool = True) -> None:
    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer(colors=False)
    )
    numeric_level = logging.getLevelNamesMapping().get(level.upper(), logging.INFO)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            _redaction_processor,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(level=numeric_level, stream=sys.stdout, format="%(message)s")
    # Uvicorn's access log prints full URLs including query strings, which may
    # contain search terms. We emit our own path-only access log instead.
    logging.getLogger("uvicorn.access").disabled = True


def get_logger(name: str | None = None) -> Any:
    return structlog.get_logger(name)
