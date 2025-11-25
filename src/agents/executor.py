"""Agent executor responsible for running declarative and SDK agents."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from time import perf_counter

from starlette.concurrency import run_in_threadpool

from agents.policies import ExecutionPolicy
from api.metrics import metrics, record_upstream_call
from api.models.chat import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
)
from registry import agent_registry, upstream_registry
from registry.models import AgentSpec
from tooling import ToolInvocationContext, tool_manager
from sdk_adapter import SDKAgentAdapter, SDKAgentError
from security import AuthContext
from observability.context import update_log_context
from api.services.streaming import encode_sse_chunk, iter_sse_from_response


class AgentNotFoundError(RuntimeError):
    """Raised when a user references an unknown agent."""


class AgentExecutionError(RuntimeError):
    """Raised when an upstream or SDK agent fails."""


sdk_agent_adapter = SDKAgentAdapter()


class AgentExecutor:
    """Coordinates agent resolution and upstream execution."""

    def __init__(self) -> None:
        self._agent_registry = agent_registry
        self._upstream_registry = upstream_registry

    async def create_completion(
        self, request: ChatCompletionRequest, auth: AuthContext
    ) -> ChatCompletionResponse:
        agent = self._resolve_agent(request.model)
        if not auth.is_agent_allowed(agent.qualified_name):
            raise PermissionError(
                f"API key does not permit access to agent '{agent.qualified_name}'"
            )
        update_log_context(
            agent_id=agent.qualified_name,
            module_path=agent.module,
            error_stage="agent_execution",
        )
        policy = self._build_policy(agent, request)
        payload = self._build_payload(agent, request, policy)
        try:
            if agent.kind == "sdk":
                try:
                    return await self._invoke_sdk_agent(agent, payload, request, policy)
                finally:
                    update_log_context(error_stage=None)
            try:
                return await self._run_tool_loop(agent, payload, request, policy)
            finally:
                update_log_context(error_stage=None)
        finally:
            update_log_context(agent_id=None, module_path=None)

    async def stream_completion(
        self, request: ChatCompletionRequest, auth: AuthContext
    ) -> AsyncIterator[str]:
        agent = self._resolve_agent(request.model)
        if not auth.is_agent_allowed(agent.qualified_name):
            raise PermissionError(
                f"API key does not permit access to agent '{agent.qualified_name}'"
            )
        update_log_context(
            agent_id=agent.qualified_name,
            module_path=agent.module,
            error_stage="agent_execution",
        )
        policy = self._build_policy(agent, request)
        payload = self._build_payload(agent, request, policy)
        try:
            if agent.kind == "sdk":
                async for chunk in sdk_agent_adapter.stream_agent(
                    agent=agent,
                    client=self._upstream_registry.get_client(agent.upstream),
                    request=request,
                    messages=payload["messages"],
                    policy=policy,
                ):
                    yield chunk
                return
            async for chunk in self._invoke_declarative_stream(agent, payload, request, policy):
                yield chunk
        finally:
            update_log_context(agent_id=None, module_path=None, error_stage=None)

    def _resolve_agent(self, identifier: str) -> AgentSpec:
        agent = self._agent_registry.get_agent(identifier)
        if not agent:
            raise AgentNotFoundError(
                f"Unknown agent or model '{identifier}'. Register it in src/config/agents.yaml."
            )
        return agent

    def _build_policy(
        self, agent: AgentSpec, request: ChatCompletionRequest
    ) -> ExecutionPolicy:
        metadata = agent.metadata or {}
        max_tokens_from_agent = metadata.get("max_completion_tokens")
        max_tokens = request.max_tokens
        if max_tokens_from_agent is not None:
            try:
                agent_tokens = int(max_tokens_from_agent)
            except (TypeError, ValueError) as exc:  # noqa: PERF203
                raise AgentExecutionError(
                    f"Invalid max_completion_tokens for agent {agent.qualified_name}"
                ) from exc
            max_tokens = min(agent_tokens, max_tokens) if max_tokens else agent_tokens
        policy = ExecutionPolicy(
            max_tool_hops=int(metadata.get("max_tool_hops", 0) or 0),
            max_completion_tokens=max_tokens,
        )
        return policy

    def _build_payload(
        self,
        agent: AgentSpec,
        request: ChatCompletionRequest,
        policy: ExecutionPolicy,
    ) -> Dict[str, Any]:
        messages: List[Dict[str, Any]] = []
        if agent.instructions:
            messages.append({"role": "system", "content": agent.instructions.strip()})
        for msg in request.messages:
            messages.append(msg.model_dump(exclude_none=True))

        payload: Dict[str, Any] = {
            "model": agent.model,
            "messages": messages,
            "temperature": request.temperature,
            "n": request.n,
            "user": request.user,
        }
        if agent.kind == "declarative" and agent.tools:
            tool_defs = self._build_tool_definitions(agent)
            payload["tools"] = tool_defs
            tool_choice = agent.metadata.get("tool_choice") if agent.metadata else None
            if tool_choice:
                payload["tool_choice"] = tool_choice
        if policy.max_completion_tokens is not None:
            payload["max_tokens"] = policy.max_completion_tokens
        elif request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        payload["stream"] = request.stream

        return {k: v for k, v in payload.items() if v is not None}

    async def _invoke_declarative_agent(
        self, agent: AgentSpec, payload: Dict[str, Any]
    ) -> ChatCompletionResponse:
        client = self._upstream_registry.get_client(agent.upstream)
        start = perf_counter()
        success = False

        def run_sync() -> ChatCompletionResponse:
            response = client.chat.completions.create(**payload)
            return ChatCompletionResponse.model_validate(response.model_dump())

        try:
            result = await run_in_threadpool(run_sync)
            success = True
            return result
        except Exception as exc:  # noqa: BLE001
            raise AgentExecutionError(str(exc)) from exc
        finally:
            latency_ms = (perf_counter() - start) * 1000
            record_upstream_call(agent.upstream, latency_ms, success)

    async def _invoke_declarative_stream(
        self,
        agent: AgentSpec,
        payload: Dict[str, Any],
        request: ChatCompletionRequest,
        policy: ExecutionPolicy,
    ) -> AsyncIterator[str]:
        client = self._upstream_registry.get_client(agent.upstream)
        hops = 0

        while True:
            start = perf_counter()
            success = False
            tool_calls: Dict[str, Dict[str, Any]] = {}
            stream_id: str | None = None

            try:
                stream = client.chat.completions.create(stream=True, **payload)
                iterator = iter(stream)
                while True:
                    try:
                        data = await run_in_threadpool(next, iterator)
                    except StopIteration:
                        break
                    chunk_model = ChatCompletionChunk.model_validate(data.model_dump())
                    stream_id = stream_id or chunk_model.id
                    self._accumulate_tool_calls(tool_calls, chunk_model)
                    yield encode_sse_chunk(chunk_model)
                    finish_reason = chunk_model.choices[0].finish_reason
                    if finish_reason and finish_reason != "tool_calls":
                        break
                    if finish_reason == "tool_calls":
                        break
                success = True
            except Exception:  # noqa: BLE001
                response = await self._invoke_declarative_agent(agent, payload | {"stream": False})
                for chunk in iter_sse_from_response(response):
                    yield chunk
                return
            finally:
                latency_ms = (perf_counter() - start) * 1000
                record_upstream_call(agent.upstream, latency_ms, success)

            if not tool_calls:
                break
            if policy.max_tool_hops <= 0:
                break
            if hops >= policy.max_tool_hops:
                raise AgentExecutionError(
                    f"Tool hop limit reached ({policy.max_tool_hops}) for {agent.qualified_name}"
                )
            hops += 1
            tool_messages = self._execute_stream_tool_calls(
                tool_calls, agent, stream_id, request, policy
            )
            payload["messages"].extend(tool_messages)
            tool_calls = {}

        yield "data: [DONE]\n\n"

    def _accumulate_tool_calls(
        self, accumulator: Dict[str, Dict[str, Any]], chunk: ChatCompletionChunk
    ) -> None:
        delta_calls = chunk.choices[0].delta.tool_calls or []
        for call in delta_calls:
            entry = accumulator.setdefault(
                call.id,
                {
                    "id": call.id,
                    "type": call.type,
                    "function": {"name": call.function.name, "arguments": ""},
                },
            )
            entry["function"]["arguments"] += call.function.arguments or ""

    def _execute_stream_tool_calls(
        self,
        tool_calls: Dict[str, Dict[str, Any]],
        agent: AgentSpec,
        stream_id: str | None,
        request: ChatCompletionRequest,
        policy: ExecutionPolicy,
    ) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = []
        context = ToolInvocationContext(
            agent_name=agent.qualified_name,
            request_id=stream_id or f"stream-{agent.qualified_name}",
            policy=policy,
            user=request.user,
            source="declarative",
        )
        for call in tool_calls.values():
            function = call.get("function", {})
            arguments = self._parse_arguments(function.get("arguments"))
            tool_name = function.get("name")
            update_log_context(error_stage="tool_invocation", tool_name=tool_name)
            try:
                result = tool_manager.invoke_tool(tool_name, arguments, context)
            finally:
                update_log_context(tool_name=None)
            messages.append(
                {
                    "role": "tool",
                    "name": tool_name,
                    "tool_call_id": call.get("id"),
                    "content": result,
                }
            )
        return messages

    async def _run_tool_loop(
        self,
        agent: AgentSpec,
        payload: Dict[str, Any],
        request: ChatCompletionRequest,
        policy: ExecutionPolicy,
    ) -> ChatCompletionResponse:
        hops = 0
        response = await self._invoke_declarative_agent(agent, payload)
        while True:
            tool_calls = self._extract_tool_calls(response)
            if not tool_calls:
                return response
            if policy.max_tool_hops <= 0:
                return response
            if hops >= policy.max_tool_hops:
                raise AgentExecutionError(
                    f"Tool hop limit reached ({policy.max_tool_hops}) for {agent.qualified_name}"
                )
            hops += 1
            tool_messages = self._execute_tool_calls(
                tool_calls, agent, response, request, policy
            )
            payload["messages"].extend(tool_messages)
            response = await self._invoke_declarative_agent(agent, payload)

    async def _invoke_sdk_agent(
        self,
        agent: AgentSpec,
        payload: Dict[str, Any],
        request: ChatCompletionRequest,
        policy: ExecutionPolicy,
    ) -> ChatCompletionResponse:
        if not agent.module:
            raise AgentExecutionError(
                f"SDK agent {agent.qualified_name} is missing the 'module' attribute"
            )
        client = self._upstream_registry.get_client(agent.upstream)

        def run_sync() -> ChatCompletionResponse:
            return sdk_agent_adapter.run_agent(
                module_path=agent.module,
                agent=agent,
                client=client,
                request=request,
                messages=payload["messages"],
                policy=policy,
            )

        try:
            return await run_in_threadpool(run_sync)
        except SDKAgentError as exc:
            raise AgentExecutionError(str(exc)) from exc

    @staticmethod
    def _extract_tool_calls(
        response: ChatCompletionResponse,
    ) -> List[Dict[str, Any]]:
        choice = response.choices[0]
        tool_calls = choice.message.tool_calls or []
        serialized = [tool_call.model_dump() for tool_call in tool_calls]
        return serialized

    def _execute_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
        agent: AgentSpec,
        response: ChatCompletionResponse,
        request: ChatCompletionRequest,
        policy: ExecutionPolicy,
    ) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = []
        context = ToolInvocationContext(
            agent_name=agent.qualified_name,
            request_id=response.id,
            policy=policy,
            user=request.user,
            source="declarative",
        )
        for call in tool_calls:
            function = call["function"]
            arguments = self._parse_arguments(function.get("arguments"))
            tool_name = function.get("name")
            update_log_context(error_stage="tool_invocation", tool_name=tool_name)
            try:
                result = tool_manager.invoke_tool(tool_name, arguments, context)
            finally:
                update_log_context(tool_name=None)
            messages.append(
                {
                    "role": "tool",
                    "name": tool_name,
                    "tool_call_id": call.get("id"),
                    "content": result,
                }
            )
        return messages

    @staticmethod
    def _parse_arguments(raw: Optional[str]) -> Dict[str, Any]:
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            raise AgentExecutionError("Tool invocation arguments must be valid JSON")
        except Exception as exc:  # noqa: BLE001
            raise AgentExecutionError(str(exc)) from exc

    def _build_tool_definitions(self, agent: AgentSpec) -> List[Dict[str, Any]]:
        available = tool_manager.list_tools()
        definitions: List[Dict[str, Any]] = []
        for tool_name in agent.tools:
            spec = available.get(tool_name)
            if not spec:
                raise AgentExecutionError(
                    f"Unknown tool '{tool_name}' for agent {agent.qualified_name}"
                )
            parameters = spec.schema or {"type": "object", "properties": {}, "required": []}
            definition = {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.module or f"{spec.provider} tool",
                    "parameters": parameters,
                },
            }
            definitions.append(definition)
        return definitions


agent_executor = AgentExecutor()
