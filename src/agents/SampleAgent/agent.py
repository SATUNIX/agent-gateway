"""Minimal SampleAgent drop-in to validate discovery and execution."""

from typing import Any, Dict, List


class SampleAgent:
    """Simple echo agent used as the default drop-in example."""

    def run_sync(
        self,
        *,
        messages: List[Dict[str, Any]],
        request: Any = None,
        policy: Any = None,
        client: Any = None,
    ) -> str:
        user_messages = [m.get("content", "") for m in messages if m.get("role") == "user"]
        latest = user_messages[-1] if user_messages else ""
        return f"[SampleAgent] {latest}".strip()


agent = SampleAgent()

__gateway__ = {
    "display_name": "Sample Agent",
    "description": "Reference drop-in agent that echoes the latest user message.",
}
