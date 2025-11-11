"""Models for management endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict


class AgentInfo(BaseModel):
    name: str
    namespace: str
    qualified_name: str
    display_name: str
    kind: str
    model: str
    upstream: str
    description: str
    tools: List[str]
    metadata: Dict[str, Any]
    status: str = Field(default="available")
    error: Optional[str] = None


class UpstreamInfo(BaseModel):
    name: str
    provider: str
    base_url: str
    priority: int
    healthy: bool
    health_path: str
    health_timeout: float
    last_checked: Optional[int]
    last_error: Optional[str]


class MetricsResponse(BaseModel):
    total_requests: int
    streaming_requests: int
    average_latency_ms: float
    max_latency_ms: float
    min_latency_ms: float


class ToolInfo(BaseModel):
    name: str
    provider: str
    module: Optional[str]
    url: Optional[str]
    method: Optional[str]


class SecurityKeyInfo(BaseModel):
    key_id: str
    allow_agents: List[str]
    rate_limit_per_minute: int
    expires_at: Optional[str]


class SecurityPreviewRequest(BaseModel):
    agent: str


class SecurityPreviewResponse(BaseModel):
    agent: str
    allowed: bool
    source: str
    pattern: Optional[str]
    override: Optional[Dict[str, Any]] = None


class SecurityOverrideRequest(BaseModel):
    agent: str
    ttl_seconds: int = Field(gt=0, lt=86_400)
    reason: Optional[str] = None


class SecurityOverrideResponse(BaseModel):
    agent: str
    pattern: str
    expires_at: int
    reason: Optional[str] = None


class RecentError(BaseModel):
    model_config = ConfigDict(extra="allow")

    timestamp: int
    event: str
    message: str
    request_id: Optional[str] = None
    agent_id: Optional[str] = None
    module_path: Optional[str] = None
    error_stage: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
