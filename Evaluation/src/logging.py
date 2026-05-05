"""structlog → stderr (so CLI stdout stays parseable)."""
from __future__ import annotations

import logging
import sys

import structlog


def configure(level: str = "INFO", json_logs: bool = False) -> None:
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        stream=sys.stderr,
        format="%(message)s",
        force=True,
    )
    procs = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    if json_logs:
        procs.append(structlog.processors.JSONRenderer())
    else:
        procs.append(structlog.dev.ConsoleRenderer(colors=False))
    structlog.configure(
        processors=procs,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None):
    return structlog.get_logger(name)
