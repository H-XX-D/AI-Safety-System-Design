"""Structured logging schema and validator.

Defines a minimal schema for security-relevant events and provides
`validate_log_event` + `bind_and_log` helpers. Validation is
dependency‑free (no jsonschema) to keep runtime lightweight.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Tuple
import time
import uuid

REQUIRED_FIELDS = {
    "timestamp": float,
    "event_type": str,
    "component": str,
    "severity": str,
    "message": str,
}

OPTIONAL_FIELDS = {
    "correlation_id": str,
    "request_id": str,
    "actor": str,
    "success": bool,
    "latency_ms": (int, float),
    "extra": dict,
}

SEVERITIES = {"DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"}


class LogValidationError(ValueError):
    pass


def validate_log_event(event: Dict[str, Any]) -> None:
    """Validate event dict in-place; raises LogValidationError on failure."""
    # Required presence and types
    for field, typ in REQUIRED_FIELDS.items():
        if field not in event:
            raise LogValidationError(f"missing required field '{field}'")
        if not isinstance(event[field], typ):
            raise LogValidationError(f"field '{field}' must be {typ}")
    # Severity check
    if event["severity"].upper() not in SEVERITIES:
        raise LogValidationError("invalid severity")
    # Optional types
    for field, typ in OPTIONAL_FIELDS.items():
        if field in event and not isinstance(event[field], typ):  # type: ignore[arg-type]
            raise LogValidationError(f"field '{field}' wrong type")


def new_event(
    *,
    event_type: str,
    component: str,
    severity: str,
    message: str,
    correlation_id: str | None = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    ev: Dict[str, Any] = {
        "timestamp": time.time(),
        "event_type": event_type,
        "component": component,
        "severity": severity.upper(),
        "message": message,
        "correlation_id": correlation_id or str(uuid.uuid4()),
    }
    ev.update(kwargs)
    return ev


def bind_and_log(logger: Any, event: Dict[str, Any]) -> None:
    """Validate then log using provided (structlog or stdlib) logger."""
    try:
        validate_log_event(event)
    except LogValidationError as e:
        # Emit a fallback error log in minimal structure
        logger.error("log_validation_failed", error=str(e), original=event)
        return
    # structlog logger supports passing as keyword args; stdlib fallback uses extra
    if hasattr(logger, "info") and hasattr(logger, "bind"):
        # structlog style
        severity = event.pop("severity")
        level_method = getattr(logger, severity.lower(), logger.info)
        level_method(event.pop("message"), **event)
    else:  # stdlib
        severity = event["severity"].upper()
        msg = event["message"]
        rest = {k: v for k, v in event.items() if k not in {"message"}}
        if severity == "DEBUG":
            logger.debug(msg, extra={"event": rest})
        elif severity == "INFO":
            logger.info(msg, extra={"event": rest})
        elif severity == "WARN":
            logger.warning(msg, extra={"event": rest})
        elif severity == "ERROR":
            logger.error(msg, extra={"event": rest})
        else:
            logger.critical(msg, extra={"event": rest})
