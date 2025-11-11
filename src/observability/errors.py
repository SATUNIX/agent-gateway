"""Ring buffer for recent discovery/runtime errors surfaced via admin APIs."""

from __future__ import annotations

import time
from collections import deque
from threading import Lock
from typing import Any, Deque, Dict, List

from observability.context import get_log_context, get_request_id


class ErrorRecorder:
    def __init__(self, max_entries: int = 200) -> None:
        self._buffer: Deque[Dict[str, Any]] = deque(maxlen=max_entries)
        self._lock = Lock()

    def record(self, *, event: str, message: str, details: Dict[str, Any] | None = None) -> None:
        entry = {
            "timestamp": int(time.time()),
            "event": event,
            "message": message,
            "request_id": get_request_id(),
        }
        entry.update(get_log_context())
        if details:
            entry["details"] = details
        with self._lock:
            self._buffer.appendleft(entry)

    def list(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._buffer)


error_recorder = ErrorRecorder()


__all__ = ["error_recorder", "ErrorRecorder"]
