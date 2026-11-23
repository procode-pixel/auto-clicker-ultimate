"""Rotating file log. Automation must never fail silently."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from autoclicker.paths import log_path


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("autoclicker")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    file_handler = RotatingFileHandler(
        log_path(), maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream)
    logger.propagate = False
    return logger
