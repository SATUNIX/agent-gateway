from __future__ import annotations

import asyncio
from typing import Any, Dict, Iterator, List

import pytest

from agents.executor import AgentExecutor
from api.models.chat import (
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionChunkChoiceDelta,
    ChatCompletionRequest,
    ChatMessage,
    ToolCall,
    ToolCallFunction,
)
from registry.models import AgentSpec
from security.manager import AuthContext


class FakeChat:
    def __init__(self) -> None:
        self._tool_phase_done = False

    def create(self, stream: bool, **kwargs: Any) -> Iterator[ChatCompletionChunk]:
        assert stream is True
        messages = kwargs["messages"]
        has_tool_response = any(m.get("role") == "tool" for m in messages)
        if not has_tool_response:
            chunk1 = ChatCompletionChunk(
                id="cmpl_stream",
                object="chat.completion.chunk",
                created=123,
                model=kwargs["model"],
                choices=[
                    ChatCompletionChunkChoice(
                        index=0,
                        delta=ChatCompletionChunkChoiceDelta(
                            role="assistant",
                            content=None,
                            tool_calls=[
                                ToolCall(
                                    id="call_1",
                                    type="function",
                                    function=ToolCallFunction(
                                        name="summarize_text", arguments='{"text": "hello world"}'
                                    ),
                                )
                            ],
                        ),
                        finish_reason=None,
                    )
                ],
            )
            chunk2 = ChatCompletionChunk(
                id="cmpl_stream",
                object="chat.completion.chunk",
                created=123,
                model=kwargs["model"],
                choices=[
                    ChatCompletionChunkChoice(
                        index=0,
                        delta=ChatCompletionChunkChoiceDelta(role=None, content=None, tool_calls=None),
                        finish_reason="tool_calls",
                    )
                ],
            )
            return iter([chunk1, chunk2])

        chunk = ChatCompletionChunk(
            id="cmpl_stream",
            object="chat.completion.chunk",
            created=123,
            model=kwargs["model"],
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkChoiceDelta(role="assistant", content="Summary", tool_calls=None),
                    finish_reason="stop",
                )
            ],
        )
        return iter([chunk])


class FakeClient:
    def __init__(self) -> None:
        self.chat = FakeChat()


class FakeUpstreamRegistry:
    def get_client(self, name: str) -> FakeClient:
        assert name == "mock"
        return FakeClient()


class FakeAgentRegistry:
    def __init__(self) -> None:
        self._agent = AgentSpec(
            name="streamer",
            namespace="default",
            display_name="Streamer",
            description="",
            kind="declarative",
            upstream="mock",
            model="gpt-test",
            instructions="Stream with tool calls.",
            tools=["summarize_text"],
            metadata={"max_tool_hops": 2},
        )

    def get_agent(self, name: str) -> AgentSpec | None:
        if name in {"default/streamer", "streamer"}:
            return self._agent
        return None


@pytest.mark.asyncio
async def test_streaming_tool_calls_execute_and_continue(monkeypatch):
    executor = AgentExecutor()
    executor._agent_registry = FakeAgentRegistry()  # type: ignore[attr-defined]
    executor._upstream_registry = FakeUpstreamRegistry()  # type: ignore[attr-defined]

    request = ChatCompletionRequest(
        model="default/streamer",
        messages=[ChatMessage(role="user", content="Hello")],
        stream=True,
    )
    auth = AuthContext(key_id=None, allow_agents=["*"], rate_limit_per_minute=10_000)

    chunks: List[str] = []
    async for chunk in executor.stream_completion(request, auth):
        chunks.append(chunk)

    content = "".join(
        json_payload.get("choices", [{}])[0]
        .get("delta", {})
        .get("content", "")
        for json_payload in (
            _parse_sse_data(entry) for entry in chunks if entry.startswith("data:") and "[DONE]" not in entry
        )
    )
    assert "Summary" in content


def _parse_sse_data(entry: str) -> Dict[str, Any]:
    payload = entry[len("data: ") :].strip()
    import json

    return json.loads(payload)
