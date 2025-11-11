"""Unit tests for the SDK adapter helpers."""

from __future__ import annotations

import pytest

from agents.policies import ExecutionPolicy
from api.models.chat import ChatCompletionRequest, ChatMessage
from registry.models import AgentSpec
from sdk_adapter import SDKAgentAdapter, SDKAgentError


class DummyClient:
    base_url = "http://dummy"


def build_agent_spec(module: str) -> AgentSpec:
    return AgentSpec(
        name="sdk-test",
        namespace="default",
        display_name="SDK Test",
        description="Test agent",
        kind="sdk",
        upstream="lmstudio",
        model="gpt-4o-mini",
        module=module,
        tools=[],
    )


def test_adapter_runs_sync_agent() -> None:
    adapter = SDKAgentAdapter()
    spec = build_agent_spec("agents.sdk_example:build_agent")
    request = ChatCompletionRequest(
        model="sdk-test",
        messages=[ChatMessage(role="user", content="Hello there!")],
    )

    response = adapter.run_agent(
        module_path=spec.module,
        agent=spec,
        client=DummyClient(),
        request=request,
        messages=[msg.model_dump() for msg in request.messages],
        policy=ExecutionPolicy(),
    )

    assert response.choices[0].message.content.startswith("[SDK:http://dummy]")


def test_adapter_raises_for_bad_path() -> None:
    adapter = SDKAgentAdapter()
    spec = build_agent_spec("agents.sdk_example")
    request = ChatCompletionRequest(
        model="sdk-test",
        messages=[ChatMessage(role="user", content="Hello")],
    )

    with pytest.raises(SDKAgentError):
        adapter.run_agent(
            module_path=spec.module,
            agent=spec,
            client=DummyClient(),
            request=request,
            messages=[msg.model_dump() for msg in request.messages],
            policy=ExecutionPolicy(),
        )


def test_adapter_surfaces_exceptions_from_sdk_module() -> None:
    adapter = SDKAgentAdapter()
    spec = build_agent_spec("agents.sdk_example:broken_agent")
    request = ChatCompletionRequest(
        model="sdk-test",
        messages=[ChatMessage(role="user", content="Hello")],
    )

    with pytest.raises(SDKAgentError):
        adapter.run_agent(
            module_path=spec.module,
            agent=spec,
            client=DummyClient(),
            request=request,
            messages=[msg.model_dump() for msg in request.messages],
            policy=ExecutionPolicy(),
        )


def test_adapter_executes_raw_agent(monkeypatch) -> None:
    adapter = SDKAgentAdapter()
    spec = build_agent_spec("tests.fixtures.raw_agent_module:agent")
    request = ChatCompletionRequest(
        model="sdk-test",
        messages=[ChatMessage(role="user", content="Describe the plan.")],
    )

    class FakeRunner:
        @staticmethod
        async def run(agent_obj, input, **kwargs):  # type: ignore[unused-argument]
            return type("Result", (), {"final_output": f"{agent_obj.label}:{input}"})()

    monkeypatch.setattr(SDKAgentAdapter, "_load_runner", lambda self: FakeRunner)

    response = adapter.run_agent(
        module_path=spec.module,
        agent=spec,
        client=DummyClient(),
        request=request,
        messages=[msg.model_dump() for msg in request.messages],
        policy=ExecutionPolicy(),
    )

    assert response.choices[0].message.content.startswith("stub:")


def test_adapter_accepts_agent_factory(monkeypatch) -> None:
    adapter = SDKAgentAdapter()
    spec = build_agent_spec("tests.fixtures.raw_agent_module:build_agent")
    request = ChatCompletionRequest(
        model="sdk-test",
        messages=[ChatMessage(role="user", content="Hi")],
    )

    class FakeRunner:
        @staticmethod
        async def run(agent_obj, input, **kwargs):  # type: ignore[unused-argument]
            return type("Result", (), {"final_output": f"{agent_obj.label}:{input}"})()

    monkeypatch.setattr(SDKAgentAdapter, "_load_runner", lambda self: FakeRunner)

    response = adapter.run_agent(
        module_path=spec.module,
        agent=spec,
        client=DummyClient(),
        request=request,
        messages=[msg.model_dump() for msg in request.messages],
        policy=ExecutionPolicy(),
    )

    assert response.choices[0].message.content.startswith("factory:")
