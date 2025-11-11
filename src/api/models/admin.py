"""Models for management endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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
