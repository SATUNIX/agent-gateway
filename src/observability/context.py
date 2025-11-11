"""Context helpers for request correlation and structured logging."""

from __future__ import annotations

import contextvars
from typing import Any, Dict, Optional


_request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)
_log_context_var: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar(
    "log_context", default={}
)


def set_request_id(value: str) -> None:
    """Set the request ID for the current context."""

    _request_id_var.set(value)
    update_log_context(request_id=value, correlation_id=value)


def get_request_id() -> Optional[str]:
    """Retrieve the current request ID."""

    return _request_id_var.get()


def clear_log_context() -> None:
    """Reset the structured log context."""

    _log_context_var.set({})


def update_log_context(**kwargs: Any) -> None:
    """Merge key/value pairs into the log context (use None to remove)."""

    ctx = dict(_log_context_var.get())
    for key, value in kwargs.items():
        if value is None:
            ctx.pop(key, None)
        else:
            ctx[key] = value
    _log_context_var.set(ctx)


def get_log_context() -> Dict[str, Any]:
    """Return a copy of the current log context."""

    return dict(_log_context_var.get())
