"""Centralized enterprise logging configuration for pharma-commercial-data-engine."""

from __future__ import annotations

import logging
import os
from pathlib import Path


def setup_logging(
    log_file: str | Path = "logs/pipeline.log",
    log_level: int = logging.INFO,
) -> logging.Logger:
    """Configure structured logging to both a file and the console."""
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Avoid adding duplicate handlers if setup_logging is invoked repeatedly
    if not root_logger.handlers:
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # File handler
        file_handler = logging.FileHandler(str(log_path), encoding="utf-8")
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    return logging.getLogger("pharma_engine")


def get_logger(name: str = "pharma_engine") -> logging.Logger:
    """Retrieve a named logger under the enterprise logging hierarchy."""
    return logging.getLogger(name)
