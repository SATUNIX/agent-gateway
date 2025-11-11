"""Reusable OpenAI Agents SDK samples extracted from docs/CodeReview.md."""

from __future__ import annotations

# NOTE: These snippets are stored as strings so tests can write them into
# temporary agent folders without importing the OpenAI Agents SDK at module
# import time. Each snippet is copied from the documentation examples.

HANDOFF_TRIAGE_AGENT = """\
from agents import Agent, Runner, function_tool


@function_tool
def history_lookup(topic: str) -> str:
    return f"History lookup for {topic}"


@function_tool
def math_solver(problem: str) -> str:
    return f"Solved math: {problem}"


history_tutor_agent = Agent(
    name="History Tutor",
    handoff_description="Specialist agent for historical questions",
    instructions="You provide assistance with historical queries.",
)


math_tutor_agent = Agent(
    name="Math Tutor",
    handoff_description="Specialist agent for math questions",
    instructions="You provide help with math problems. Explain your reasoning.",
)


triage_agent = Agent(
    name="Triage Agent",
    instructions="""
        You determine which agent to use based on the user's homework question.
        Hand off to the history tutor for history, math tutor for math.
    """.strip(),
    handoffs=[history_tutor_agent, math_tutor_agent],
)


async def main(prompt: str) -> str:
    result = await Runner.run(triage_agent, prompt)
    return result.final_output
"""


LIFECYCLE_HOOK_AGENT = """\
import asyncio
from typing import Any, Dict, List

from agents import Agent, AgentHooks, RunContextWrapper, Runner, Tool, function_tool


class LifecycleHooks(AgentHooks):
    def __init__(self, display_name: str) -> None:
        self.display_name = display_name
        self.events: List[str] = []

    async def on_start(self, context: RunContextWrapper, agent: Agent) -> None:
        self.events.append(f"{self.display_name}:start:{agent.name}")

    async def on_end(self, context: RunContextWrapper, agent: Agent, output: Any) -> None:
        self.events.append(f"{self.display_name}:end:{agent.name}:{output}")

    async def on_handoff(self, context: RunContextWrapper, agent: Agent, source: Agent) -> None:
        self.events.append(f"handoff:{source.name}->{agent.name}")

    async def on_tool_start(self, context: RunContextWrapper, agent: Agent, tool: Tool) -> None:
        self.events.append(f"tool_start:{agent.name}:{tool.name}")

    async def on_tool_end(self, context: RunContextWrapper, agent: Agent, tool: Tool, result: str) -> None:
        self.events.append(f"tool_end:{agent.name}:{tool.name}:{result}")


@function_tool
def random_number(max: int) -> int:
    import random

    return random.randint(0, max)


@function_tool
def multiply_by_two(x: int) -> int:
    return x * 2


multiply_agent = Agent(
    name="Multiply Agent",
    instructions="Multiply the number by 2 and return the result.",
    tools=[multiply_by_two],
    hooks=LifecycleHooks(display_name="Multiply"),
)


start_agent = Agent(
    name="Start Agent",
    instructions="""
        Generate a random number. If it's even, stop. If odd, hand off to Multiply Agent.
    """.strip(),
    tools=[random_number],
    handoffs=[multiply_agent],
    hooks=LifecycleHooks(display_name="Start"),
)


class ProperExampleRunner:
    def run_sync(
        self,
        *,
        messages: List[Dict[str, Any]],
        request: Any,
        policy: Any,
        client: Any,
    ) -> str:
        prompt = messages[-1]["content"] if messages else "Generate a number"

        async def _run() -> str:
            result = await Runner.run(start_agent, input=prompt)
            return str(result.final_output)

        return asyncio.run(_run())


runner = ProperExampleRunner()
"""


