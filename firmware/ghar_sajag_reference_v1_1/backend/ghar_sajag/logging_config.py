"""Bounded diagnostics for the backend. Never log resident data or secrets."""
from __future__ import annotations

from functools import wraps
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path

TRACE = 5
logging.addLevelName(TRACE, "TRACE")
_LOGGER = logging.getLogger("ghar_sajag")


def configure_logging(path: str | None = None, trace_enabled: bool | None = None) -> logging.Logger:
    """Configure once; ERROR is retained in every build and TRACE is opt-in."""
    if _LOGGER.handlers:
        return _LOGGER
    enabled = trace_enabled if trace_enabled is not None else os.getenv("GS_TRACE", "0") == "1"
    destination = Path(path or os.getenv("GS_LOG_FILE", "logs/backend.txt"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(destination, maxBytes=131_072, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "level=%(levelname)s category=%(category)s module=%(module_id)s event=%(event)s detail=%(message)s"
    ))
    handler.setLevel(TRACE if enabled else logging.ERROR)
    _LOGGER.setLevel(TRACE if enabled else logging.ERROR)
    _LOGGER.propagate = False
    _LOGGER.addHandler(handler)
    return _LOGGER


def emit(level: int, category: str, module_id: str, event: str, detail: str = "-") -> None:
    configure_logging().log(level, detail, extra={"category": category, "module_id": module_id, "event": event})


def error(category: str, module_id: str, event: str, detail: str) -> None:
    emit(logging.ERROR, category, module_id, event, detail)


def trace(category: str, module_id: str, event: str, detail: str = "-") -> None:
    if _LOGGER.isEnabledFor(TRACE) or os.getenv("GS_TRACE", "0") == "1":
        emit(TRACE, category, module_id, event, detail)


def traced(module_id: str, category: str = "BACKEND"):
    """Development flow trace plus a stable failure breadcrumb; no argument values."""
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            trace(category, module_id, f"{function.__name__}.enter")
            try:
                result = function(*args, **kwargs)
                trace(category, module_id, f"{function.__name__}.exit")
                return result
            except (MemoryError, RuntimeError, ValueError, TypeError, KeyError, IndexError) as exc:
                error(category, module_id, f"{function.__name__}.failed", type(exc).__name__)
                raise
        return wrapped
    return decorate
