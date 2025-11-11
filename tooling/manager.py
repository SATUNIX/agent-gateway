"""Centralized tool manager handling MCP, HTTP, and local providers."""

from __future__ import annotations

import importlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Optional

import httpx
import yaml

from agents.policies import ExecutionPolicy
from api.metrics import metrics
from config import get_settings
from registry.models import ToolSpec, ToolsFile
from security import security_manager
from tooling.mcp_client import MCPClient
from observability.context import get_request_id


class ToolExecutionError(RuntimeError):
    """Raised when a tool invocation fails."""


@dataclass
class ToolInvocationContext:
    agent_name: str
    request_id: str
    policy: ExecutionPolicy
    user: Optional[str]


logger = logging.getLogger("agent_gateway.tooling")


class ToolManager:
    def __init__(self, config_path: Path, auto_reload: bool = False) -> None:
        self._config_path = config_path
        self._auto_reload = auto_reload
        self._tools: Dict[str, ToolSpec] = {}
        self._local_cache: Dict[str, Any] = {}
        self._last_mtime = 0.0
        self._mcp_clients: Dict[str, MCPClient] = {}
        self._load(force=True)

    @classmethod
    def from_settings(cls) -> "ToolManager":
        settings = get_settings()
        return cls(
            config_path=Path(settings.tool_config_path).resolve(),
            auto_reload=settings.tool_auto_reload,
        )

    def invoke_tool(
        self, name: str, arguments: Dict[str, Any], context: ToolInvocationContext
    ) -> str:
        self._auto_reload_if_needed()
        spec = self._tools.get(name)
        if not spec:
            raise ToolExecutionError(f"Unknown tool: {name}")
        self._validate_arguments(spec, arguments)
        start = perf_counter()
        success = False
        try:
            if spec.provider == "local":
                result = self._invoke_local_tool(spec, arguments, context)
            elif spec.provider == "http":
                result = self._invoke_http_tool(spec, arguments)
            elif spec.provider == "mcp":
                result = self._invoke_mcp_tool(spec, arguments, context)
            else:
                raise ToolExecutionError(f"Unsupported tool provider: {spec.provider}")
            success = True
            return result
        finally:
            latency_ms = (perf_counter() - start) * 1000
            metrics.record_tool_invocation(
                tool_name=spec.name,
                provider=spec.provider,
                latency_ms=latency_ms,
                success=success,
            )
            self._log_tool_event(
                tool=spec.name,
                provider=spec.provider,
                arguments=arguments,
                latency_ms=latency_ms,
                success=success,
            )

    def list_tools(self) -> Dict[str, ToolSpec]:
        self._auto_reload_if_needed()
        return dict(self._tools)

    def refresh(self) -> None:
        self._load(force=True)

    def _invoke_local_tool(
        self, spec: ToolSpec, arguments: Dict[str, Any], context: ToolInvocationContext
    ) -> str:
        if not spec.module:
            raise ToolExecutionError(
                f"Local tool '{spec.name}' is missing the 'module' attribute"
            )
        security_manager.assert_tool_allowed(spec.module)
        func = self._get_local_callable(spec.module)
        result = func(arguments=arguments, context=context)
        return self._stringify_result(result)

    def _invoke_http_tool(self, spec: ToolSpec, arguments: Dict[str, Any]) -> str:
        if not spec.url:
            raise ToolExecutionError(
                f"HTTP tool '{spec.name}' is missing the 'url' attribute"
            )
        method = (spec.method or "POST").upper()
        try:
            with httpx.Client(timeout=spec.timeout, headers=spec.headers) as client:
                if method == "GET":
                    response = client.get(str(spec.url), params=arguments)
                else:
                    response = client.request(method, str(spec.url), json=arguments)
                response.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            raise ToolExecutionError(
                f"HTTP tool '{spec.name}' failed: {exc}"
            ) from exc
        return response.text

    def _invoke_mcp_tool(
        self,
        spec: ToolSpec,
        arguments: Dict[str, Any],
        context: ToolInvocationContext,
    ) -> str:
        if not spec.url or not spec.method:
            raise ToolExecutionError(
                f"MCP tool '{spec.name}' requires 'url' and 'method' attributes"
            )
        mcp_client = self._get_mcp_client(spec)
        payload_context = {
            "agent": context.agent_name,
            "user": context.user,
            "policy": context.policy.max_tool_hops,
        }
        try:
            return mcp_client.invoke(
                method=spec.method,
                arguments=arguments,
                context=payload_context,
                streaming=spec.stream,
            )
        except Exception as exc:  # noqa: BLE001
            raise ToolExecutionError(
                f"MCP tool '{spec.name}' failed: {exc}"
            ) from exc

    def _log_tool_event(
        self,
        *,
        tool: str,
        provider: str,
        arguments: Dict[str, Any],
        latency_ms: float,
        success: bool,
    ) -> None:
        level = logging.INFO if success else logging.WARNING
        logger.log(
            level,
            {
                "event": "tool.invoke",
                "tool": tool,
                "provider": provider,
                "latency_ms": round(latency_ms, 3),
                "status": "success" if success else "failure",
                "arguments": arguments,
                "request_id": get_request_id(),
            },
        )

    def _auto_reload_if_needed(self) -> None:
        if not self._auto_reload:
            return
        try:
            mtime = self._config_path.stat().st_mtime
        except FileNotFoundError:
            return
        if mtime <= self._last_mtime:
            return
        self._load(force=True)

    def _load(self, force: bool = False) -> None:
        path = self._config_path
        if not path.exists():
            raise FileNotFoundError(f"Tool configuration file not found: {path}")
        mtime = path.stat().st_mtime
        if not force and mtime <= self._last_mtime:
            return
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        parsed = ToolsFile(**data)
        self._tools = {tool.name: tool for tool in parsed.tools}
        self._last_mtime = mtime
        self._mcp_clients.clear()

    def _get_local_callable(self, module_path: str) -> Any:
        if module_path in self._local_cache:
            return self._local_cache[module_path]
        if ":" not in module_path:
            raise ToolExecutionError(
                f"Local tool paths must use 'module:callable' format (got {module_path})"
            )
        module_name, attr = module_path.split(":", 1)
        module = importlib.import_module(module_name)
        func = getattr(module, attr, None)
        if func is None or not callable(func):
            raise ToolExecutionError(
                f"Callable '{attr}' not found or not callable in module '{module_name}'"
            )
        self._local_cache[module_path] = func
        return func

    def _get_mcp_client(self, spec: ToolSpec) -> MCPClient:
        url = str(spec.url)
        if url in self._mcp_clients:
            return self._mcp_clients[url]
        client = MCPClient(
            base_url=url,
            timeout=spec.timeout,
            headers=spec.headers or None,
        )
        self._mcp_clients[url] = client
        return client

    def _validate_arguments(self, spec: ToolSpec, arguments: Dict[str, Any]) -> None:
        schema = spec.schema or {}
        required = schema.get("required", [])
        for field in required:
            if field not in arguments:
                raise ToolExecutionError(
                    f"Tool '{spec.name}' missing required argument '{field}'"
                )
        properties = schema.get("properties", {})
        for name, meta in properties.items():
            if name not in arguments:
                continue
            expected = meta.get("type")
            if expected and not self._matches_type(arguments[name], expected):
                raise ToolExecutionError(
                    f"Tool '{spec.name}' argument '{name}' expected type '{expected}'"
                )

    @staticmethod
    def _matches_type(value: Any, expected: str) -> bool:
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "object": dict,
            "array": list,
        }
        python_type = type_map.get(expected.lower())
        if python_type is None:
            return True
        return isinstance(value, python_type)

    @staticmethod
    def _stringify_result(result: Any) -> str:
        if isinstance(result, str):
            return result
        if isinstance(result, (dict, list)):
            return json.dumps(result)
        return str(result)


tool_manager = ToolManager.from_settings()
