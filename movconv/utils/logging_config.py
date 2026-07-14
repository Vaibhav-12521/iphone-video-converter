"""Centralised logging configuration.

Logs go to both the console (for development) and a rotating file inside the
per-user application data directory (for diagnosing issues in the field).
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from movconv.utils.resources import app_data_dir

_CONFIGURED = False


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure the root logger once and return it.

    Safe to call multiple times; only the first call installs handlers.
    """
    global _CONFIGURED
    root = logging.getLogger()
    if _CONFIGURED:
        return root

    root.setLevel(level)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler.
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    # Rotating file handler (5 files x 1 MB).
    try:
        log_file = app_data_dir() / "movtomp4.log"
        file_handler = RotatingFileHandler(
            log_file, maxBytes=1_000_000, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)
        root.info("Logging to %s", log_file)
    except Exception:  # pragma: no cover - never let logging break startup
        root.exception("Could not create file log handler; console only.")

    _CONFIGURED = True
    return root
