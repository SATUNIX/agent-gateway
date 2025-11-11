"""API key authentication dependency."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from security import AuthContext, RateLimitExceeded, security_manager


api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)


async def enforce_api_key(api_key: str | None = Depends(api_key_header)) -> AuthContext:
    """Validate the gateway API key and return the auth context."""

    try:
        return security_manager.authenticate(api_key)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
