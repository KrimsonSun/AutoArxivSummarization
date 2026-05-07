"""Structured logging configured to write only to stderr.

Per handoff §13.1, the CLI must emit JSON on stdout and logs on stderr so
the parent TS process can reliably parse stdout. ``structlog`` is configured
once at process startup; everything else just calls ``log = get_logger()``.
"""
from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(level: str = "INFO", json_logs: bool = True) -> None:
    """Idempotent log configuration. Streams ALL output to stderr."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        stream=sys.stderr,  # never stdout — see handoff §13.1
        format="%(message)s",
        force=True,  # override any earlier basicConfig from libraries
    )

    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    if json_logs:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=False))

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None):
    return structlog.get_logger(name)
