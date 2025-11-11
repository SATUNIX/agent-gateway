"""OpenAI-compatible models endpoint."""

from __future__ import annotations

import time
from typing import List

from fastapi import APIRouter, Depends

from api.auth import enforce_api_key
from api.models.model import ModelInfo, ModelListResponse
from registry import agent_registry
from registry.models import AgentSpec
from security import AuthContext


router = APIRouter(prefix="/v1", tags=["models"])


@router.get("/models", response_model=ModelListResponse)
async def list_models(auth: AuthContext = Depends(enforce_api_key)) -> ModelListResponse:
    visible: List[ModelInfo] = []
    for spec in agent_registry.list_agents():
        if not auth.is_agent_allowed(spec.qualified_name):
            continue
        visible.append(_serialize_spec(spec))
    return ModelListResponse(data=visible)


def _serialize_spec(spec: AgentSpec) -> ModelInfo:
    metadata = spec.metadata or {}
    created = int(metadata.get("discovered_at") or time.time())
    return ModelInfo(
        id=spec.qualified_name,
        created=created,
        owned_by=metadata.get("owned_by", "agent-gateway"),
        description=spec.description or spec.display_name,
        metadata={
            "namespace": spec.namespace,
            "display_name": spec.display_name,
            "kind": spec.kind,
            **metadata,
        },
    )


__all__ = ["router"]
