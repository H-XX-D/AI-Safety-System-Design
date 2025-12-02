from __future__ import annotations

from typing import Any, Dict


def log_structured(logger_obj: Any, level: str, message: str, payload: Dict[str, Any] | None = None, exc_info: bool = False) -> None:
    """Log an event using structured args when available (structlog),
    otherwise fall back to interpolated text. Never raises.
    """
    pl = payload or {}
    try:
        if hasattr(logger_obj, 'bind'):
            func = getattr(logger_obj, level)
            if exc_info:
                func(message, **pl, exc_info=True)
            else:
                func(message, **pl)
        else:
            func = getattr(logger_obj, level)
            if exc_info:
                func(f"{message} {pl}", exc_info=True)
            else:
                func(f"{message} {pl}")
    except Exception:
        try:
            func = getattr(logger_obj, level)
            func(message)
        except Exception:
            pass

