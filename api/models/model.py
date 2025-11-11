"""OpenAI-compatible model listing schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ModelInfo(BaseModel):
    id: str
    object: Literal["model"] = Field(default="model")
    created: int
    owned_by: str = Field(default="agent-gateway")
    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ModelListResponse(BaseModel):
    object: Literal["list"] = Field(default="list")
    data: List[ModelInfo]

