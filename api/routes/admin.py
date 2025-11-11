"""Management endpoints for agents, upstreams, and metrics."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends

from api.auth import enforce_api_key
from api.metrics import metrics
from api.models.admin import AgentInfo, MetricsResponse, SecurityKeyInfo, ToolInfo, UpstreamInfo
from registry import agent_registry, upstream_registry
from tooling import tool_manager
from security import security_manager


router = APIRouter(tags=["admin"], dependencies=[Depends(enforce_api_key)])


@router.get("/agents", response_model=List[AgentInfo], summary="List available agents")
async def list_agents() -> List[AgentInfo]:
    agents = []
    for agent in agent_registry.list_agents():
        agents.append(
            AgentInfo(
                name=agent.name,
                namespace=agent.namespace,
                qualified_name=agent.qualified_name,
                display_name=agent.display_name,
                kind=agent.kind,
                model=agent.model,
                upstream=agent.upstream,
                description=agent.description,
                tools=agent.tools,
                metadata=agent.metadata,
            )
        )
    return agents


@router.get(
    "/upstreams",
    response_model=List[UpstreamInfo],
    summary="List configured upstream providers",
)
async def list_upstreams() -> List[UpstreamInfo]:
    upstreams: List[UpstreamInfo] = []
    for record in upstream_registry.list_upstreams():
        upstreams.append(
            UpstreamInfo(
                name=record.spec.name,
                provider=record.spec.provider,
                base_url=str(record.spec.base_url),
                priority=record.spec.priority,
                healthy=record.healthy,
                health_path=record.spec.health_path,
                health_timeout=record.spec.health_timeout,
                last_checked=int(record.last_checked) if record.last_checked else None,
                last_error=record.last_error,
            )
        )
    return upstreams


@router.get("/metrics", response_model=MetricsResponse, summary="Gateway metrics snapshot")
async def metrics_snapshot() -> MetricsResponse:
    return MetricsResponse(**metrics.snapshot())


@router.get(
    "/tools",
    response_model=List[ToolInfo],
    summary="List registered tools",
)
async def list_tools() -> List[ToolInfo]:
    infos: List[ToolInfo] = []
    for tool in tool_manager.list_tools().values():
        infos.append(
            ToolInfo(
                name=tool.name,
                provider=tool.provider,
                module=tool.module,
                url=str(tool.url) if tool.url else None,
                method=tool.method,
            )
        )
    return infos


@router.post(
    "/agents/refresh",
    response_model=List[AgentInfo],
    summary="Force agent registry reload",
)
async def refresh_agents() -> List[AgentInfo]:
    agent_registry.refresh()
    return await list_agents()


@router.post(
    "/upstreams/refresh",
    response_model=List[UpstreamInfo],
    summary="Force upstream registry reload",
)
async def refresh_upstreams() -> List[UpstreamInfo]:
    upstream_registry.refresh()
    return await list_upstreams()


@router.post(
    "/tools/refresh",
    response_model=List[ToolInfo],
    summary="Force tool registry reload",
)
async def refresh_tools() -> List[ToolInfo]:
    tool_manager.refresh()
    return await list_tools()


@router.post(
    "/security/refresh",
    response_model=List[SecurityKeyInfo],
    summary="Reload security config and list API keys",
)
async def refresh_security() -> List[SecurityKeyInfo]:
    security_manager.reload()
    return [
        SecurityKeyInfo(
            key_id=entry["key_id"],
            allow_agents=entry["allow_agents"],
            rate_limit_per_minute=entry["rate_limit_per_minute"],
            expires_at=entry["expires_at"],
        )
        for entry in security_manager.summary()
    ]
