from __future__ import annotations

import sys
from pathlib import Path

import pytest

from registry.agents import AgentRegistry
from registry.discovery import AgentDiscoverer


def _write_agent_package(root: Path, package: str, folder: str, body: str) -> Path:
    pkg_root = root / package
    pkg_root.mkdir(parents=True, exist_ok=True)
    (pkg_root / "__init__.py").write_text("", encoding="utf-8")
    agent_pkg = pkg_root / folder
    agent_pkg.mkdir(parents=True, exist_ok=True)
    (agent_pkg / "__init__.py").write_text("", encoding="utf-8")
    agent_file = agent_pkg / "agent.py"
    agent_file.write_text(body, encoding="utf-8")
    return pkg_root


def test_discoverer_detects_agent_exports(tmp_path, monkeypatch):
    body = """\
class Agent:
    def __init__(self, name: str):
        self.name = name


agent = Agent(name="Sample")
"""
    pkg_root = _write_agent_package(tmp_path, "agents_pkg", "ResearchAgent", body)
    monkeypatch.syspath_prepend(str(tmp_path))
    discoverer = AgentDiscoverer(pkg_root, "agents_pkg", export_names=["agent", "build_agent"])

    exports = discoverer.discover()

    assert exports, "Expected at least one export"
    agent_exports = [e for e in exports if e.kind == "agent" and e.attribute and e.attribute.lower() == "agent"]
    assert agent_exports, "Expected an 'agent' export in discovered exports"
    export = agent_exports[0]
    assert export.import_path.endswith(":agent")


def test_registry_merges_dropin_agents(tmp_path, monkeypatch):
    config_path = tmp_path / "agents.yaml"
    config_path.write_text(
        """\
version: 1
defaults:
  namespace: dropin
  upstream: lmstudio
  model: gpt-4o-mini
agents: []
""",
        encoding="utf-8",
    )

    body = """\
class Agent:
    def __init__(self, name: str):
        self.name = name


agent = Agent(name="ResearchAgent")
"""
    pkg_root = _write_agent_package(tmp_path, "agents_pkg", "ResearchAgent", body)
    monkeypatch.syspath_prepend(str(tmp_path))

    registry = AgentRegistry(
        config_path=config_path,
        auto_reload=False,
        discovery_root=pkg_root,
        discovery_package="agents_pkg",
    )

    agents = list(registry.list_agents())
    assert agents, "Expected discovered agent in registry"
    names = {agent.name for agent in agents}
    assert "researchagent" in names
    spec = registry.get_agent("researchagent")
    assert spec is not None
    assert spec.namespace == "dropin"
    assert spec.metadata.get("dropin") is True


def test_registry_blocks_disallowed_modules(tmp_path, monkeypatch):
    config_path = tmp_path / "agents.yaml"
    config_path.write_text(
        """\
version: 1
defaults:
  namespace: dropin
  upstream: lmstudio
  model: gpt-4o-mini
agents: []
""",
        encoding="utf-8",
    )
    body = """\
class Agent:
    def __init__(self, name: str):
        self.name = name


agent = Agent(name="ResearchAgent")
"""
    pkg_root = _write_agent_package(tmp_path, "agents_pkg", "ResearchAgent", body)
    monkeypatch.syspath_prepend(str(tmp_path))

    class Blocker:
        def assert_agent_module_allowed(self, module_path: str) -> None:
            raise PermissionError(f"Blocked {module_path}")

    monkeypatch.setattr("registry.agents.security_manager", Blocker())

    registry = AgentRegistry(
        config_path=config_path,
        auto_reload=False,
        discovery_root=pkg_root,
        discovery_package="agents_pkg",
    )

    agents = list(registry.list_agents())
    assert agents == []


def test_registry_respects_custom_allowance(tmp_path, monkeypatch):
    config_path = tmp_path / "agents.yaml"
    config_path.write_text(
        """\
version: 1
defaults:
  namespace: research
  upstream: lmstudio
  model: gpt-4o-mini
agents: []
""",
        encoding="utf-8",
    )
    body = """\
class Agent:
    def __init__(self, name: str):
        self.name = name


agent = Agent(name="ResearchAgent")
"""
    pkg_root = _write_agent_package(tmp_path, "agents_pkg", "ResearchAgent", body)
    monkeypatch.syspath_prepend(str(tmp_path))

    class AllowOnlyResearch:
        def assert_agent_module_allowed(self, module_path: str) -> None:
            if "ResearchAgent" not in module_path:
                raise PermissionError("forbidden")

    monkeypatch.setattr("registry.agents.security_manager", AllowOnlyResearch())

    registry = AgentRegistry(
        config_path=config_path,
        auto_reload=False,
        discovery_root=pkg_root,
        discovery_package="agents_pkg",
    )

    agents = list(registry.list_agents())
    assert len(agents) == 1
    assert agents[0].namespace == "research"
@pytest.fixture(autouse=True)
def allow_all_security(monkeypatch):
    class AllowAll:
        def assert_agent_module_allowed(self, module_path: str) -> None:  # noqa: D401
            return None

    stub = AllowAll()
    monkeypatch.setattr("registry.agents.security_manager", stub)
    return stub
