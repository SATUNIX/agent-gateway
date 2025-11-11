"""Management endpoints for agents, upstreams, and metrics."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends

from api.auth import enforce_api_key
from api.metrics import metrics
from api.models.admin import (
    AgentInfo,
    MetricsResponse,
    SecurityKeyInfo,
    SecurityOverrideRequest,
    SecurityOverrideResponse,
    SecurityPreviewRequest,
    SecurityPreviewResponse,
    ToolInfo,
    UpstreamInfo,
    RecentError,
)
from registry import agent_registry, upstream_registry
from tooling import tool_manager
from security import security_manager
from observability.errors import error_recorder


router = APIRouter(tags=["admin"], dependencies=[Depends(enforce_api_key)])


@router.get("/agents", response_model=List[AgentInfo], summary="List available agents")
async def list_agents() -> List[AgentInfo]:
    agents: List[AgentInfo] = []
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
                status=agent.metadata.get("discovery_status", "available"),
                error=agent.metadata.get("discovery_error"),
            )
        )
    for diag in agent_registry.list_discovery_diagnostics():
        diag_name = diag.file_path.stem or "unknown"
        agents.append(
            AgentInfo(
                name=f"diagnostic::{diag_name}",
                namespace="diagnostics",
                qualified_name=f"diagnostics/{diag_name}",
                display_name=f"Diagnostic {diag_name}",
                kind="diagnostic",
                model="-",
                upstream="-",
                description=diag.message,
                tools=[],
                metadata={
                    "file_path": str(diag.file_path),
                    "module": diag.module,
                    "severity": diag.severity,
                    "kind": diag.kind,
                    "occurred_at": int(diag.occurred_at),
                },
                status="error" if diag.severity == "error" else diag.severity,
                error=diag.message,
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


@router.post(
    "/security/preview",
    response_model=SecurityPreviewResponse,
    summary="Preview whether an agent would be allowed",
)
async def security_preview(request: SecurityPreviewRequest) -> SecurityPreviewResponse:
    result = security_manager.preview_agent(request.agent)
    return SecurityPreviewResponse(**result)


@router.post(
    "/security/override",
    response_model=SecurityOverrideResponse,
    summary="Create a temporary agent allowlist override",
)
async def security_override(request: SecurityOverrideRequest) -> SecurityOverrideResponse:
    override = security_manager.add_agent_override(
        pattern=request.agent,
        ttl_seconds=request.ttl_seconds,
        reason=request.reason,
    )
    return SecurityOverrideResponse(agent=request.agent, **override)


@router.get(
    "/agents/errors",
    response_model=List[RecentError],
    summary="List recent discovery/runtime errors",
)
async def list_agent_errors() -> List[RecentError]:
    return [RecentError(**entry) for entry in error_recorder.list()]
