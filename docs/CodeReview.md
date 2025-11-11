# Agent Gateway Code Review Report

## Integration Status (Observed)

**Status:** ❌ Does not support; gateway expects a custom format.

Agent loading is entirely driven by `config/agents.yaml`, which requires synthetic fields such as `kind`, `namespace`, and a `module` string for SDK entries. The executor never inspects OpenAI Agents SDK objects directly (`registry/models.py` lines 13–43, `agents/executor.py` lines 54–59). The SDK adapter imports a callable and demands it return a runner exposing `run_sync/run`, rather than accepting the native `Agent/Runner` constructs from the OpenAI Agents SDK (`sdk_adapter/adapter.py` lines 31–96). The bundled **ProperExampleRunner** wrapper bridges `Runner.run` into that interface, proving that drop-in SDK files require editing (`agents/proper_example.py` lines 86–114).

---

## Code Paths Inspected

| File                                                                          | Lines                   | Purpose                                                                                     |
| ----------------------------------------------------------------------------- | ----------------------- | ------------------------------------------------------------------------------------------- |
| `api/main.py`                                                                 | 22–35                   | Wires FastAPI app, middleware, and chat/admin routers.                                      |
| `api/routes/chat.py`                                                          | 14–31                   | Exposes POST `/v1/chat/completions` and routes to chat service.                             |
| `api/services/chat.py`                                                        | 26–89                   | Handles streaming vs. non-streaming requests, delegates to `agent_executor`.                |
| `agents/executor.py`                                                          | 33–236                  | Resolves agent IDs, runs declarative tools or SDK adapter when `kind=="sdk"`.               |
| `registry/agents.py` & `config/agents.yaml`                                   | 15–83 / 1–29            | Maintains static YAML-defined catalog of agents; no dynamic discovery.                      |
| `sdk_adapter/adapter.py`, `agents/sdk_example.py`, `agents/proper_example.py` | 31–145 / 29–46 / 86–114 | Show adapter’s callable import expectations and runner shim for SDK agents.                 |
| `tooling/manager.py`                                                          | 24–205                  | Loads tools from `config/tools.yaml` and applies provider invocation logic outside the SDK. |

---

## Discovery / Auto-pickup Findings

* `AgentRegistry` reads a single YAML path from settings; it sorts and caches entries but never scans Python modules (`registry/agents.py` 31–83).
* Every SDK agent entry must declare `module: some.module:callable`; the `AgentSpec` validator enforces this field for `kind=="sdk"` (`registry/models.py` 13–43, `config/agents.yaml` 19–29).
* The executor error explicitly states “Register it in config/agents.yaml,” confirming no auto-discovery (`agents/executor.py` 54–59).

**Result:** No drop-in support; manual YAML edits required.

---

## SDK vs Gateway Structure Comparison

| Component            | SDK Expectation                                         | Gateway Behavior                                                                                  | Verdict    |
| -------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------------------------------- | ---------- |
| **Agent Definition** | Developers instantiate `Agent(...)` directly in Python. | Gateway reads metadata from YAML plus a factory callable string; does not import `Agent` objects. | ❌ Mismatch |
| **Tools**            | Declared with `@function_tool` inside agent module.     | Ignores SDK tool decorators, instead uses `config/tools.yaml`; no dynamic attachment.             | ❌ Mismatch |
| **Handoffs/Hooks**   | Supported through `AgentHooks` and handoffs.            | Never referenced; only works if manually wrapped (e.g., ProperExampleRunner).                     | ❌ Mismatch |
| **Execution Entry**  | `Runner.run(agent, input=...)`                          | Requires callable returning `run_sync/run`; uses asyncio to execute.                              | ❌ Mismatch |

---

## Routing Findings

* Chat UI posts to `/v1/chat/completions` (API-key protected).
* Requests are processed via `ChatCompletionService` → `agent_executor.create_completion` (`api/services/chat.py` 26–89).
* `agent_executor` resolves models strictly from YAML registry; dropped SDK files are ignored (`agents/executor.py` 40–59).
* For SDK agents, the executor imports the callable specified in YAML and invokes it with message list + upstream client (`agents/executor.py` 157–184).
* No `/v1/models` endpoint for listing; available agents are exposed only to admins via `/agents` (`api/routes/admin.py` 24–54).

