"""Bridge sample OpenAI Agents SDK workflows into Agent Gateway."""

from __future__ import annotations

import asyncio
import random
from typing import Any, Dict, List

try:
    from agents import Agent, AgentHooks, RunContextWrapper, Runner, Tool, function_tool
except ImportError as exc:  # pragma: no cover - optional dependency
    raise RuntimeError(
        "The openai-agents package is required to use agents.proper_example. "
        "Install it via `pip install openai-agents` and ensure OPENAI_BASE_URL points to Agent Gateway."
    ) from exc


class LifecycleHooks(AgentHooks):
    """Replicates the SDK example hooks for logging."""

    def __init__(self, display_name: str) -> None:
        self.event_counter = 0
        self.display_name = display_name

    async def on_start(self, context: RunContextWrapper, agent: Agent) -> None:  # noqa: D401
        self.event_counter += 1
        print(f"### ({self.display_name}) {self.event_counter}: Agent {agent.name} started")

    async def on_end(self, context: RunContextWrapper, agent: Agent, output: Any) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}: Agent {agent.name} ended with output {output}"
        )

    async def on_handoff(self, context: RunContextWrapper, agent: Agent, source: Agent) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}: Agent {source.name} handed off to {agent.name}"
        )

    async def on_tool_start(self, context: RunContextWrapper, agent: Agent, tool: Tool) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}: Agent {agent.name} started tool {tool.name}"
        )

    async def on_tool_end(
        self, context: RunContextWrapper, agent: Agent, tool: Tool, result: str
    ) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}: Agent {agent.name} ended tool {tool.name} with result {result}"
        )


@function_tool
def random_number(max: int) -> int:
    """Generate a random number between 0 and max (inclusive)."""

    return random.randint(0, max)


@function_tool
def multiply_by_two(x: int) -> int:
    """Simple multiplication helper."""

    return x * 2


multiply_agent = Agent(
    name="Multiply Agent",
    instructions="Multiply the number by 2 and then return the final result.",
    tools=[multiply_by_two],
    hooks=LifecycleHooks(display_name="Multiply Agent"),
)

start_agent = Agent(
    name="Start Agent",
    instructions="Generate a random number. If it's even, stop. If it's odd, hand off to the multiply agent.",
    tools=[random_number],
    handoffs=[multiply_agent],
    hooks=LifecycleHooks(display_name="Start Agent"),
)


class ProperExampleRunner:
    """Adapter that executes the SDK lifecycle example inside the gateway."""

    def run_sync(
        self,
        *,
        messages: List[Dict[str, Any]],
        request: Any,
        policy: Any,
        client: Any,
    ) -> str:
        prompt = messages[-1]["content"] if messages else ""

        async def _run() -> str:
            result = await Runner.run(
                start_agent,
                input=prompt or "Generate a random number between 0 and 100.",
            )
            output = getattr(result, "final_output", result)
            return str(output)

        return asyncio.run(_run())


def build_agent(**_: Any) -> ProperExampleRunner:
    """Entry point consumed by SDKAgentAdapter."""

    return ProperExampleRunner()


if __name__ == "__main__":
    asyncio.run(Runner.run(start_agent, input="Generate a random number between 0 and 10."))
