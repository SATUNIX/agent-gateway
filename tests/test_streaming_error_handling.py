from __future__ import annotations

from fastapi.testclient import TestClient

import api.main as main_app
from agents.executor import AgentNotFoundError


DEV_HEADERS = {"x-api-key": "dev-secret"}


def test_streaming_returns_404_for_missing_agent(monkeypatch):
    def fake_stream_completion(*args, **kwargs):
        raise AgentNotFoundError("Unknown agent or model 'missing'. Register it in src/config/agents.yaml.")

    monkeypatch.setattr(
        "api.services.chat.agent_executor.stream_completion",
        fake_stream_completion,
    )
    client = TestClient(main_app.app)
    response = client.post(
        "/v1/chat/completions",
        headers=DEV_HEADERS,
        json={"model": "missing", "messages": [], "stream": True},
    )
    assert response.status_code == 404
    assert "Unknown agent" in response.text


def test_streaming_returns_403_for_acl_denial(monkeypatch):
    def fake_stream_completion(*args, **kwargs):
        raise PermissionError("API key does not permit access to agent 'forbidden'")

    monkeypatch.setattr(
        "api.services.chat.agent_executor.stream_completion",
        fake_stream_completion,
    )
    client = TestClient(main_app.app)
    response = client.post(
        "/v1/chat/completions",
        headers=DEV_HEADERS,
        json={"model": "forbidden", "messages": [], "stream": True},
    )
    assert response.status_code == 403
    assert "does not permit" in response.text
