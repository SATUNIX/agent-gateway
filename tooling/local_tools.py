"""Collection of local Python tool implementations."""

from __future__ import annotations

from typing import Any, Dict

from tooling.manager import ToolInvocationContext


def summarize_text(
    *, arguments: Dict[str, Any], context: ToolInvocationContext
) -> str:
    """Return a concise summary of the provided text argument."""

    text = str(arguments.get("text", "")).strip()
    if not text:
        return "No text provided for summarization."
    words = text.split()
    max_words = int(arguments.get("max_words", 40))
    summary = " ".join(words[:max_words])
    suffix = "..." if len(words) > max_words else ""
    return f"Summary ({context.agent_name}): {summary}{suffix}"

