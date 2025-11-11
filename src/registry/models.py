"""Pydantic models describing agent configuration."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator, model_validator


AgentKind = Literal["declarative", "sdk"]


class AgentSpec(BaseModel):
    """Represents a single agent definition loaded from YAML."""

    name: str
    namespace: str = Field(default="default")
    display_name: str
    description: str = Field(default="")
    kind: AgentKind
    upstream: str
    model: str
    instructions: Optional[str] = None
    module: Optional[str] = None
    tools: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def qualified_name(self) -> str:
        return f"{self.namespace}/{self.name}"

    @field_validator("namespace")
    @classmethod
    def _normalize_namespace(cls, value: str) -> str:
        return value or "default"

    @model_validator(mode="after")
    def _validate_kind_requirements(self) -> "AgentSpec":
        if self.kind == "sdk" and not self.module:
            raise ValueError("SDK agents must define the 'module' attribute")
        if self.kind == "declarative" and not self.instructions:
            raise ValueError("Declarative agents must include 'instructions'")
        return self


class AgentsFile(BaseModel):
    """Full YAML document structure."""

    version: int = Field(default=1)
    defaults: Dict[str, Any] = Field(default_factory=dict)
    agents: List[AgentSpec]

    @model_validator(mode="after")
    def _apply_defaults(self) -> "AgentsFile":
        default_namespace = self.defaults.get("namespace", "default")
        default_upstream = self.defaults.get("upstream")
        default_model = self.defaults.get("model")
        for agent in self.agents:
            if not agent.namespace:
                agent.namespace = default_namespace
            if not agent.upstream and default_upstream:
                agent.upstream = default_upstream
            if not agent.model and default_model:
                agent.model = default_model
        return self


class UpstreamSpec(BaseModel):
    """Definition for a single upstream provider."""

    name: str
    provider: str = Field(default="openai-compatible")
    base_url: AnyHttpUrl
    priority: int = Field(default=1, ge=1)
    api_key: Optional[str] = None
    api_key_env: Optional[str] = None
    health_path: str = Field(default="/models")
    health_timeout: float = Field(default=5.0, gt=0)

    @field_validator("health_path")
    @classmethod
    def _ensure_health_path(cls, value: str) -> str:
        if not value.startswith("/"):
            return f"/{value}"
        return value


class UpstreamsFile(BaseModel):
    version: int = Field(default=1)
    upstreams: List[UpstreamSpec]

    @model_validator(mode="after")
    def _ensure_unique_names(self) -> "UpstreamsFile":
        seen = set()
        for upstream in self.upstreams:
            if upstream.name in seen:
                raise ValueError(f"Duplicate upstream detected: {upstream.name}")
            seen.add(upstream.name)
        return self


class ToolSpec(BaseModel):
    """Definition for a single tool entry."""

    name: str
    provider: Literal["local", "http", "mcp"]
    module: Optional[str] = None
    url: Optional[AnyHttpUrl] = None
    method: Optional[str] = None
    timeout: float = Field(default=10.0, gt=0)
    headers: Dict[str, str] = Field(default_factory=dict)
    stream: bool = Field(default=False)
    schema: Optional[Dict[str, Any]] = None


class ToolsFile(BaseModel):
    version: int = Field(default=1)
    tools: List[ToolSpec]

    @model_validator(mode="after")
    def _ensure_unique_tools(self) -> "ToolsFile":
        seen = set()
        for tool in self.tools:
            if tool.name in seen:
                raise ValueError(f"Duplicate tool detected: {tool.name}")
            seen.add(tool.name)
        return self
