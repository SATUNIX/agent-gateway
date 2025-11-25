from __future__ import annotations

from pathlib import Path

import pytest

from registry.agents import AgentRegistry
from config import get_settings


def _write_agents_config(path: Path) -> None:
    path.write_text(
        """
version: 1
defaults:
  namespace: default
  upstream: mock
  model: mock-model
agents: []
""",
        encoding="utf-8",
    )


def test_registry_discovers_examples_root(tmp_path, monkeypatch):
    examples_root = tmp_path / "examples" / "agents" / "DemoAgent"
    examples_root.mkdir(parents=True, exist_ok=True)
    agent_file = examples_root / "agent.py"
    agent_file.write_text(
        """
class DemoAgent:
    def run_sync(self, *, messages, **kwargs):
        return "ok"


agent = DemoAgent()
""",
        encoding="utf-8",
    )

    config_path = tmp_path / "agents.yaml"
    _write_agents_config(config_path)

    monkeypatch.setenv("GATEWAY_AGENT_CONFIG", str(config_path))
    monkeypatch.setenv("GATEWAY_AGENT_DISCOVERY_PATH", str(tmp_path / "src" / "agents"))
    monkeypatch.setenv("GATEWAY_AGENT_DISCOVERY_EXTRA_PATHS", str(examples_root.parent))
    get_settings.cache_clear()

    registry = AgentRegistry(
        config_path=config_path,
        auto_reload=False,
    )

    agents = list(registry.list_agents())
    discovered = [a for a in agents if a.metadata.get("source_file") == str(agent_file)]
    assert discovered, "Expected example agent to be discovered from extra path"

    get_settings.cache_clear()
