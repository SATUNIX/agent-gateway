"""Tests for the MCP client helper."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Iterable, List

import pytest

from tooling.mcp_client import MCPClient


class FakeResponse:
    def __init__(self, text: str = "ok", status_code: int = 200, lines: Iterable[str] | None = None):
        self.text = text
        self.status_code = status_code
        self._lines = lines or []

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("error")

    def iter_lines(self) -> Iterable[str]:
        for line in self._lines:
            yield line


class FakeClient:
    def __init__(self) -> None:
        self.latest_payload: Dict[str, Any] | None = None

    def post(self, url: str, json: Dict[str, Any]) -> FakeResponse:  # noqa: ANN401
        self.latest_payload = json
        return FakeResponse(text="success")

    @contextmanager
    def stream(self, method: str, url: str, json: Dict[str, Any]):  # noqa: ANN401
        self.latest_payload = json
        yield FakeResponse(lines=["chunk-1", "chunk-2"])


def test_mcp_client_posts_payload() -> None:
    client = MCPClient("https://mcp.example.com", client=FakeClient())
    result = client.invoke(method="current", arguments={"city": "Lisbon"}, context={}, streaming=False)
    assert result == "success"


def test_mcp_client_streams_payload() -> None:
    fake_client = FakeClient()
    client = MCPClient("https://mcp.example.com", client=fake_client)
    result = client.invoke(method="current", arguments={"city": "Lisbon"}, context={}, streaming=True)
    assert result == "chunk-1\nchunk-2"
    assert fake_client.latest_payload is not None
