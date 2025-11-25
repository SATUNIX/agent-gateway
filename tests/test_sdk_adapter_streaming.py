from __future__ import annotations

import asyncio

import pytest

from agents.policies import ExecutionPolicy
from api.models.chat import ChatCompletionRequest, ChatMessage
from registry.models import AgentSpec
from sdk_adapter.adapter import SDKAgentAdapter


class FakeRunner:
    @staticmethod
    async def run(agent_obj, *, input, client, stream=False):  # type: ignore[override]
        if stream:
            async def _gen():
                yield {"role": "assistant", "content": "hello", "finish_reason": None}
                yield {"role": None, "content": None, "finish_reason": "stop"}

            return _gen()
        return type("Result", (), {"final_output": "hello"})()


def build_agent_spec(module: str) -> AgentSpec:
    return AgentSpec(
        name="sdk-stream",
        namespace="default",
        display_name="SDK Stream",
        description="",
        kind="sdk",
        upstream="lmstudio",
        model="gpt-4o-mini",
        module=module,
        tools=[],
    )


@pytest.mark.asyncio
async def test_stream_openai_agent_yields_sse(monkeypatch):
    adapter = SDKAgentAdapter()
    spec = build_agent_spec("tests.fixtures.raw_agent_module:agent")
    request = ChatCompletionRequest(
        model="sdk-stream",
        messages=[ChatMessage(role="user", content="hi")],
        stream=True,
    )

    monkeypatch.setattr(SDKAgentAdapter, "_load_runner", lambda self: FakeRunner)

    chunks = []
    async for entry in adapter.stream_agent(
        agent=spec,
        client=object(),
        request=request,
        messages=[msg.model_dump() for msg in request.messages],
        policy=ExecutionPolicy(),
    ):
        chunks.append(entry)

    payload = "".join(chunks)
    assert "hello" in payload
    assert "[DONE]" in payload