---

## Deviation Notes

1. **Static YAML Schema Required:** Every agent must define `namespace`, `kind`, `module`. This diverges from SDK’s principle of in-module agent metadata (`registry/models.py` 13–43).
2. **Gateway-specific Factory Layer:** The SDK adapter mandates `module:callable` returning custom runner signatures instead of directly consuming SDK agents (`sdk_adapter/adapter.py` 31–96).
3. **Tool Schema Disconnect:** Gateway never forwards SDK tool declarations; relies on external YAML for tool registration (`agents/executor.py` 82–108).
4. **Ignored SDK Hooks/Handoffs:** These constructs aren’t referenced by gateway code; only manual wrappers can trigger them (`agents/proper_example.py` 86–114).
5. **Tool Invocation Bypass:** Tool execution enforced via `tool_manager.invoke_tool`, ignoring SDK `@function_tool` definitions (`tooling/manager.py` 24–205).

---

## Summary: What the Code Actually Does

### Static Agent Registry via YAML

The gateway uses a Pydantic-based registry that loads agent definitions from `config/agents.yaml`. Each agent must include `name`, `kind`, and for SDK agents, a `module` string (`module_path:callable`). Agents not listed here trigger `AgentNotFoundError`.

### SDK Adapter Dependency on YAML

The `SDKAgentAdapter` dynamically imports the callable defined in `agent.module`, enabling OpenAI Agents SDK-style usage but only if declared in YAML. No scanning for SDK agents occurs.

### Auto-Reload Behavior

`agent_auto_reload` in `config/settings.py` refreshes the YAML file on change, not new file detection. Agents must still be listed manually.

### Serving to Chat UI

The chat API resolves models from the YAML registry. If the model isn’t defined, it fails. There’s no endpoint dynamically exposing Python agent files as models.

---

## Comparison with OpenAI Agents SDK Design

The OpenAI Agents SDK defines lightweight primitives—**agents**, **handoffs**, **guardrails**, and **sessions**—for modular orchestration. SDK agents can be written in plain Python with tools and run using `Runner.run()` without configuration indirection. Tutorials (OpenAI docs, DataCamp) emphasize treating the agent file as the source of truth.

The gateway diverges from this model, introducing a YAML registry that acts as a custom framework layer instead of using SDK-native discovery and execution.

---

## Conclusion

The gateway implementation is **not compliant** with the intended drop-in architecture. It does not dynamically discover or serve OpenAI Agents SDK agent files. To add an agent, a developer must:

1. Place the agent module on the Python path.
2. Edit `config/agents.yaml` to add an SDK entry with a `module:callable` path.
3. Optionally enable `agent_auto_reload` for YAML refresh.

This design defeats the purpose of “drop-in” SDK agent deployment. Achieving true plug-and-play support would require eliminating YAML indirection, scanning for SDK `Agent` definitions, or allowing dynamic registration through the chat UI.

---

**Final Verdict:**

> The current gateway architecture uses a configuration-driven registry rather than leveraging the OpenAI Agents SDK directly. It does not support drop-in agent discovery or automatic serving to the chat UI without manual edits.


---
Example agents: 
These are code examples of agents which will be dropped in, the aim is to have these agents be dropped into the agent folder such as ./agents/ResearchAgent/agent.py and have that agent be served so you can chat with it, with no to absolute minimal code changes to the agent file to link it with the gateway. 

```py
import asyncio

from agents import Agent, Runner


async def main():
    agent = Agent(
        name="Assistant",
        instructions="You only respond in haikus.",
    )

    result = await Runner.run(agent, "Tell me about recursion in programming.")
    print(result.final_output)
    # Function calls itself,
    # Looping in smaller pieces,
    # Endless by design.


if __name__ == "__main__":
    asyncio.run(main())

```

