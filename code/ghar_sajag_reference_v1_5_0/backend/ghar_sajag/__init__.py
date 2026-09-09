"""Ghar Sajag hardware-independent backend domain package."""

from .service import GharSajagService
from .logging_config import configure_logging

configure_logging()

__all__ = ["GharSajagService"]
