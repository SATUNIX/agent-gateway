from __future__ import annotations

import pytest

from agents.executor import AgentExecutor, AgentExecutionError
from agents.policies import ExecutionPolicy
from api.models.chat import ChatCompletionRequest, ChatMessage
from registry.models import AgentSpec, ToolSpec


def _build_agent_with_tools() -> AgentSpec:
    return AgentSpec(
        name="tool-agent",
        namespace="default",
        display_name="Tool Agent",
        description="",
        kind="declarative",
        upstream="mock",
        model="mock-model",
        instructions="Use tools.",
        tools=["summarize_text", "http_echo"],
        metadata={"tool_choice": "auto"},
    )


def test_build_payload_includes_tool_definitions(monkeypatch):
    tool_specs = {
        "summarize_text": ToolSpec(
            name="summarize_text",
            provider="local",
            module="tooling.local_tools:summarize_text",
            schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
        ),
        "http_echo": ToolSpec(
            name="http_echo",
            provider="http",
            url="https://example.com/echo",
            method="POST",
        ),
    }

    monkeypatch.setattr("agents.executor.tool_manager", type("T", (), {"list_tools": lambda self=None: tool_specs})())

    executor = AgentExecutor()
    agent = _build_agent_with_tools()
    request = ChatCompletionRequest(
        model=agent.qualified_name,
        messages=[ChatMessage(role="user", content="hi")],
        stream=False,
    )

    payload = executor._build_payload(agent, request, ExecutionPolicy())

    assert "tools" in payload
    assert len(payload["tools"]) == 2
    names = {entry["function"]["name"] for entry in payload["tools"]}
    assert {"summarize_text", "http_echo"} <= names
    assert payload["tool_choice"] == "auto"


def test_build_payload_raises_on_unknown_tool(monkeypatch):
    monkeypatch.setattr("agents.executor.tool_manager", type("T", (), {"list_tools": lambda self=None: {}})())

    executor = AgentExecutor()
    agent = _build_agent_with_tools()
    request = ChatCompletionRequest(
        model=agent.qualified_name,
        messages=[ChatMessage(role="user", content="hi")],
        stream=False,
    )

    with pytest.raises(AgentExecutionError):
        executor._build_payload(agent, request, ExecutionPolicy())
