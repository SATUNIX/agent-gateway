"""Acceptance tests for drop-in OpenAI Agents SDK modules.

All tests are marked as expected failures until Steps 2–4 of the
Enablement Plan land. They act as executable documentation for the
required behavior.
"""

from __future__ import annotations

import pathlib

import pytest

from tests.fixtures.dropin_agents import DROPIN_FIXTURES


pytestmark = pytest.mark.skip(reason="Drop-in SDK support not implemented yet")


def _materialize_fixture(tmp_path: pathlib.Path, name: str) -> pathlib.Path:
    """Write the requested fixture under agents/<Name>/agent.py."""

    agent_dir = tmp_path / "agents" / name
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "__init__.py").write_text("", encoding="utf-8")
    (agent_dir / "agent.py").write_text(DROPIN_FIXTURES[name], encoding="utf-8")
    return agent_dir


class TestDropInAgents:
    def test_agent_visible_via_models_endpoint(self, tmp_path, client):
        """Dropping an agent folder should expose it via /v1/models without YAML edits."""

        _materialize_fixture(tmp_path, "handoff_triad")
        # TODO: trigger discovery reload and assert /v1/models includes the agent ID.
        raise NotImplementedError

    def test_chat_completion_streams_from_dropin_agent(self, tmp_path, client):
        """Chat completions against a drop-in agent should stream SSE chunks."""

        _materialize_fixture(tmp_path, "dynamic_prompt")
        # TODO: POST /v1/chat/completions?stream=true and validate chunk ordering/content.
        raise NotImplementedError

    def test_tool_invocation_uses_sdk_tooling(self, tmp_path, client):
        """SDK-decorated tools must execute via Runner without schema rewrites."""

        _materialize_fixture(tmp_path, "basic_tool")
        # TODO: invoke agent, assert tool output surfaces directly and metrics/logs capture call.
        raise NotImplementedError

    def test_handoff_flow_executes_downstream_agent(self, tmp_path, client):
        """Handoff agents should transition control exactly as defined in SDK code."""

        _materialize_fixture(tmp_path, "lifecycle_hooks")
        # TODO: run chat completion and verify downstream multiply agent result is returned.
        raise NotImplementedError

    def test_guardrail_blocks_input(self, tmp_path, client):
        """Input guardrails must be evaluated when the drop-in agent runs through the gateway."""

        _materialize_fixture(tmp_path, "guardrail")
        # TODO: send disallowed prompt and expect guardrail tripwire/HTTP 4xx response.
        raise NotImplementedError

    def test_manager_agent_exposes_subagents_as_tools(self, tmp_path, client):
        """Agents that as_tool() other agents must remain callable via the chat endpoint."""

        _materialize_fixture(tmp_path, "manager_tools")
        # TODO: run conversation verifying specialized agent output surfaces when invoked as a tool.
        raise NotImplementedError
