"""Logging setup: RotatingFileHandler + console."""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional

from src.config.schema import LoggingConfig


def setup_logging(
    config: LoggingConfig,
    logs_dir: str = "logs",
    ui_handler: Optional[logging.Handler] = None,
) -> logging.Logger:
    """Configure root logger with file + console handlers."""
    os.makedirs(logs_dir, exist_ok=True)

    root = logging.getLogger("parser_nb_bet")
    root.setLevel(getattr(logging, config.level.upper(), logging.INFO))

    # Clear existing handlers
    root.handlers.clear()

    formatter = logging.Formatter(config.format)

    # File handler with rotation
    file_handler = RotatingFileHandler(
        os.path.join(logs_dir, "parser.log"),
        maxBytes=config.max_bytes,
        backupCount=config.backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    # Optional UI handler (for Tkinter log viewer)
    if ui_handler:
        ui_handler.setFormatter(formatter)
        root.addHandler(ui_handler)

    return root
