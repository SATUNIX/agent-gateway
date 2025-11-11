"""Application settings sourced from environment variables."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import BaseModel, Field

PACKAGE_DIR = Path(__file__).resolve().parent
SRC_ROOT = PACKAGE_DIR.parent
CONFIG_DIR = PACKAGE_DIR
AGENTS_DIR = SRC_ROOT / "agents"


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
        default=str(CONFIG_DIR / "agents.yaml"),
        description="Path to agents YAML file",
    )
    agent_auto_reload: bool = Field(
        default=False, description="Reload agent config when file changes"
    )
    agent_discovery_path: str = Field(
        default=str(AGENTS_DIR),
        description="Root directory containing drop-in SDK agents",
    )
    agent_discovery_package: str = Field(
        default="agents",
        description="Python package name corresponding to the discovery root",
    )
    upstream_config_path: str = Field(
        default=str(CONFIG_DIR / "upstreams.yaml"),
        description="Path to upstreams YAML file",
    )
    upstream_auto_reload: bool = Field(
        default=False, description="Reload upstream config when file changes"
    )
    tool_config_path: str = Field(
        default=str(CONFIG_DIR / "tools.yaml"),
        description="Path to tool definitions",
    )
    tool_auto_reload: bool = Field(
        default=False, description="Reload tools when config changes"
    )
    security_config_path: str = Field(
        default=str(CONFIG_DIR / "security.yaml"),
        description="Path to API key security config",
    )
    log_level: str = Field(default="INFO", description="Application log level")
    prometheus_enabled: bool = Field(
        default=False, description="Expose Prometheus metrics endpoint"
    )
    agent_export_names: List[str] = Field(
        default_factory=lambda: ["agent", "build_agent"],
        description="Attribute names inspected during drop-in discovery",
    )
    agent_default_namespace: str = Field(
        default="default", description="Fallback namespace for drop-in agents"
    )
    agent_default_upstream: str | None = Field(
        default=None, description="Fallback upstream when YAML defaults missing"
    )
    agent_default_model: str | None = Field(
        default=None, description="Fallback model when YAML defaults missing"
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

    export_names_env = os.getenv("GATEWAY_AGENT_EXPORTS")
    agent_export_names = (
        _split_csv(export_names_env) if export_names_env else ["agent", "build_agent"]
    )

    return Settings(
        project_name=os.getenv("GATEWAY_PROJECT_NAME", "Agent Gateway"),
        version=os.getenv("GATEWAY_VERSION", "0.1.0"),
        api_key=os.getenv("GATEWAY_API_KEY"),
        cors_origins=_split_csv(cors_value),
        agent_config_path=os.getenv(
            "GATEWAY_AGENT_CONFIG", str(CONFIG_DIR / "agents.yaml")
        ),
        agent_auto_reload=agent_auto_reload,
        agent_discovery_path=os.getenv(
            "GATEWAY_AGENT_DISCOVERY_PATH", str(AGENTS_DIR)
        ),
        agent_discovery_package=os.getenv("GATEWAY_AGENT_DISCOVERY_PACKAGE", "agents"),
        upstream_config_path=os.getenv(
            "GATEWAY_UPSTREAM_CONFIG", str(CONFIG_DIR / "upstreams.yaml")
        ),
        upstream_auto_reload=upstream_auto_reload,
        tool_config_path=os.getenv(
            "GATEWAY_TOOL_CONFIG", str(CONFIG_DIR / "tools.yaml")
        ),
        tool_auto_reload=tool_auto_reload,
        security_config_path=os.getenv(
            "GATEWAY_SECURITY_CONFIG", str(CONFIG_DIR / "security.yaml")
        ),
        log_level=os.getenv("GATEWAY_LOG_LEVEL", "INFO"),
        prometheus_enabled=prometheus_enabled,
        agent_export_names=agent_export_names,
        agent_default_namespace=os.getenv("GATEWAY_DEFAULT_NAMESPACE", "default"),
        agent_default_upstream=os.getenv("GATEWAY_DEFAULT_UPSTREAM"),
        agent_default_model=os.getenv("GATEWAY_DEFAULT_MODEL"),
    )
