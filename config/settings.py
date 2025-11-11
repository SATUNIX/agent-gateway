"""Application settings sourced from environment variables."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import List

from pydantic import BaseModel, Field


def _split_csv(value: str | None) -> List[str]:
    if not value:
        return ["*"]
    parts = [item.strip() for item in value.split(",") if item.strip()]
    return parts or ["*"]


def _env_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


class Settings(BaseModel):
    """Runtime configuration for the Agent Gateway service."""

    project_name: str = Field(default="Agent Gateway")
    version: str = Field(default="0.1.0")
    api_key: str | None = Field(default=None, description="Gateway API key for auth")
    cors_origins: List[str] = Field(default_factory=lambda: ["*"])
    agent_config_path: str = Field(
        default="config/agents.yaml", description="Path to agents YAML file"
    )
    agent_auto_reload: bool = Field(
        default=False, description="Reload agent config when file changes"
    )
    agent_discovery_path: str = Field(
        default="agents",
        description="Root directory containing drop-in SDK agents",
    )
    agent_discovery_package: str = Field(
        default="agents",
        description="Python package name corresponding to the discovery root",
    )
    upstream_config_path: str = Field(
        default="config/upstreams.yaml", description="Path to upstreams YAML file"
    )
    upstream_auto_reload: bool = Field(
        default=False, description="Reload upstream config when file changes"
    )
    tool_config_path: str = Field(
        default="config/tools.yaml", description="Path to tool definitions"
    )
    tool_auto_reload: bool = Field(
        default=False, description="Reload tools when config changes"
    )
    security_config_path: str = Field(
        default="config/security.yaml", description="Path to API key security config"
    )
    log_level: str = Field(default="INFO", description="Application log level")
    prometheus_enabled: bool = Field(
        default=False, description="Expose Prometheus metrics endpoint"
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings once per process."""

    cors_value = os.getenv("GATEWAY_CORS_ORIGINS")
    agent_auto_reload = _env_bool(os.getenv("GATEWAY_AGENT_AUTO_RELOAD"), False)
    upstream_auto_reload = _env_bool(
        os.getenv("GATEWAY_UPSTREAM_AUTO_RELOAD"), False
    )

    tool_auto_reload = _env_bool(os.getenv("GATEWAY_TOOL_AUTO_RELOAD"), False)

    prometheus_enabled = _env_bool(os.getenv("GATEWAY_PROMETHEUS_ENABLED"), False)

    return Settings(
        project_name=os.getenv("GATEWAY_PROJECT_NAME", "Agent Gateway"),
        version=os.getenv("GATEWAY_VERSION", "0.1.0"),
        api_key=os.getenv("GATEWAY_API_KEY"),
        cors_origins=_split_csv(cors_value),
        agent_config_path=os.getenv("GATEWAY_AGENT_CONFIG", "config/agents.yaml"),
        agent_auto_reload=agent_auto_reload,
        agent_discovery_path=os.getenv("GATEWAY_AGENT_DISCOVERY_PATH", "agents"),
        agent_discovery_package=os.getenv("GATEWAY_AGENT_DISCOVERY_PACKAGE", "agents"),
        upstream_config_path=os.getenv(
            "GATEWAY_UPSTREAM_CONFIG", "config/upstreams.yaml"
        ),
        upstream_auto_reload=upstream_auto_reload,
        tool_config_path=os.getenv("GATEWAY_TOOL_CONFIG", "config/tools.yaml"),
        tool_auto_reload=tool_auto_reload,
        security_config_path=os.getenv(
            "GATEWAY_SECURITY_CONFIG", "config/security.yaml"
        ),
        log_level=os.getenv("GATEWAY_LOG_LEVEL", "INFO"),
        prometheus_enabled=prometheus_enabled,
    )
