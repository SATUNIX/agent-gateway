"""Utility layer for dynamically loading and executing SDK agents."""

from __future__ import annotations

import inspect
import importlib.util
import sys
import logging
import math
import time
from importlib import import_module
import asyncio
from pathlib import Path
from typing import Any, Dict, List, AsyncIterator
from uuid import uuid4
from time import perf_counter

from agents.policies import ExecutionPolicy
from api.models.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    ChatCompletionChoice,
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionChunkChoiceDelta,
    ToolCall,
    ToolCallFunction,
    Usage,
)
from api.services.streaming import encode_sse_chunk, iter_sse_from_response
from observability.context import get_request_id
from registry.models import AgentSpec
from sdk_adapter.context import pop_run_context, push_run_context
from sdk_adapter.context import get_run_context
from api.metrics import metrics, record_upstream_call
from tooling import tool_manager, ToolInvocationContext
from security import security_manager


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
        symbol = self._import_symbol(module_path, agent)
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

    async def stream_agent(
        self,
        *,
        agent: AgentSpec,
        client: Any,
        request: ChatCompletionRequest,
        messages: List[Dict[str, Any]],
        policy: ExecutionPolicy,
    ) -> AsyncIterator[str]:
        logger.info(
            {
                "event": "sdk_agent.stream.start",
                "agent": agent.qualified_name,
                "module": agent.module,
                "message_count": len(messages),
            }
        )
        symbol = self._import_symbol(agent.module, agent)
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
            if self._is_openai_agent(instance):
                async for chunk in self._stream_openai_agent(
                    instance, messages, client, agent
                ):
                    yield chunk
            else:
                result = self._execute_agent(instance, messages, request, policy, client)
                response = self._normalize_result(result, agent)
                for chunk in iter_sse_from_response(response):
                    yield chunk
            logger.info(
                {
                    "event": "sdk_agent.stream.success",
                    "agent": agent.qualified_name,
                    "module": agent.module,
                }
            )
        except Exception:
            logger.exception(
                {
                    "event": "sdk_agent.stream.failure",
                    "agent": agent.qualified_name,
                    "module": agent.module,
                }
            )
            raise
        finally:
            pop_run_context(token)

    def _import_symbol(self, module_path: str, agent: AgentSpec) -> Any:
        if ":" in module_path:
            module_name, attr = module_path.split(":", 1)
        else:
            module_name, attr = module_path, None
        try:
            module = import_module(module_name)
        except Exception as exc:  # noqa: BLE001
            module = self._import_module_from_file(agent, module_name, exc)
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

    def _import_module_from_file(self, agent: AgentSpec, module_name: str, original_exc: Exception):
        source_file = agent.metadata.get("source_file") if agent.metadata else None
        if not source_file:
            raise SDKAgentError(
                f"Module '{module_name}' not importable and no source file provided"
            ) from original_exc
        path = Path(source_file)
        if not path.exists():
            raise SDKAgentError(
                f"Module '{module_name}' source file missing at {source_file}"
            ) from original_exc
        spec = importlib.util.spec_from_file_location(
            f"_gateway_dropin_{path.stem}", path
        )
        if spec is None or spec.loader is None:
            raise SDKAgentError(
                f"Unable to load module from source file {source_file}"
            ) from original_exc
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

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
        runner_input = self._build_runner_input(messages)
        start = perf_counter()
        success = False

        async def _run() -> Any:
            result = await runner_cls.run(agent_obj, input=runner_input, client=client)
            if hasattr(result, "final_output"):
                return result.final_output  # type: ignore[attr-defined]
            if hasattr(result, "final_output_as"):
                return result.final_output_as(str)  # type: ignore[attr-defined]
            return result

        try:
            output = self._run_coroutine(_run())
            success = True
            return str(output)
        finally:
            latency_ms = (perf_counter() - start) * 1000
            record_upstream_call(getattr(client, "base_url", "sdk"), latency_ms, success)

    async def _stream_openai_agent(
        self, agent_obj: Any, messages: List[Dict[str, Any]], client: Any, agent: AgentSpec
    ) -> AsyncIterator[str]:
        runner_cls = self._load_runner()
        runner_input = self._build_runner_input(messages)
        start = perf_counter()
        success = False

        async def _maybe_stream(result: Any):
            if hasattr(result, "__aiter__"):
                async for delta in result:
                    yield delta
            else:
                yield result

        try:
            result = await runner_cls.run(agent_obj, input=runner_input, client=client, stream=True)
            async for delta in _maybe_stream(result):
                chunk = self._build_chunk_from_delta(delta, agent.model)
                yield encode_sse_chunk(chunk)
                if chunk.choices[0].finish_reason:
                    break
            yield "data: [DONE]\\n\\n"
            success = True
        finally:
            latency_ms = (perf_counter() - start) * 1000
            record_upstream_call(getattr(client, "base_url", "sdk"), latency_ms, success)

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
            entry: Dict[str, Any] = {
                "role": message.get("role"),
                "content": message.get("content"),
            }
            tool_calls = message.get("tool_calls")
            if tool_calls:
                entry["tool_calls"] = tool_calls
            if message.get("name"):
                entry["name"] = message["name"]
            if message.get("tool_call_id"):
                entry["tool_call_id"] = message["tool_call_id"]
            input_items.append(entry)
        return input_items

    def _build_chunk_from_delta(self, delta: Any, model: str) -> ChatCompletionChunk:
        payload = delta
        if hasattr(delta, "__dict__"):
            payload = delta.__dict__
        role = payload.get("role")
        content = payload.get("content")
        tool_calls_raw = payload.get("tool_calls") or []
        finish_reason = payload.get("finish_reason")
        tool_calls: list[ToolCall] = []
        for call in tool_calls_raw:
            call_payload = call
            if hasattr(call, "__dict__"):
                call_payload = call.__dict__
            func = call_payload.get("function") or {}
            tool_calls.append(
                ToolCall(
                    id=call_payload.get("id") or f"call_{uuid4().hex[:8]}",
                    type="function",
                    function=ToolCallFunction(
                        name=func.get("name") or "",
                        arguments=func.get("arguments") or "",
                    ),
                )
            )
        chunk = ChatCompletionChunk(
            id=self._build_completion_id(),
            object="chat.completion.chunk",
            created=int(time.time()),
            model=model,
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkChoiceDelta(
                        role=role,
                        content=self._coerce_text(content),
                        tool_calls=tool_calls or None,
                    ),
                    finish_reason=finish_reason,
                )
            ],
        )
        return chunk

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

    def _enforce_sdk_tool_governance(self, target: Any) -> None:
        """Wrap native SDK tools to run through gateway governance/metrics."""

        tools = getattr(target, "tools", None)
        if not tools:
            return
        instrumented: list[Any] = []
        for tool in tools:
            if getattr(tool, "__gateway_tool__", False):
                instrumented.append(tool)
                continue
            instrumented.append(self._wrap_native_tool(tool))
        target.tools = instrumented

    def _wrap_native_tool(self, tool: Any):
        name = getattr(tool, "__name__", "tool")
        available = tool_manager.list_tools()
        if name in available:

            def _gateway_tool(**kwargs: Any):
                ctx = get_run_context()
                if ctx is None:
                    raise SDKAgentError("Gateway tool invoked outside of agent execution context")
                invocation = self._build_invocation_context(ctx)
                return tool_manager.invoke_tool(name, kwargs, invocation)

            _gateway_tool.__name__ = name
            _gateway_tool.__doc__ = getattr(tool, "__doc__", None)
            _gateway_tool.__gateway_tool__ = True
            return _gateway_tool

        module_path = f"{tool.__module__}:{name}"

        def _native_tool(**kwargs: Any):
            ctx = get_run_context()
            if ctx is None:
                raise SDKAgentError("Native tool invoked outside of agent execution context")
            security_manager.assert_tool_allowed(module_path)
            start = perf_counter()
            success = False
            try:
                result = tool(**kwargs)
                success = True
                return result
            finally:
                latency_ms = (perf_counter() - start) * 1000
                metrics.record_tool_invocation(
                    tool_name=name,
                    provider="native",
                    latency_ms=latency_ms,
                    success=success,
                    source="sdk",
                )

        _native_tool.__name__ = name
        _native_tool.__doc__ = getattr(tool, "__doc__", None)
        _native_tool.__gateway_tool__ = True
        return _native_tool

    @staticmethod
    def _build_invocation_context(ctx) -> ToolInvocationContext:
        request_id = get_request_id() or ctx.request_id or f"dropin-{uuid4().hex}"
        return ToolInvocationContext(
            agent_name=ctx.agent_spec.qualified_name,
            request_id=request_id,
            policy=ctx.policy,
            user=ctx.request.user,
            source="sdk",
        )
