"""Central logging configuration using structlog + standard logging.

Call `init_logging()` once at process start.
"""
from __future__ import annotations
import logging
import sys
from typing import Optional, Any, List
from log_schema import bind_and_log, new_event

try:
    import structlog
except ImportError:  # Fallback if structlog not installed yet
    structlog = None  # type: ignore


def init_logging(level: int = logging.INFO, json_mode: bool = False) -> None:
    """Initialize application-wide logging.

    Args:
        level: Base log level (default INFO)
        json_mode: If True, emit JSON logs (for production ingestion)
    """
    if structlog is None:
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            stream=sys.stdout,
        )
        logging.getLogger(__name__).warning(
            "structlog not installed; using basic logging config"  # noqa: E501
        )
        return

    processors: List[Any] = [
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if json_mode:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(level=level, stream=sys.stdout)


def get_logger(name: Optional[str] = None):
    """Return a structlog logger if available, else stdlib logger."""
    if structlog is None:
        return logging.getLogger(name or __name__)
    return structlog.get_logger(name or __name__)


def log_event(name: Optional[str], *, event_type: str, component: str, severity: str, message: str, **kwargs: Any) -> None:
    """Convenience wrapper: build schema event, validate, and log it.

    Example:
        log_event("audit", event_type="audit_seed", component="audit", severity="INFO",
                  message="seed generated", seed_hex=hexv)
    """
    logger = get_logger(name)
    ev = new_event(event_type=event_type, component=component, severity=severity, message=message, **kwargs)
    bind_and_log(logger, ev)
