"""Helpers for calling gateway-managed tools from drop-in SDK agents."""

from __future__ import annotations

from typing import Any, Callable, Dict
from uuid import uuid4

from agents.policies import ExecutionPolicy
from observability.context import get_request_id
from sdk_adapter.context import get_run_context
from tooling import ToolInvocationContext, tool_manager


_TOOL_WRAPPER_CACHE: Dict[str, Callable[..., Any]] = {}


def gateway_tool(tool_name: str, *, description: str | None = None) -> Callable[..., Any]:
    """Return (and cache) a function_tool proxy backed by the gateway tool manager.

    Example usage inside an OpenAI Agents SDK module::

        from sdk_adapter.gateway_tools import use_gateway_tool

        http_echo = use_gateway_tool("http_echo")

        agent = Agent(name="Echo", tools=[http_echo])
    """

    cached = _TOOL_WRAPPER_CACHE.get(tool_name)
    if cached is not None and description is None:
        return cached

    _ensure_tool_available(tool_name)
    function_tool = _resolve_function_tool()

    @function_tool  # type: ignore[misc]
    def _gateway_tool(**arguments: Any) -> str:
        ctx = get_run_context()
        if ctx is None:
            raise RuntimeError("Gateway tool invoked outside of agent execution context")

        invocation = _build_invocation_context(ctx.policy, ctx)
        payload = arguments or {}
        return tool_manager.invoke_tool(tool_name, payload, invocation)

    _gateway_tool.__name__ = f"gateway_{tool_name}"
    _gateway_tool.__doc__ = description or f"Gateway-managed tool '{tool_name}'"
    _gateway_tool.__gateway_tool__ = True  # marker for governance checks
    _TOOL_WRAPPER_CACHE[tool_name] = _gateway_tool
    return _gateway_tool


def use_gateway_tool(tool_name: str, *, description: str | None = None) -> Callable[..., Any]:
    """Ergonomic helper that auto-discovers gateway tools and caches wrappers."""

    return gateway_tool(tool_name, description=description)


def _resolve_function_tool() -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    try:
        from agents import function_tool
    except ImportError as exc:  # pragma: no cover - SDK required for runtime use
        raise RuntimeError(
            "The openai-agents package is required to use gateway-managed tools"
        ) from exc
    return function_tool


def _build_invocation_context(policy: ExecutionPolicy, ctx) -> ToolInvocationContext:
    request_id = get_request_id() or ctx.request_id or f"dropin-{uuid4().hex}"
    return ToolInvocationContext(
        agent_name=ctx.agent_spec.qualified_name,
        request_id=request_id,
        policy=policy,
        user=ctx.request.user,
        source="sdk",
    )


def _ensure_tool_available(tool_name: str) -> None:
    tools = tool_manager.list_tools()
    if tool_name not in tools:
        raise RuntimeError(
            f"Gateway-managed tool '{tool_name}' not found. Check src/config/tools.yaml."
        )


__all__ = ["gateway_tool", "use_gateway_tool"]
