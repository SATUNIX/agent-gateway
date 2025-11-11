"""Tests for the AgentRegistry loader and lookups."""

from __future__ import annotations

from pathlib import Path
import time

from registry.agents import AgentRegistry


def write_agents_config(path: Path) -> None:
    path.write_text(
        """
version: 1
defaults:
  namespace: default
  upstream: mock
  model: mock-model

agents:
  - name: helper
    display_name: Helper
    description: Test helper
    kind: declarative
    instructions: |
      Be helpful.
    tools: []

  - name: sdk-agent
    namespace: sdk
    display_name: SDK Agent
    description: Runs python code.
    kind: sdk
    module: agents.sdk_example:build_agent
    instructions: null
""",
        encoding="utf-8",
    )


def test_agent_registry_loads_and_queries(tmp_path: Path) -> None:
    config_path = tmp_path / "agents.yaml"
    write_agents_config(config_path)
    registry = AgentRegistry(config_path=config_path, auto_reload=False)

    agents = list(registry.list_agents())
    assert len(agents) == 2
    assert agents[0].qualified_name == "default/helper"

    helper = registry.get_agent("helper")
    assert helper is not None
    assert helper.namespace == "default"

    sdk_agent = registry.get_agent("sdk/sdk-agent")
    assert sdk_agent is not None
    assert sdk_agent.kind == "sdk"


def test_agent_registry_auto_reload_detects_changes(tmp_path: Path) -> None:
    config_path = tmp_path / "agents.yaml"
    write_agents_config(config_path)
    registry = AgentRegistry(config_path=config_path, auto_reload=True)

    sdk_agent = registry.get_agent("sdk/sdk-agent")
    assert sdk_agent is not None
    assert sdk_agent.instructions is None

    config_path.write_text(
        """
version: 1
defaults:
  namespace: sdk
  upstream: mock
  model: mock-model

agents:
  - name: sdk-agent
    display_name: SDK Agent
    description: Updated description.
    kind: sdk
    module: agents.sdk_example:build_agent
    instructions: Updated instructions.
""",
        encoding="utf-8",
    )
    time.sleep(0.05)  # ensure mtime advances
    registry.list_agents()  # trigger auto-reload
    sdk_agent = registry.get_agent("sdk/sdk-agent")
    assert sdk_agent is not None
    assert sdk_agent.instructions == "Updated instructions."
