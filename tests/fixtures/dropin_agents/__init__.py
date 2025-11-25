"""Simple drop-in agent fixtures used by the acceptance suite."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

BASIC_ECHO_AGENT = """\
from typing import List, Dict, Any


class EchoAgent:
    def run_sync(self, *, messages: List[Dict[str, Any]], **_: Any) -> str:
        last = messages[-1]["content"] if messages else "hello"
        return f"ECHO:{last}"


agent = EchoAgent()
"""


GATEWAY_TOOL_AGENT = """\
from typing import List, Dict, Any

from sdk_adapter.gateway_tools import use_gateway_tool

summarize = use_gateway_tool("summarize_text")


class ToolAgent:
    def run_sync(self, *, messages: List[Dict[str, Any]], **_: Any) -> str:
        text = messages[-1]["content"] if messages else "empty"
        return summarize(text=text, max_words=5)


agent = ToolAgent()
"""


DROPIN_FIXTURES: Dict[str, str] = {
    "basic_echo": BASIC_ECHO_AGENT,
    "gateway_tool": GATEWAY_TOOL_AGENT,
    "agent_builder": """\
from agents import Agent, function_tool


@function_tool
def greet(name: str) -> str:
    return f"Hello, {name}!"


agent = Agent(
    name=\"BuilderAgent\",
    instructions=\"Greet the user politely.\",
    tools=[greet],
)
""",
}


def materialize_fixture(root: Path, fixture_name: str, agent_name: str) -> Path:
    """Write the given fixture under <root>/<agent_name>/agent.py."""

    if fixture_name not in DROPIN_FIXTURES:
        raise KeyError(f"Unknown fixture '{fixture_name}'")
    agent_dir = root / agent_name
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "__init__.py").write_text("", encoding="utf-8")
    (agent_dir / "agent.py").write_text(DROPIN_FIXTURES[fixture_name], encoding="utf-8")
    return agent_dir


__all__ = ["DROPIN_FIXTURES", "materialize_fixture"]
