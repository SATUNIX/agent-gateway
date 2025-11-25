"""Async SDK agent fixture for tests."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List


class AsyncAgent:
    async def run(self, *, messages: List[Dict[str, Any]], **_: Any) -> str:  # noqa: ANN401
        await asyncio.sleep(0)
        return "async-response"


def build_agent(**_: Any) -> AsyncAgent:
    return AsyncAgent()