```py
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
    elif context.style == "pirate":
        return "Respond as a pirate."
    else:
        return "Respond as a robot and say 'beep boop' a lot."


agent = Agent(
    name="Chat agent",
    instructions=custom_instructions,
)


async def main():
    context = CustomContext(style=random.choice(["haiku", "pirate", "robot"]))
    print(f"Using style: {context.style}\n")

    user_message = "Tell me a joke."
    print(f"User: {user_message}")
    result = await Runner.run(agent, user_message, context=context)

    print(f"Assistant: {result.final_output}")


if __name__ == "__main__":
    asyncio.run(main())


"""
$ python examples/basic/dynamic_system_prompt.py

Using style: haiku

User: Tell me a joke.
Assistant: Why don't eggs tell jokes?
They might crack each other's shells,
leaving yolk on face.

$ python examples/basic/dynamic_system_prompt.py
Using style: robot

User: Tell me a joke.
Assistant: Beep boop! Why was the robot so bad at soccer? Beep boop... because it kept kicking up a debug! Beep boop!

$ python examples/basic/dynamic_system_prompt.py
Using style: pirate

User: Tell me a joke.
Assistant: Why did the pirate go to school?

To improve his arrr-ticulation! Har har har! 🏴‍☠️
"""
```

```md
This section is some documentaiton about the open ai agents sdk for context. This is what the agents are written against, the goal is to serve the user message to these and send the response back via the gateway.

Agents
Agents are the core building block in your apps. An agent is a large language model (LLM), configured with instructions and tools.

Basic configuration
The most common properties of an agent you'll configure are:

name: A required string that identifies your agent.
instructions: also known as a developer message or system prompt.
model: which LLM to use, and optional model_settings to configure model tuning parameters like temperature, top_p, etc.
tools: Tools that the agent can use to achieve its tasks.

from agents import Agent, ModelSettings, function_tool

@function_tool
def get_weather(city: str) -> str:
    """returns weather info for the specified city."""
    return f"The weather in {city} is sunny"

agent = Agent(
    name="Haiku agent",
    instructions="Always respond in haiku form",
    model="gpt-5-nano",
    tools=[get_weather],
)
Context
Agents are generic on their context type. Context is a dependency-injection tool: it's an object you create and pass to Runner.run(), that is passed to every agent, tool, handoff etc, and it serves as a grab bag of dependencies and state for the agent run. You can provide any Python object as the context.


@dataclass
class UserContext:
    name: str
    uid: str
    is_pro_user: bool

    async def fetch_purchases() -> list[Purchase]:
        return ...

agent = Agent[UserContext](
    ...,
)
Output types
By default, agents produce plain text (i.e. str) outputs. If you want the agent to produce a particular type of output, you can use the output_type parameter. A common choice is to use Pydantic objects, but we support any type that can be wrapped in a Pydantic TypeAdapter - dataclasses, lists, TypedDict, etc.


from pydantic import BaseModel
from agents import Agent


class CalendarEvent(BaseModel):
    name: str
    date: str
    participants: list[str]

agent = Agent(
    name="Calendar extractor",
    instructions="Extract calendar events from text",
    output_type=CalendarEvent,
)
Note

When you pass an output_type, that tells the model to use structured outputs instead of regular plain text responses.

Multi-agent system design patterns
There are many ways to design multi‑agent systems, but we commonly see two broadly applicable patterns:

Manager (agents as tools): A central manager/orchestrator invokes specialized sub‑agents as tools and retains control of the conversation.
Handoffs: Peer agents hand off control to a specialized agent that takes over the conversation. This is decentralized.
See our practical guide to building agents for more details.

Manager (agents as tools)
The customer_facing_agent handles all user interaction and invokes specialized sub‑agents exposed as tools. Read more in the tools documentation.


from agents import Agent

booking_agent = Agent(...)
refund_agent = Agent(...)

customer_facing_agent = Agent(
    name="Customer-facing agent",
    instructions=(
        "Handle all direct user communication. "
        "Call the relevant tools when specialized expertise is needed."
    ),
    tools=[
        booking_agent.as_tool(
            tool_name="booking_expert",
            tool_description="Handles booking questions and requests.",
        ),
        refund_agent.as_tool(
            tool_name="refund_expert",
            tool_description="Handles refund questions and requests.",
        )
    ],
)
Handoffs
Handoffs are sub‑agents the agent can delegate to. When a handoff occurs, the delegated agent receives the conversation history and takes over the conversation. This pattern enables modular, specialized agents that excel at a single task. Read more in the handoffs documentation.


from agents import Agent

booking_agent = Agent(...)
refund_agent = Agent(...)

triage_agent = Agent(
    name="Triage agent",
    instructions=(
        "Help the user with their questions. "
        "If they ask about booking, hand off to the booking agent. "
        "If they ask about refunds, hand off to the refund agent."
    ),
    handoffs=[booking_agent, refund_agent],
)
Dynamic instructions
In most cases, you can provide instructions when you create the agent. However, you can also provide dynamic instructions via a function. The function will receive the agent and context, and must return the prompt. Both regular and async functions are accepted.


def dynamic_instructions(
    context: RunContextWrapper[UserContext], agent: Agent[UserContext]
) -> str:
    return f"The user's name is {context.context.name}. Help them with their questions."


agent = Agent[UserContext](
    name="Triage agent",
    instructions=dynamic_instructions,
)
Lifecycle events (hooks)
Sometimes, you want to observe the lifecycle of an agent. For example, you may want to log events, or pre-fetch data when certain events occur. You can hook into the agent lifecycle with the hooks property. Subclass the AgentHooks class, and override the methods you're interested in.

Guardrails
Guardrails allow you to run checks/validations on user input in parallel to the agent running, and on the agent's output once it is produced. For example, you could screen the user's input and agent's output for relevance. Read more in the guardrails documentation.

Cloning/copying agents
By using the clone() method on an agent, you can duplicate an Agent, and optionally change any properties you like.


pirate_agent = Agent(
    name="Pirate",
    instructions="Write like a pirate",
    model="gpt-4.1",
)

robot_agent = pirate_agent.clone(
    name="Robot",
    instructions="Write like a robot",
)
Forcing tool use
Supplying a list of tools doesn't always mean the LLM will use a tool. You can force tool use by setting ModelSettings.tool_choice. Valid values are:

auto, which allows the LLM to decide whether or not to use a tool.
required, which requires the LLM to use a tool (but it can intelligently decide which tool).
none, which requires the LLM to not use a tool.
Setting a specific string e.g. my_tool, which requires the LLM to use that specific tool.

from agents import Agent, Runner, function_tool, ModelSettings

@function_tool
def get_weather(city: str) -> str:
    """Returns weather info for the specified city."""
    return f"The weather in {city} is sunny"

agent = Agent(
    name="Weather Agent",
    instructions="Retrieve weather details.",
    tools=[get_weather],
    model_settings=ModelSettings(tool_choice="get_weather")
)
Tool Use Behavior
The tool_use_behavior parameter in the Agent configuration controls how tool outputs are handled:

"run_llm_again": The default. Tools are run, and the LLM processes the results to produce a final response.
"stop_on_first_tool": The output of the first tool call is used as the final response, without further LLM processing.

from agents import Agent, Runner, function_tool, ModelSettings

@function_tool
def get_weather(city: str) -> str:
    """Returns weather info for the specified city."""
    return f"The weather in {city} is sunny"

agent = Agent(
    name="Weather Agent",
    instructions="Retrieve weather details.",
    tools=[get_weather],
    tool_use_behavior="stop_on_first_tool"
)
StopAtTools(stop_at_tool_names=[...]): Stops if any specified tool is called, using its output as the final response.

from agents import Agent, Runner, function_tool
from agents.agent import StopAtTools

@function_tool
def get_weather(city: str) -> str:
    """Returns weather info for the specified city."""
    return f"The weather in {city} is sunny"

@function_tool
def sum_numbers(a: int, b: int) -> int:
    """Adds two numbers."""
    return a + b

agent = Agent(
    name="Stop At Stock Agent",
    instructions="Get weather or sum numbers.",
    tools=[get_weather, sum_numbers],
    tool_use_behavior=StopAtTools(stop_at_tool_names=["get_weather"])
)
ToolsToFinalOutputFunction: A custom function that processes tool results and decides whether to stop or continue with the LLM.

from agents import Agent, Runner, function_tool, FunctionToolResult, RunContextWrapper
from agents.agent import ToolsToFinalOutputResult
from typing import List, Any

@function_tool
def get_weather(city: str) -> str:
    """Returns weather info for the specified city."""
    return f"The weather in {city} is sunny"

def custom_tool_handler(
    context: RunContextWrapper[Any],
    tool_results: List[FunctionToolResult]
) -> ToolsToFinalOutputResult:
    """Processes tool results to decide final output."""
    for result in tool_results:
        if result.output and "sunny" in result.output:
            return ToolsToFinalOutputResult(
                is_final_output=True,
                final_output=f"Final weather: {result.output}"
            )
    return ToolsToFinalOutputResult(
        is_final_output=False,
        final_output=None
    )

agent = Agent(
    name="Weather Agent",
    instructions="Retrieve weather details.",
    tools=[get_weather],
    tool_use_behavior=custom_tool_handler
)
Note

To prevent infinite loops, the framework automatically resets tool_choice to "auto" after a tool call. This behavior is configurable via agent.reset_tool_choice. The infinite loop is because tool results are sent to the LLM, which then generates another tool call because of tool_choice, ad infinitum.

Create your first agent
Agents are defined with instructions, a name, and optional config (such as model_config)


from agents import Agent

agent = Agent(
    name="Math Tutor",
    instructions="You provide help with math problems. Explain your reasoning at each step and include examples",
)
Add a few more agents
Additional agents can be defined in the same way. handoff_descriptions provide additional context for determining handoff routing


from agents import Agent

history_tutor_agent = Agent(
    name="History Tutor",
    handoff_description="Specialist agent for historical questions",
    instructions="You provide assistance with historical queries. Explain important events and context clearly.",
)

math_tutor_agent = Agent(
    name="Math Tutor",
    handoff_description="Specialist agent for math questions",
    instructions="You provide help with math problems. Explain your reasoning at each step and include examples",
)
Define your handoffs
On each agent, you can define an inventory of outgoing handoff options that the agent can choose from to decide how to make progress on their task.


triage_agent = Agent(
    name="Triage Agent",
    instructions="You determine which agent to use based on the user's homework question",
    handoffs=[history_tutor_agent, math_tutor_agent]
)
Run the agent orchestration
Let's check that the workflow runs and the triage agent correctly routes between the two specialist agents.


from agents import Runner

async def main():
    result = await Runner.run(triage_agent, "What is the capital of France?")
    print(result.final_output)
Add a guardrail
You can define custom guardrails to run on the input or output.


from agents import GuardrailFunctionOutput, Agent, Runner
from pydantic import BaseModel


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
Put it all together
Let's put it all together and run the entire workflow, using handoffs and the input guardrail.


from agents import Agent, InputGuardrail, GuardrailFunctionOutput, Runner
from agents.exceptions import InputGuardrailTripwireTriggered
from pydantic import BaseModel
import asyncio

class HomeworkOutput(BaseModel):
    is_homework: bool
    reasoning: str

guardrail_agent = Agent(
    name="Guardrail check",
    instructions="Check if the user is asking about homework.",
    output_type=HomeworkOutput,
)

math_tutor_agent = Agent(
    name="Math Tutor",
    handoff_description="Specialist agent for math questions",
    instructions="You provide help with math problems. Explain your reasoning at each step and include examples",
)

history_tutor_agent = Agent(
    name="History Tutor",
    handoff_description="Specialist agent for historical questions",
    instructions="You provide assistance with historical queries. Explain important events and context clearly.",
)


async def homework_guardrail(ctx, agent, input_data):
    result = await Runner.run(guardrail_agent, input_data, context=ctx.context)
    final_output = result.final_output_as(HomeworkOutput)
    return GuardrailFunctionOutput(
        output_info=final_output,
        tripwire_triggered=not final_output.is_homework,
    )

triage_agent = Agent(
    name="Triage Agent",
    instructions="You determine which agent to use based on the user's homework question",
    handoffs=[history_tutor_agent, math_tutor_agent],
    input_guardrails=[
        InputGuardrail(guardrail_function=homework_guardrail),
    ],
)

async def main():
    # Example 1: History question
    try:
        result = await Runner.run(triage_agent, "who was the first president of the united states?")
        print(result.final_output)
    except InputGuardrailTripwireTriggered as e:
        print("Guardrail blocked this input:", e)

    # Example 2: General/philosophical question
    try:
        result = await Runner.run(triage_agent, "What is the meaning of life?")
        print(result.final_output)
    except InputGuardrailTripwireTriggered as e:
        print("Guardrail blocked this input:", e)

if __name__ == "__main__":
    asyncio.run(main())
View your traces
To review what happened during your agent run, navigate to the Trace viewer in the OpenAI Dashboard to view traces of your agent runs.
```
