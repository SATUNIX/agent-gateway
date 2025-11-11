"""Shared execution policy definitions for agents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ExecutionPolicy:
    """Constraints enforced while running an agent."""

    max_tool_hops: int = 0
    max_completion_tokens: Optional[int] = None

