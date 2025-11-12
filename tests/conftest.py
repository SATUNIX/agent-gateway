from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api.main as main_app
import agents.executor as executor_module
import api.services.chat as chat_services
import api.routes.admin as admin_routes
import api.routes.models as model_routes
import registry as registry_pkg
from agents.executor import AgentExecutor
from config import get_settings
from registry.agents import AgentRegistry


class _StubUpstreamRegistry:
    def get_client(self, _: str) -> object:  # noqa: D401
        return object()


@dataclass
class DropInGatewayEnv:
    client: TestClient
    registry: AgentRegistry
    agents_root: Path


@pytest.fixture()
def dropin_gateway(tmp_path, monkeypatch) -> DropInGatewayEnv:
    tmp_src = tmp_path / "src"
    package_name = "dropin_agents_pkg"
    agents_root = tmp_src / package_name
    agents_root.mkdir(parents=True, exist_ok=True)
    (agents_root / "__init__.py").write_text("", encoding="utf-8")

    monkeypatch.syspath_prepend(str(tmp_src))
    monkeypatch.setenv("GATEWAY_AGENT_WATCH", "0")

    get_settings.cache_clear()

    config_path = Path("src/config/agents.yaml").resolve()
    agent_registry = AgentRegistry(
        config_path=config_path,
        auto_reload=False,
        discovery_root=agents_root,
        discovery_package=package_name,
    )

    executor = AgentExecutor()
    executor._agent_registry = agent_registry  # type: ignore[attr-defined]
    executor._upstream_registry = _StubUpstreamRegistry()  # type: ignore[attr-defined]

    original_executor = executor_module.agent_executor
    executor_module.agent_executor = executor
    chat_services.agent_executor = executor

    original_registry = registry_pkg.agent_registry
    registry_pkg.agent_registry = agent_registry
    admin_routes.agent_registry = agent_registry
    model_routes.agent_registry = agent_registry

    client = TestClient(main_app.app)

    yield DropInGatewayEnv(client=client, registry=agent_registry, agents_root=agents_root)

    client.close()
    executor_module.agent_executor = original_executor
    chat_services.agent_executor = original_executor
    registry_pkg.agent_registry = original_registry
    admin_routes.agent_registry = original_registry
    model_routes.agent_registry = original_registry
    get_settings.cache_clear()
