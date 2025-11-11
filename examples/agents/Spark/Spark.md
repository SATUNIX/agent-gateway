# Spark Agent

Spark is a general lightweight agent in the MoA style (Agents as Tools). 

you will find agent.py in this repository for some more gateway focused design. You will also see below, sample python for a lightweight agent written more to OpenAI Agents SDK.
The goal for the gateway is to require absolute minimal code changes to an sdk spec agent definition to get your agents running in standard local chat interfaces. Eventually - zero code changes required.

---

<div align="center">
<img width="500" height="500" alt="image" src="https://github.com/user-attachments/assets/d8e3d453-0b85-4c9c-b573-ee9c4c8864e6" />
</div>

---

## Example Code - Lightweight Agents as Tools

```py
"""
agent.py

SparkMoA – Lightweight Mixture-of-Agents example for Agent Gateway.

Pattern:
- 1 coordinator agent (this file exports `agent`)
- 3 small specialists exposed as tools:
  - plan_task(...)  -> Planner agent
  - research_topic(...) -> Researcher agent (uses hosted WebSearchTool if present)
  - improve_answer(...) -> Writer agent

Coordinator runs a short ReAct-style loop:
"Think about the user goal -> pick tool -> observe -> answer concisely".

This follows the OpenAI Agents SDK patterns for:
- agents as tools
- orchestration via LLM
- function tools
Docs: https://openai.github.io/openai-agents-python/  (see multi-agent + tools)

"""

from __future__ import annotations

from typing import Any, Optional
from datetime import datetime

from agents import (
    Agent,
    Runner,
    RunContextWrapper,
    function_tool,
)

# ------------------------------------------------------------
# Optional hosted tool(s) – safe fallback if not installed
# ------------------------------------------------------------
OPTIONAL_TOOLS = []
try:  # pragma: no cover
    from agents import WebSearchTool  # type: ignore

    OPTIONAL_TOOLS.append(WebSearchTool(max_results=3))
except Exception:
    # ok to run without hosted web
    pass


# ------------------------------------------------------------
# 1) Specialist: Planner
# ------------------------------------------------------------
planner_agent = Agent(
    name="Spark Planner",
    instructions=(
        "You turn an open-ended goal into a small, executable plan. "
        "Return 3-6 numbered steps, each actionable and short. "
        "Prefer steps that the main agent or other tools can actually do. "
        "No chit-chat, just the plan."
    ),
)

@function_tool
async def plan_task(ctx: RunContextWrapper[Any], goal: str) -> str:
    """Plan a goal into 3-6 numbered, actionable steps."""
    result = await Runner.run(
        planner_agent,
        input=goal,
        parent_run=ctx.run,
    )
    return result.final_output or "1. Clarify goal\n2. Execute\n3. Summarize"


# ------------------------------------------------------------
# 2) Specialist: Researcher
#    - If web tool is present, call it
#    - Otherwise, just echo a structured "no web" response
# ------------------------------------------------------------
researcher_agent = Agent(
    name="Spark Researcher",
    instructions=(
        "You gather quick factual context for the user. "
        "If a web search tool is available, call it for the query. "
        "Return a tight bullet summary (3-5 bullets) + a 1-sentence takeaway."
    ),
    tools=[*OPTIONAL_TOOLS],
)

@function_tool
async def research_topic(ctx: RunContextWrapper[Any], query: str) -> str:
    """Research a topic using the Researcher sub-agent (web if available)."""
    # If we have a hosted web tool, we just let the researcher agent decide.
    result = await Runner.run(
        researcher_agent,
        input=query,
        parent_run=ctx.run,
    )
    return result.final_output or f"No live web available. Known topic: {query}"


# ------------------------------------------------------------
# 3) Specialist: Writer / Polisher
# ------------------------------------------------------------
writer_agent = Agent(
    name="Spark Writer",
    instructions=(
        "You improve and finalize an answer for the end user. "
        "Keep the user's intent, but make it clearer, shorter, and ordered. "
        "Prefer bullets or short paragraphs."
    ),
)

@function_tool
async def improve_answer(ctx: RunContextWrapper[Any], draft: str, user_intent: Optional[str] = None) -> str:
    """Polish a draft answer into a user-ready response."""
    prompt = draft if not user_intent else f"User intent: {user_intent}\n\nDraft:\n{draft}"
    result = await Runner.run(
        writer_agent,
        input=prompt,
        parent_run=ctx.run,
    )
    return result.final_output or draft


# ------------------------------------------------------------
# 4) Small utility tools
# ------------------------------------------------------------
@function_tool
def get_current_utc_time() -> str:
    """Return current UTC time (ISO 8601)."""
    return datetime.utcnow().isoformat() + "Z"


# ------------------------------------------------------------
# 5) Coordinator (the actual exported agent)
#    ReAct-y instructions:
#    - THINK: decide if we need plan/research
#    - ACT: call the right tool
#    - OBSERVE: integrate tool output
#    - ANSWER: produce final to user
# ------------------------------------------------------------
agent = Agent(
    name="SparkMoA",
    instructions=(
        "You are SparkMoA, a lightweight mixture-of-agents coordinator running inside Agent Gateway.\n"
        "Follow a short ReAct cycle:\n"
        "1) THINK: read the user's message and decide whether you need planning or research.\n"
        "2) ACT: call exactly one tool (plan_task, research_topic, improve_answer, get_current_utc_time) when it helps.\n"
        "3) OBSERVE: read the tool result.\n"
        "4) ANSWER: give the user a concise, helpful final answer.\n\n"
        "When the user asks for something broad or multi-step, call `plan_task` first.\n"
        "When the user asks for 'latest', 'compare', or 'what are the options', call `research_topic`.\n"
        "When you produced a rough draft and want it cleaner for the user, call `improve_answer`.\n"
        "Always return a final answer addressed to the user, even after tool calls.\n"
        "Keep answers lightweight — this is the 'Spark' tier, not a heavy research agent."
    ),
    tools=[
        plan_task,
        research_topic,
        improve_answer,
        get_current_utc_time,
        *OPTIONAL_TOOLS,  # lets the coordinator call web directly if the model decides
    ],
    # leave model unspecified – gateway/upstream decides (OpenAI, LM Studio, Ollama, vLLM…)
)

__all__ = ["agent"]


```
