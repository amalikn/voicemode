"""Structured logging helpers for the realtime voice runtime."""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


class JsonFormatter(logging.Formatter):
    """Simple JSON log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "time": self.formatTime(record, self.datefmt),
        }
        if hasattr(record, "event"):
            payload["event"] = record.event
        if hasattr(record, "details"):
            payload["details"] = record.details
        return json.dumps(payload, sort_keys=True)


def setup_runtime_logging(log_dir: Path, debug: bool = False) -> logging.Logger:
    """Configure rotating file logs for the realtime runtime."""
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("voicemode.realtime")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.propagate = True

    log_path = log_dir / "runtime.log"
    if not any(
        isinstance(handler, RotatingFileHandler) and getattr(handler, "baseFilename", "") == str(log_path)
        for handler in logger.handlers
    ):
        handler = RotatingFileHandler(log_path, maxBytes=2_000_000, backupCount=5)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    return logger
