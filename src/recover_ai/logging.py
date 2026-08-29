"""structlog setup: pretty console for humans, JSON for machines."""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

_configured = False


def configure(*, json_logs: bool = False, level: str = "INFO") -> None:
    global _configured
    if _configured:
        return

    logging.basicConfig(format="%(message)s", stream=sys.stderr, level=level.upper())

    shared: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]
    renderer = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())
    )

    structlog.configure(
        processors=[*shared, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level.upper())),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str) -> Any:
    if not _configured:
        configure()
    return structlog.get_logger(name)
