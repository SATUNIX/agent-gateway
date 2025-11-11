"""Context variables shared during SDK agent execution."""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from agents.policies import ExecutionPolicy
from api.models.chat import ChatCompletionRequest
from registry.models import AgentSpec


@dataclass(frozen=True)
class SDKRunContext:
    agent_spec: AgentSpec
    request: ChatCompletionRequest
    messages: List[Dict[str, Any]]
    policy: ExecutionPolicy
    client: Any
    request_id: Optional[str] = None


_context_var: ContextVar[Optional[SDKRunContext]] = ContextVar(
    "sdk_run_context", default=None
)


def push_run_context(
    *,
    agent_spec: AgentSpec,
    request: ChatCompletionRequest,
    messages: List[Dict[str, Any]],
    policy: ExecutionPolicy,
    client: Any,
    request_id: Optional[str] = None,
) -> Token:
    ctx = SDKRunContext(
        agent_spec=agent_spec,
        request=request,
        messages=messages,
        policy=policy,
        client=client,
        request_id=request_id,
    )
    return _context_var.set(ctx)


def get_run_context() -> Optional[SDKRunContext]:
    return _context_var.get()


def pop_run_context(token: Token) -> None:
    _context_var.reset(token)


__all__ = [
    "SDKRunContext",
    "push_run_context",
    "get_run_context",
    "pop_run_context",
]
