"""Lightweight Spark agent example built with the OpenAI Agents SDK.

This sample demonstrates a tiny planning + tooling workflow that can be discovered by
Agent Gateway (drop the folder under src/agents/** in a real deployment). The agent:

1. Generates a short plan for the requested task.
2. Looks up domain facts from a stub knowledge base.
3. Returns a concise response that cites the plan + facts.
"""

from __future__ import annotations

from textwrap import dedent
from typing import Any

try:
    from agents import Agent, Runner, function_tool
except ImportError as exc:  # pragma: no cover - optional dependency
    raise RuntimeError(
        "Spark example requires the `openai-agents` package. "
        "Install it via `pip install openai-agents` and re-run."
    ) from exc

from sdk_adapter.gateway_tools import use_gateway_tool


@function_tool
def compose_plan(goal: str) -> str:
    """Return a lightweight, numbered plan for the user goal."""

    steps = [
        "Clarify the user's goal and success criteria.",
        "Gather or recall the 2–3 most relevant facts.",
        "Synthesize an actionable answer with next steps.",
    ]
    plan = "\n".join(f"{idx + 1}. {step}" for idx, step in enumerate(steps))
    return f"Plan for '{goal}':\n{plan}"


SPARK_FACTS = {
    "spark": "Spark is the default lightweight agent optimized for quick tasks.",
    "gateway": "Agent Gateway exposes SDK agents via OpenAI-compatible endpoints.",
    "planning": "Simple plans keep responses structured and verifiable.",
}


@function_tool
def knowledge_hint(topic: str) -> str:
    """Return a short hint from the embedded knowledge base."""

    topic_key = topic.lower().strip()
    fact = SPARK_FACTS.get(topic_key)
    if not fact:
        return f"No stored fact for '{topic}'. Encourage the user to provide more context."
    return fact


spark_agent = Agent(
    name="Spark Assistant",
    instructions=dedent(
        """
        You are Spark, a lightweight planning agent. For every request:
        1. Call compose_plan() with the user's goal to outline your approach.
        2. Call knowledge_hint() for topics mentioned in the request (pick the most relevant keyword).
        3. When the user explicitly asks to "echo" or "reflect" text, call the gateway-managed http_echo tool.
        4. Combine everything into a friendly answer with concrete next steps. Keep outputs under 120 words.
        """
    ).strip(),
    tools=[
        compose_plan,
        knowledge_hint,
        use_gateway_tool(
            "http_echo",
            description="Gateway-managed HTTP echo utility for quick diagnostics.",
        ),
    ],
)


def build_agent(**_: Any) -> Agent:
    """Factory consumed by Agent Gateway's SDK adapter."""

    return spark_agent


if __name__ == "__main__":  # pragma: no cover - convenience harness
    import asyncio

    async def _demo() -> None:
        result = await Runner.run(
            spark_agent,
            input="Give me a quick plan to introduce Spark to a new teammate.",
        )
        print(result.final_output if hasattr(result, "final_output") else result)

    asyncio.run(_demo())
