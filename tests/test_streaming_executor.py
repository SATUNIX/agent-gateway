from __future__ import annotations

import asyncio

from agents.executor import AgentExecutor
from agents.policies import ExecutionPolicy
from api.models.chat import ChatCompletionRequest, ChatMessage
from api.models.chat import ChatCompletionChunkChoice, ChatCompletionChunkChoiceDelta, ChatCompletionChunk
from registry.models import AgentSpec


class FakeChunk:
    def __init__(self, text: str):
        self._payload = {
            "id": "chunk_1",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "mock-model",
            "choices": [
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkChoiceDelta(content=text),
                    finish_reason=None,
                ).model_dump()
            ],
        }

    def model_dump(self):
        return self._payload


class FakeStreamClient:
    def __init__(self) -> None:
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        assert kwargs.get("stream") is True
        return [FakeChunk("hello"), FakeChunk(None)]


class StubUpstreamRegistry:
    def get_client(self, name: str):
        assert name == "mock"
        return FakeStreamClient()


async def collect_stream(stream):
    data = []
    async for chunk in stream:
        data.append(chunk)
    return "".join(data)


def test_declarative_streaming_sse(monkeypatch):
    executor = AgentExecutor()
    executor._upstream_registry = StubUpstreamRegistry()  # type: ignore[attr-defined]

    agent = AgentSpec(
        name="streamer",
        namespace="default",
        display_name="Streamer",
        description="",
        kind="declarative",
        upstream="mock",
        model="mock-model",
        instructions=None,
        tools=[],
        metadata={},
    )
    executor._agent_registry = type(
        "R", (), {"get_agent": lambda self, name: agent}
    )()  # type: ignore[attr-defined]

    request = ChatCompletionRequest(
        model="default/streamer",
        messages=[ChatMessage(role="user", content="hi")],
        stream=True,
    )

    stream = executor.stream_completion(request, auth=type("A", (), {"is_agent_allowed": lambda self, n: True})())
    result = asyncio.run(collect_stream(stream))
    assert "hello" in result
