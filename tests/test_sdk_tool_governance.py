from __future__ import annotations

from api.metrics import metrics
from agents.policies import ExecutionPolicy
from api.models.chat import ChatCompletionRequest, ChatMessage
from registry.models import AgentSpec
from sdk_adapter.adapter import SDKAgentAdapter


def _plain_tool(**kwargs):  # noqa: ANN401
    return kwargs.get("value", "ok")


class FakeSDKAgent:
    instructions = "test"
    tools = [_plain_tool]

    def run_sync(self, *, messages, request, policy, client):  # noqa: ANN401
        return self.tools[0](value="ok")


def test_sdk_agent_with_native_tool_is_instrumented(monkeypatch):
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

    class DummyClient:
        base_url = "http://dummy"

    class FakeModule:
        agent = FakeSDKAgent()

    monkeypatch.setattr("sdk_adapter.adapter.import_module", lambda name: FakeModule)

    before = metrics.tool_invocations
    response = adapter.run_agent(
        module_path="tests.fixtures.fake",
        agent=agent_spec,
        client=DummyClient(),
        request=request,
        messages=[m.model_dump() for m in request.messages],
        policy=ExecutionPolicy(),
    )

    assert response.choices[0].message.content == "ok"
    assert metrics.tool_invocations == before + 1
