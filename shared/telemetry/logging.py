"""Structured logging helper."""

from __future__ import annotations

import logging
import sys

from shared.config import get_settings


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger for the given service/module name."""
    settings = get_settings()
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(settings.LOG_LEVEL)
    return logger