DYNAMIC_PROMPT_AGENT = """\
import asyncio
import random
from dataclasses import dataclass
from typing import Literal

from agents import Agent, RunContextWrapper, Runner


@dataclass
class CustomContext:
    style: Literal["haiku", "pirate", "robot"]


def custom_instructions(
    run_context: RunContextWrapper[CustomContext], agent: Agent[CustomContext]
) -> str:
    context = run_context.context
    if context.style == "haiku":
        return "Only respond in haikus."
    if context.style == "pirate":
        return "Respond as a pirate."
    return "Respond as a robot and say 'beep boop'."


agent = Agent(
    name="Chat agent",
    instructions=custom_instructions,
)


async def main(prompt: str) -> str:
    ctx = CustomContext(style=random.choice(["haiku", "pirate", "robot"]))
    result = await Runner.run(agent, prompt, context=ctx)
    return result.final_output
"""


GUARDRAIL_AGENT = """\
import asyncio
from pydantic import BaseModel

from agents import Agent, GuardrailFunctionOutput, InputGuardrail, Runner


class HomeworkOutput(BaseModel):
    is_homework: bool
    reasoning: str


guardrail_agent = Agent(
    name="Guardrail check",
    instructions="Check if the user is asking about homework.",
    output_type=HomeworkOutput,
)


async def homework_guardrail(ctx, agent, input_data):
    result = await Runner.run(guardrail_agent, input_data, context=ctx.context)
    final_output = result.final_output_as(HomeworkOutput)
    return GuardrailFunctionOutput(
        output_info=final_output,
        tripwire_triggered=not final_output.is_homework,
    )


math_tutor_agent = Agent(
    name="Math Tutor",
    handoff_description="Specialist agent for math questions",
    instructions="You provide help with math problems.",
)


triage_agent = Agent(
    name="Triage Agent",
    instructions="You determine which agent to use based on the user's homework question",
    handoffs=[math_tutor_agent],
    input_guardrails=[InputGuardrail(guardrail_function=homework_guardrail)],
)


async def main(prompt: str) -> str:
    result = await Runner.run(triage_agent, prompt)
    return result.final_output
"""


MANAGER_TOOLS_AGENT = """\
from agents import Agent


booking_agent = Agent(name="Booking", instructions="Handle booking questions.")
refund_agent = Agent(name="Refund", instructions="Handle refund questions.")


customer_facing_agent = Agent(
    name="Customer-facing agent",
    instructions="Handle all direct user communication.",
    tools=[
        booking_agent.as_tool(
            tool_name="booking_expert",
            tool_description="Handles booking questions and requests.",
        ),
        refund_agent.as_tool(
            tool_name="refund_expert",
            tool_description="Handles refund questions and requests.",
        ),
    ],
)
"""


BASIC_TOOL_AGENT = """\
from pydantic import BaseModel
from agents import Agent, function_tool


class WeatherReport(BaseModel):
    city: str
    outlook: str


@function_tool
def get_weather(city: str) -> WeatherReport:
    return WeatherReport(city=city, outlook="sunny")


agent = Agent(
    name="Weather Agent",
    instructions="Always respond with the weather report for the requested city.",
    tools=[get_weather],
    output_type=WeatherReport,
)
"""


DROPIN_FIXTURES = {
    "handoff_triad": HANDOFF_TRIAGE_AGENT,
    "lifecycle_hooks": LIFECYCLE_HOOK_AGENT,
    "dynamic_prompt": DYNAMIC_PROMPT_AGENT,
    "guardrail": GUARDRAIL_AGENT,
    "manager_tools": MANAGER_TOOLS_AGENT,
    "basic_tool": BASIC_TOOL_AGENT,
}


__all__ = [
    "HANDOFF_TRIAGE_AGENT",
    "LIFECYCLE_HOOK_AGENT",
    "DYNAMIC_PROMPT_AGENT",
    "GUARDRAIL_AGENT",
    "MANAGER_TOOLS_AGENT",
    "BASIC_TOOL_AGENT",
    "DROPIN_FIXTURES",
]
