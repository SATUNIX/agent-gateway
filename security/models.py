"""Pydantic models for security configuration."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class RateLimitConfig(BaseModel):
    per_minute: int = Field(default=60, gt=0)


class APIKeyEntry(BaseModel):
    id: str
    key: Optional[str] = Field(default=None, description="Plaintext API key (hashed at load)")
    hashed_key: Optional[str] = Field(default=None, description="Pre-hashed API key (sha256)")
    description: Optional[str] = None
    allow_agents: List[str] = Field(default_factory=lambda: ["*"])
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    expires_at: Optional[datetime] = None


class DefaultSecurity(BaseModel):
    allow_agents: List[str] = Field(default_factory=lambda: ["*"])
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    local_tools_allowlist: List[str] = Field(default_factory=lambda: ["tooling.local_tools:*"])
    dropin_module_allowlist: List[str] = Field(default_factory=lambda: ["*"])
    dropin_module_denylist: List[str] = Field(default_factory=list)


class SecurityConfig(BaseModel):
    version: int = Field(default=1)
    default: DefaultSecurity = Field(default_factory=DefaultSecurity)
    api_keys: List[APIKeyEntry] = Field(default_factory=list)
