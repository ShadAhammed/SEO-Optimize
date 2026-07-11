"""Centralised logging configuration for SEOOptimize.

Call ``setup_logging()`` once at application startup.  After that, every
module obtains its own logger with ``get_logger(__name__)``.
"""

import logging
import sys
from typing import Any


def setup_logging(level: str = "INFO") -> None:
    """Configure root logger with a clean, readable format.

    Args:
        level: One of DEBUG / INFO / WARNING / ERROR / CRITICAL.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(fmt)
    handler.setLevel(numeric_level)

    root = logging.getLogger()
    root.setLevel(numeric_level)

    # Avoid duplicate handlers on Streamlit hot-reload
    if not root.handlers:
        root.addHandler(handler)
    else:
        root.handlers.clear()
        root.addHandler(handler)

    # Quieten noisy third-party libraries
    for noisy in ("httpx", "httpcore", "playwright", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger.

    Usage::

        from app.core.logging import get_logger
        logger = get_logger(__name__)
        logger.info("Starting analysis for %s", url)
    """
    return logging.getLogger(name)


class ProgressLogger:
    """Thin wrapper that logs progress steps with consistent formatting."""

    def __init__(self, logger: logging.Logger, prefix: str = "") -> None:
        self._log = logger
        self._prefix = f"[{prefix}] " if prefix else ""

    def step(self, message: str, **extra: Any) -> None:
        self._log.info("%s%s", self._prefix, message)

    def warn(self, message: str, **extra: Any) -> None:
        self._log.warning("%s%s", self._prefix, message)

    def error(self, message: str, **extra: Any) -> None:
        self._log.error("%s%s", self._prefix, message)
