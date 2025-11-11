"""Tests for the UpstreamRegistry client loader and health probe."""

from __future__ import annotations

from pathlib import Path

import pytest

from registry.upstreams import UpstreamRegistry


class DummyOpenAI:
    def __init__(self, *, base_url: str, api_key: str) -> None:
        self.base_url = base_url
        self.api_key = api_key


class DummyResponse:
    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code
        self.text = "ok"


def test_upstream_registry_loads(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config = tmp_path / "upstreams.yaml"
    config.write_text(
        """
version: 1
upstreams:
  - name: mock
    provider: openai-compatible
    base_url: http://mock-upstream
    priority: 1
    api_key: mock
    health_path: /health
""",
        encoding="utf-8",
    )

    monkeypatch.setattr("registry.upstreams.OpenAI", DummyOpenAI)
    monkeypatch.setattr("registry.upstreams.httpx.get", lambda url, timeout: DummyResponse())

    registry = UpstreamRegistry(config_path=config, auto_reload=False)
    record = registry.get_record("mock")
    assert record is not None
    assert record.spec.name == "mock"
    assert record.healthy is True
    assert isinstance(record.client, DummyOpenAI)
