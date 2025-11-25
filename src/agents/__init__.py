"""Agent utilities and shared policies."""

from typing import Any

from .policies import ExecutionPolicy

try:
    from openai_agents import (  # type: ignore
        Agent,
        Runner,
        function_tool,
        ModelSettings,
        RunConfig,
        TResponseInputItem,
    )
    SDK_AVAILABLE = True
except Exception:  # pragma: no cover - fallback for environments without the SDK
    SDK_AVAILABLE = False

    class _MissingDependency:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise ImportError(
                "The 'openai-agents' package is required for Agent Builder drop-ins. "
                "Add it to your environment or install via requirements.txt."
            )

    def function_tool(*args: Any, **kwargs: Any):  # type: ignore[misc]
        raise ImportError(
            "The 'openai-agents' package is required for Agent Builder drop-ins. "
            "Add it to your environment or install via requirements.txt."
        )

    Agent = _MissingDependency  # type: ignore[assignment]
    Runner = _MissingDependency  # type: ignore[assignment]
    ModelSettings = _MissingDependency  # type: ignore[assignment]
    RunConfig = _MissingDependency  # type: ignore[assignment]
    TResponseInputItem = Any  # type: ignore[assignment]


__all__ = [
    "ExecutionPolicy",
    "Agent",
    "Runner",
    "function_tool",
    "ModelSettings",
    "RunConfig",
    "TResponseInputItem",
    "SDK_AVAILABLE",
]
