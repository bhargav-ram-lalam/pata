"""
observability/logger.py
=======================
Structured JSON logging formatter and request correlation context with strict PII protection.
"""

from __future__ import annotations

import contextvars
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Context variable for request correlation ID
request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_id", default=None)

# PII debug logging flag
ALLOW_PII_LOGGING = os.getenv("PATA_DEBUG_LOG_PII", "false").lower() in ("true", "1", "yes")


class JSONLogFormatter(logging.Formatter):
    """
    Format log records as single-line JSON objects with ISO timestamps,
    request correlation IDs, and PII guardrails.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Inject request_id from context if present
        req_id = request_id_var.get()
        if req_id:
            log_data["request_id"] = req_id

        # Attach custom structured attributes if provided
        if hasattr(record, "structured_data") and isinstance(record.structured_data, dict):
            # Guard against PII leaking into structured logs
            data_copy = dict(record.structured_data)
            if not ALLOW_PII_LOGGING and record.levelno >= logging.INFO:
                for pii_key in ("raw_address", "address", "raw_input"):
                    if pii_key in data_copy:
                        data_copy[pii_key] = "[REDACTED_PII]"
            log_data.update(data_copy)

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


def setup_structured_logging(level: int = logging.INFO) -> None:
    """Configure root logger with JSON log formatting."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to prevent duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONLogFormatter())
    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with Pata naming."""
    return logging.getLogger(name)
