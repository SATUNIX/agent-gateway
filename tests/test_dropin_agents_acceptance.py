"""Acceptance tests for drop-in OpenAI Agents SDK modules."""

from __future__ import annotations

import json
from types import SimpleNamespace

from tests.fixtures.dropin_agents import materialize_fixture


DEV_HEADERS = {"x-api-key": "dev-secret"}


def _register_fixture(env, fixture_name: str, agent_folder: str) -> str:
    materialize_fixture(env.agents_root, fixture_name, agent_folder)
    env.registry.refresh()
    slug = agent_folder.lower()
    return f"default/{slug}"


def test_dropin_agent_visible_via_models_endpoint(dropin_gateway):
    agent_id = _register_fixture(dropin_gateway, "basic_echo", "EchoAgent")

    response = dropin_gateway.client.get("/v1/models", headers=DEV_HEADERS)
    assert response.status_code == 200
    payload = response.json()
    model_ids = {entry["id"] for entry in payload["data"]}
    assert agent_id in model_ids


def test_dropin_agent_handles_standard_completion(dropin_gateway):
    agent_id = _register_fixture(dropin_gateway, "basic_echo", "EchoAgent")

    response = dropin_gateway.client.post(
        "/v1/chat/completions",
        headers=DEV_HEADERS,
        json={
            "model": agent_id,
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": False,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    message = payload["choices"][0]["message"]["content"]
    assert message == "ECHO:Hello"


def test_dropin_agent_streams_gateway_tool_results(dropin_gateway):
    agent_id = _register_fixture(dropin_gateway, "gateway_tool", "ToolAgent")

    with dropin_gateway.client.stream(
        "POST",
        "/v1/chat/completions",
        headers=DEV_HEADERS,
        json={
            "model": agent_id,
            "messages": [
                {"role": "user", "content": "Summarize this sentence please."}
            ],
            "stream": True,
        },
    ) as response:
        assert response.status_code == 200
        content = _collect_sse_content(response)
        assert "Summary" in content or "Summarize" in content


def _collect_sse_content(response) -> str:
    """Return concatenated content from an SSE response."""

    chunks: list[str] = []
    for line in response.iter_lines():
        if not line:
            continue
        if not line.startswith("data:"):
            continue
        payload = line[len("data: ") :]
        if payload == "[DONE]":
            break
        data = json.loads(payload)
        delta = data["choices"][0]["delta"]
        if delta.get("content"):
            chunks.append(delta["content"])
    return "".join(chunks)


def test_agent_builder_imports_and_runs(dropin_gateway, monkeypatch):
    agent_id = _register_fixture(dropin_gateway, "agent_builder", "BuilderAgent")

    class FakeRunner:
        @staticmethod
        async def run(agent_obj, *, input):  # type: ignore[override]
            return SimpleNamespace(final_output="builder-ok")

    monkeypatch.setattr("agents.Runner", FakeRunner)

    response = dropin_gateway.client.post(
        "/v1/chat/completions",
        headers=DEV_HEADERS,
        json={
            "model": agent_id,
            "messages": [{"role": "user", "content": "Hi"}],
            "stream": False,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["choices"][0]["message"]["content"] == "builder-ok"
