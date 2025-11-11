"""Custom middleware components for the Agent Gateway."""

from __future__ import annotations

import time
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from observability.context import clear_log_context, set_request_id, update_log_context
from uuid import uuid4


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log structured request/response information for every call."""

    def __init__(self, app, logger) -> None:  # type: ignore[override]
        super().__init__(app)
        self._logger = logger

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            status_code = response.status_code if response else 500
            context = {
                "event": "http.request",
                "method": request.method,
                "path": request.url.path,
                "status": status_code,
                "duration_ms": round(duration_ms, 3),
                "client_ip": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
            }
            self._logger.info(
                context
            )


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns a request ID (from header or generated) and stores it in context vars."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        clear_log_context()
        incoming_id = request.headers.get("x-request-id")
        request_id = incoming_id or str(uuid4())
        set_request_id(request_id)
        update_log_context(endpoint=request.url.path, error_stage="request")
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        update_log_context(error_stage=None)
        return response
