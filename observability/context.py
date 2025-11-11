"""Context helpers for request correlation."""

from __future__ import annotations

import contextvars
from typing import Optional


_request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)


def set_request_id(value: str) -> None:
    """Set the request ID for the current context.
    
    Args:
        value: The request ID to set
    """
    _request_id_var.set(value)


def get_request_id() -> Optional[str]:
    """Get the request ID from the current context.
    
    Returns:
        The request ID if set, otherwise None
    """
    return _request_id_var.get()