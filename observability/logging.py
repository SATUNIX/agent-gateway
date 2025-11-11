"""Structured logging utilities for the Agent Gateway."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict

from observability.context import get_request_id


class JSONFormatter(logging.Formatter):
    """Render log records as JSON objects."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": get_request_id(),
        }
        if isinstance(record.msg, dict):
            payload.update(record.msg)
            message = payload.get("message")
            if not message:
                payload["message"] = record.getMessage()
        else:
            payload["message"] = record.getMessage()
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> logging.Logger:
    """Configure application-wide structured logging and return the root logger."""

    logger = logging.getLogger("agent_gateway")
    logger.setLevel(level.upper())
    logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def logging_level_from_env(default: str = "INFO") -> str:
    return os.getenv("GATEWAY_LOG_LEVEL", default)
