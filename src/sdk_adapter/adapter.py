"""Utility layer for dynamically loading and executing SDK agents."""

from __future__ import annotations

import inspect
import logging
import math
import time
from importlib import import_module
import asyncio
from typing import Any, Dict, List
from uuid import uuid4

from agents.policies import ExecutionPolicy
from api.models.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    Usage,
)
from observability.context import get_request_id
from registry.models import AgentSpec
from sdk_adapter.context import pop_run_context, push_run_context


logger = logging.getLogger("agent_gateway.sdk")


class SDKAgentError(RuntimeError):
    """Raised when an SDK-backed agent cannot be executed."""


class SDKAgentAdapter:
    """Provides helper methods to run SDK-defined agents consistently."""

    def run_agent(
        self,
        *,
        module_path: str,
        agent: AgentSpec,
        client: Any,
        request: ChatCompletionRequest,
        messages: List[Dict[str, Any]],
        policy: ExecutionPolicy,
    ) -> ChatCompletionResponse:
        logger.info(
            {
                "event": "sdk_agent.start",
                "agent": agent.qualified_name,
                "module": module_path,
                "message_count": len(messages),
            }
        )
        symbol = self._import_symbol(module_path)
        instance = self._instantiate_symbol(
            symbol,
            agent=agent,
            client=client,
            request=request,
            messages=messages,
            policy=policy,
        )
        self._enforce_sdk_tool_governance(instance)
        token = push_run_context(
            agent_spec=agent,
            request=request,
            messages=messages,
            policy=policy,
            client=client,
            request_id=get_request_id(),
        )
        try:
        result = self._execute_agent(instance, messages, request, policy, client)
            logger.info(
                {
                    "event": "sdk_agent.success",
                    "agent": agent.qualified_name,
                    "module": module_path,
                }
            )
        except Exception:
            logger.exception(
                {
                    "event": "sdk_agent.failure",
                    "agent": agent.qualified_name,
                    "module": module_path,
                }
            )
            raise
        finally:
            pop_run_context(token)
        return self._normalize_result(result, agent)

    @staticmethod
    def _import_symbol(module_path: str) -> Any:
        if ":" in module_path:
            module_name, attr = module_path.split(":", 1)
        else:
            module_name, attr = module_path, None
        module = import_module(module_name)
        if attr:
            if not hasattr(module, attr):
                raise SDKAgentError(
                    f"Attribute '{attr}' not found in module '{module_name}'"
                )
            return getattr(module, attr)
        if hasattr(module, "agent"):
            return getattr(module, "agent")
        raise SDKAgentError(
            f"Module '{module_name}' must expose an 'agent' attribute or use module:attribute path"
        )

    def _instantiate_symbol(
        self,
        symbol: Any,
        *,
        agent: AgentSpec,
        client: Any,
        request: ChatCompletionRequest,
        messages: List[Dict[str, Any]],
        policy: ExecutionPolicy,
    ) -> Any:
        if self._is_openai_agent(symbol):
            return symbol
        if callable(symbol):
            try:
                instance = symbol(
                    agent=agent,
                    client=client,
                    request=request,
                    messages=messages,
                    policy=policy,
                )
            except TypeError:
                instance = symbol()
            return instance
        return symbol

    def _execute_agent(
        self,
        target: Any,
        messages: List[Dict[str, Any]],
        request: ChatCompletionRequest,
        policy: ExecutionPolicy,
        client: Any,
    ) -> Any:
        if target is None:
            raise SDKAgentError("SDK agent factory returned None")

        if self._is_openai_agent(target):
            return self._run_openai_agent(target, messages, client)

        if hasattr(target, "run_sync"):
            return target.run_sync(
                messages=messages, request=request, policy=policy, client=client
            )
        if hasattr(target, "run"):
            result = target.run(
                messages=messages, request=request, policy=policy, client=client
            )
            if inspect.isawaitable(result):
                return self._run_coroutine(result)
            return result
        if callable(target):
            result = target(
                messages=messages, request=request, policy=policy, client=client
            )
            if inspect.isawaitable(result):
                return self._run_coroutine(result)
            return result
        return target

    def _normalize_result(
        self, result: Any, agent: AgentSpec
    ) -> ChatCompletionResponse:
        if isinstance(result, ChatCompletionResponse):
            return result
        if isinstance(result, dict):
            return ChatCompletionResponse.model_validate(result)
        if isinstance(result, str):
            return self._build_string_response(result, agent)
        raise SDKAgentError(
            "SDK agents must return ChatCompletionResponse, dict, or string"
        )

    def _build_string_response(
        self, content: str, agent: AgentSpec
    ) -> ChatCompletionResponse:
        message = ChatMessage(role="assistant", content=content)
        usage = self._build_usage_from_text(content)
        return ChatCompletionResponse(
            id=self._build_completion_id(),
            object="chat.completion",
            created=int(time.time()),
            model=agent.model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=message,
                    finish_reason="stop",
                )
            ],
            usage=usage,
        )

    @staticmethod
    def _build_completion_id() -> str:
        return f"cmpl_{uuid4().hex}"

    @staticmethod
    def _build_usage_from_text(text: str) -> Usage:
        tokens = SDKAgentAdapter._count_tokens(text)
        return Usage(
            prompt_tokens=0,
            completion_tokens=tokens,
            total_tokens=tokens,
        )

    @staticmethod
    def _count_tokens(text: str) -> int:
        if not text:
            return 0
        return max(1, math.ceil(len(text.split()) * 1.5))

    def _run_openai_agent(
        self, agent_obj: Any, messages: List[Dict[str, Any]], client: Any
    ) -> str:
        runner_cls = self._load_runner()

        async def _run() -> Any:
            runner_input = self._build_runner_input(messages)
            result = await runner_cls.run(agent_obj, input=runner_input, client=client)
            if hasattr(result, "final_output"):
                return result.final_output  # type: ignore[attr-defined]
            if hasattr(result, "final_output_as"):
                return result.final_output_as(str)  # type: ignore[attr-defined]
            return result

        return str(self._run_coroutine(_run()))

    def _load_runner(self):
        try:
            from agents import Runner, SDK_AVAILABLE
        except ImportError as exc:  # pragma: no cover - import failures
            raise SDKAgentError(
                "OpenAI Agents SDK is required to execute Agent objects"
            ) from exc
        if not SDK_AVAILABLE:
            raise SDKAgentError(
                "OpenAI Agents SDK is required to execute Agent objects. "
                "Install 'openai-agents' to run Agent Builder drop-ins."
            )
        return Runner

    @staticmethod
    def _build_runner_input(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert ChatCompletion messages into SDK-friendly input items."""

        input_items: list[Dict[str, Any]] = []
        for message in messages:
            entry: Dict[str, Any] = {"role": message.get("role"), "content": message.get("content")}
            tool_calls = message.get("tool_calls")
            if tool_calls:
                entry["tool_calls"] = tool_calls
            if message.get("name"):
                entry["name"] = message["name"]
            if message.get("tool_call_id"):
                entry["tool_call_id"] = message["tool_call_id"]
            input_items.append(entry)
        return input_items

    @staticmethod
    def _coerce_text(content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    parts.append(str(item.get("text", "")))
                else:
                    parts.append(str(item))
            return "".join(parts)
        return str(content)

    @staticmethod
    def _run_coroutine(coro):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            return asyncio.run_coroutine_threadsafe(coro, loop).result()
        new_loop = asyncio.new_event_loop()
        try:
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()

    @staticmethod
    def _is_openai_agent(obj: Any) -> bool:
        cls = getattr(obj, "__class__", None)
        if cls is None:
            return False
        return cls.__name__ == "Agent" and hasattr(obj, "instructions")

    @staticmethod
    def _enforce_sdk_tool_governance(target: Any) -> None:
        """Require SDK tools to be gateway-managed for observability/ACLs."""

        tools = getattr(target, "tools", None)
        if not tools:
            return
        unmanaged = [tool for tool in tools if not getattr(tool, "__gateway_tool__", False)]
        if unmanaged:
            names = [getattr(t, "__name__", "tool") for t in unmanaged]
            raise SDKAgentError(
                "SDK agent tools must use sdk_adapter.gateway_tools.use_gateway_tool(...) "
                "so the gateway can enforce allowlists and record metrics. "
                f"Unmanaged tools: {', '.join(names)}"
            )
