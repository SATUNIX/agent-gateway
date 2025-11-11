from __future__ import annotations

import pytest

from agents.policies import ExecutionPolicy
from api.models.chat import ChatCompletionRequest
from registry.models import AgentSpec
from sdk_adapter.context import pop_run_context, push_run_context
from sdk_adapter.gateway_tools import gateway_tool


def _build_agent_spec() -> AgentSpec:
    return AgentSpec(
        name="sample",
        namespace="default",
        display_name="Sample Agent",
        description="",
        kind="sdk",
        upstream="lmstudio",
        model="gpt-4o-mini",
        module="tests.fixtures.raw_agent_module:agent",
    )


def test_gateway_tool_invokes_tool_manager(monkeypatch):
    captured = {}

    def fake_invoker(tool_name, arguments, context):
        captured["tool_name"] = tool_name
        captured["arguments"] = arguments
        captured["context"] = context
        return "ok"

    class DummyManager:
        @staticmethod
        def invoke_tool(tool_name, arguments, context):
            return fake_invoker(tool_name, arguments, context)

    def fake_function_tool(func):
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    monkeypatch.setattr(
        "sdk_adapter.gateway_tools.tool_manager",
        DummyManager,
    )
    monkeypatch.setattr(
        "sdk_adapter.gateway_tools._resolve_function_tool",
        lambda: fake_function_tool,
    )

    spec = _build_agent_spec()
    request = ChatCompletionRequest(model="sample", messages=[])
    token = push_run_context(
        agent_spec=spec,
        request=request,
        messages=[],
        policy=ExecutionPolicy(),
        client=object(),
        request_id="req-123",
    )
    try:
        tool = gateway_tool("http_echo")
        result = tool(city="NYC")
    finally:
        pop_run_context(token)

    assert result == "ok"
    assert captured["tool_name"] == "http_echo"
    assert captured["arguments"] == {"city": "NYC"}
    assert captured["context"].agent_name == spec.qualified_name


def test_gateway_tool_propagates_permission_error(monkeypatch):
    class DummyManager:
        @staticmethod
        def invoke_tool(tool_name, arguments, context):
            raise PermissionError("blocked")

    monkeypatch.setattr(
        "sdk_adapter.gateway_tools.tool_manager",
        DummyManager,
    )
    monkeypatch.setattr(
        "sdk_adapter.gateway_tools._resolve_function_tool",
        lambda: (lambda func: func),
    )

    spec = _build_agent_spec()
    request = ChatCompletionRequest(model="sample", messages=[])
    token = push_run_context(
        agent_spec=spec,
        request=request,
        messages=[],
        policy=ExecutionPolicy(),
        client=object(),
        request_id="req-123",
    )
    try:
        tool = gateway_tool("restricted")
        with pytest.raises(PermissionError):
            tool()
    finally:
        pop_run_context(token)
