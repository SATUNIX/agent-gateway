"""End-to-end smoke test for the Agent Gateway."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List

from fastapi.testclient import TestClient

import api.main as main_app
from agents.executor import AgentExecutor
from registry.models import AgentSpec


class FakeCompletion:
    def __init__(self, payload: Dict[str, Any]) -> None:
        self._payload = payload

    def model_dump(self) -> Dict[str, Any]:
        return self._payload


class FakeChat:
    def create(self, **kwargs: Any) -> FakeCompletion:  # noqa: ANN401
        messages: List[Dict[str, Any]] = kwargs["messages"]
        tool_messages = [m for m in messages if m.get("role") == "tool"]
        if not tool_messages:
            arguments = json.dumps(
                {
                    "text": " ".join(m["content"] for m in messages if m.get("role") == "user")
                }
            )
            payload = {
                "id": "cmpl_smoke",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": kwargs["model"],
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {"name": "summarize_text", "arguments": arguments},
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
            return FakeCompletion(payload)

        last_tool = tool_messages[-1]["content"]
        payload = {
            "id": "cmpl_smoke",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": kwargs["model"],
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": f"Tool result: {last_tool}",
                        "tool_calls": None,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 2, "completion_tokens": 2, "total_tokens": 4},
        }
        return FakeCompletion(payload)


class FakeOpenAI:
    def __init__(self, **_: Any) -> None:  # noqa: ANN401
        self.chat = FakeChat()


class FakeAgentRegistry:
    def __init__(self) -> None:
        self._agent = AgentSpec(
            name="smoke",
            namespace="default",
            display_name="Smoke",
            description="",
            kind="declarative",
            upstream="mock",
            model="mock-model",
            instructions="You are a smoke tester.",
            tools=["summarize_text"],
            metadata={"max_tool_hops": 2},
        )

    def list_agents(self):  # noqa: D401
        return [self._agent]

    def get_agent(self, name: str):  # noqa: D401
        if name in {"smoke", "default/smoke"}:
            return self._agent
        return None


class FakeUpstreamRegistry:
    def get_client(self, name: str) -> FakeOpenAI:  # noqa: D401
        assert name == "mock"
        return FakeOpenAI()


client = TestClient(main_app.app)


def _inject_fake_executor() -> None:
    from agents import executor as executor_module
    import api.services.chat as chat_service_module

    fake_executor = AgentExecutor()
    fake_executor._agent_registry = FakeAgentRegistry()  # type: ignore[attr-defined]
    fake_executor._upstream_registry = FakeUpstreamRegistry()  # type: ignore[attr-defined]
    executor_module.agent_executor = fake_executor
    chat_service_module.agent_executor = fake_executor


def test_gateway_smoke_round_trip() -> None:
    _inject_fake_executor()
    response = client.post(
        "/v1/chat/completions",
        headers={"x-api-key": "dev-secret"},
        json={
            "model": "smoke",
            "messages": [{"role": "user", "content": "Please summarize this tool call."}],
            "stream": False,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["choices"][0]["finish_reason"] == "stop"
    assert payload["choices"][0]["message"]["content"].startswith("Tool result:")
*** End Patch
