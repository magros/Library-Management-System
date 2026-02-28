from __future__ import annotations

import logging
import json
import sys
from datetime import datetime, timezone
from contextvars import ContextVar
from typing import Optional

from app.core.config import settings

# Context variables for request-scoped data
request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
current_user_id_ctx: ContextVar[Optional[str]] = ContextVar("current_user_id", default=None)


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add context variables
        req_id = request_id_ctx.get()
        if req_id:
            log_entry["request_id"] = req_id

        user_id = current_user_id_ctx.get()
        if user_id:
            log_entry["user_id"] = user_id

        # Add extra fields
        if hasattr(record, "extra_data"):
            log_entry.update(record.extra_data)

        # Add exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def setup_logging() -> None:
    """Configure structured JSON logging for the application."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler with JSON formatter
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root_logger.addHandler(handler)

    # Reduce noise from third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger."""
    return logging.getLogger(name)


