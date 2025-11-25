from __future__ import annotations

import pytest

from sdk_adapter.adapter import SDKAgentAdapter, SDKAgentError
from agents.policies import ExecutionPolicy
from api.models.chat import ChatCompletionRequest, ChatMessage
from registry.models import AgentSpec


def _plain_tool(**kwargs):  # noqa: ANN401
    return "ok"


class FakeSDKAgent:
    instructions = "test"
    tools = [_plain_tool]

    def run_sync(self, *, messages, request, policy, client):  # noqa: ANN401
        return "noop"


def test_sdk_agent_with_unmanaged_tools_is_blocked():
    adapter = SDKAgentAdapter()
    agent_spec = AgentSpec(
        name="sdk",
        namespace="default",
        display_name="SDK",
        description="",
        kind="sdk",
        upstream="mock",
        model="mock-model",
        instructions=None,
        module="tests.fixtures.fake",
        tools=["plain_tool"],
        metadata={},
    )
    request = ChatCompletionRequest(model="sdk", messages=[ChatMessage(role="user", content="hi")])
    with pytest.raises(SDKAgentError) as excinfo:
        adapter.run_agent(
            module_path="tests.fixtures.fake",
            agent=agent_spec,
            client=object(),
            request=request,
            messages=[m.model_dump() for m in request.messages],
            policy=ExecutionPolicy(),
        )
    assert "use_gateway_tool" in str(excinfo.value)
