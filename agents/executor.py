"""Agent executor responsible for running declarative and SDK agents."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from time import perf_counter

from starlette.concurrency import run_in_threadpool

from agents.policies import ExecutionPolicy
from api.metrics import metrics, record_upstream_call
from api.models.chat import ChatCompletionRequest, ChatCompletionResponse
from registry import agent_registry, upstream_registry
from registry.models import AgentSpec
from tooling import ToolInvocationContext, tool_manager
from sdk_adapter import SDKAgentAdapter, SDKAgentError
from security import AuthContext


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
        policy = self._build_policy(agent, request)
        payload = self._build_payload(agent, request, policy)
        if agent.kind == "sdk":
            return await self._invoke_sdk_agent(agent, payload, request, policy)
        return await self._run_tool_loop(agent, payload, request, policy)

    def _resolve_agent(self, identifier: str) -> AgentSpec:
        agent = self._agent_registry.get_agent(identifier)
        if not agent:
            raise AgentNotFoundError(
                f"Unknown agent or model '{identifier}'. Register it in config/agents.yaml."
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
        if policy.max_completion_tokens is not None:
            payload["max_tokens"] = policy.max_completion_tokens
        elif request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.stream:
            payload["stream"] = False

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
        )
        for call in tool_calls:
            function = call["function"]
            arguments = self._parse_arguments(function.get("arguments"))
            tool_name = function.get("name")
            result = tool_manager.invoke_tool(tool_name, arguments, context)
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


agent_executor = AgentExecutor()
