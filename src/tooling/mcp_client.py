"""Simple MCP client supporting HTTP POST and SSE streaming."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

import httpx


class MCPClient:
    """Minimal MCP transport helper."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 10.0,
        headers: Optional[Dict[str, str]] = None,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self._base_url = base_url
        self._own_client = client is None
        self._client = client or httpx.Client(timeout=timeout, headers=headers or {})

    def invoke(
        self,
        *,
        method: str,
        arguments: Dict[str, Any],
        context: Dict[str, Any],
        streaming: bool = False,
    ) -> str:
        payload = {"method": method, "arguments": arguments, "context": context}
        if streaming:
            return self._stream_payload(payload)
        response = self._client.post(self._base_url, json=payload)
        response.raise_for_status()
        return response.text

    def _stream_payload(self, payload: Dict[str, Any]) -> str:
        chunks: list[str] = []
        with self._client.stream("POST", self._base_url, json=payload) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                chunks.append(line.decode("utf-8") if isinstance(line, bytes) else line)
        return "\n".join(chunks)

    def close(self) -> None:
        if self._own_client:
            self._client.close()


def drain_stream(stream: Iterable[str]) -> str:
    """Utility used in tests to join SSE lines."""

    return "\n".join(stream)
