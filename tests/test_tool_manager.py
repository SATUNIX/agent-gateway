"""Tests for the ToolManager providers."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.policies import ExecutionPolicy
from tooling.manager import ToolExecutionError, ToolInvocationContext, ToolManager


@pytest.fixture()
def tool_manager(tmp_path: Path) -> ToolManager:
    config = tmp_path / "tools.yaml"
    config.write_text(
        """
version: 1
tools:
  - name: local_test
    provider: local
    module: tooling.local_tools:summarize_text
    schema:
      required: ["text"]
""",
        encoding="utf-8",
    )
    return ToolManager(config_path=config, auto_reload=False)


def test_local_tool_invocation(tool_manager: ToolManager) -> None:
    context = ToolInvocationContext(
        agent_name="default/test",
        request_id="req-123",
        policy=ExecutionPolicy(max_tool_hops=1),
        user="tester",
    )
    output = tool_manager.invoke_tool(
        "local_test",
        {"text": "one two three", "max_words": 2},
        context,
    )
    assert "Summary" in output


def test_unknown_tool(tool_manager: ToolManager) -> None:
    context = ToolInvocationContext(
        agent_name="default/test",
        request_id="req-123",
        policy=ExecutionPolicy(),
        user=None,
    )
    with pytest.raises(Exception):
        tool_manager.invoke_tool("missing", {}, context)


def test_schema_validation(tool_manager: ToolManager) -> None:
    context = ToolInvocationContext(
        agent_name="default/test",
        request_id="req-456",
        policy=ExecutionPolicy(),
        user=None,
    )
    with pytest.raises(ToolExecutionError):
        tool_manager.invoke_tool("local_test", {"max_words": 5}, context)
