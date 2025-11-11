"""Example SDK agent implementations for testing and documentation."""

from __future__ import annotations

from typing import Any, Dict, List


class EchoSDKAgent:
    """Simple agent that echoes the most recent user message."""

    def __init__(self, *, client: Any, agent: Any) -> None:
        self._client = client
        self._agent = agent

    def run_sync(
        self,
        *,
        messages: List[Dict[str, Any]],
        request: Any,
        policy: Any,
        client: Any,
    ) -> str:
        user_messages = [m.get("content", "") for m in messages if m.get("role") == "user"]
        latest = user_messages[-1] if user_messages else ""
        client_label = getattr(self._client, "base_url", "client")
        return f"[SDK:{client_label}] {latest}".strip()


def build_agent(**kwargs: Any) -> EchoSDKAgent:
    """Factory referenced by src/config/agents.yaml for SDK agents."""

    return EchoSDKAgent(client=kwargs.get("client"), agent=kwargs.get("agent"))


def return_string_agent(**kwargs: Any) -> str:
    """Demonstrates that agents may directly return string outputs."""

    messages = kwargs.get("messages", [])
    user_messages = [m.get("content", "") for m in messages if m.get("role") == "user"]
    return user_messages[-1] if user_messages else "No input"


def broken_agent(**kwargs: Any):
    """Raises an exception to simulate a faulty SDK module."""

    raise RuntimeError("Broken SDK agent")
