# Drop-in Agents SDK Test Plan

This document captures the acceptance criteria for Step 1 of the "Drop-in SDK Enablement" roadmap. It translates the findings in `docs/plans/CodeReview.md` into concrete fixtures, scenarios, and compatibility requirements that will drive implementation in later steps.

## Goals

1. **Guarantee drop-in workflow:** Adding `src/agents/<AgentName>/agent.py` that defines OpenAI Agents SDK objects must automatically expose `<AgentName>` via `/v1/models` and `/v1/chat/completions` without editing YAML.
2. **Honor SDK constructs:** Tools declared with `@function_tool`, handoffs, dynamic instructions, hooks, guardrails, output types, and Runner features must execute exactly as written in the SDK module.
3. **Preserve observability & security:** Existing gateway telemetry, streaming behavior, and ACL/rate-limit enforcement must apply equally to discovered SDK agents.

## Sample Fixtures (from CodeReview)

| Fixture ID | Description | Source snippet |
| --- | --- | --- |
| `HANDOFF_TRIAGE_AGENT` | Multi-agent triage workflow with handoffs between history/math tutors. | "Put it all together" section (guardrail + handoffs) |
| `LIFECYCLE_HOOK_AGENT` | Lifecycle hooks logging start/end/tool events plus handoffs (Start/Multiply). | `src/agents/proper_example.py` + hooks excerpt |
| `DYNAMIC_PROMPT_AGENT` | Context-driven instructions (haiku/pirate/robot). | Dynamic system prompt example |
| `GUARDRAIL_AGENT` | Input guardrail invoking a secondary agent to screen homework questions. | Guardrail section |
| `MANAGER_TOOLS_AGENT` | Manager-style agent exposing sub-agents as tools plus forced tool choice. | Manager (agents as tools) + tool_choice documentation |
| `BASIC_TOOL_AGENT` | Simple `@function_tool` usage returning weather data with structured output. | Basic configuration + structured output examples |

These fixtures are stored as reusable code snippets under `tests/fixtures/dropin_agents/__init__.py`. Acceptance tests can materialize them into the `src/agents/` directory as part of future steps.

## Compatibility Matrix

| Feature | Required Behavior |
| --- | --- |
| Agent discovery | File-based discovery under `src/agents/**` auto-registers models without YAML edits. |
| Tools (`@function_tool`) | Execute through SDK-defined semantics; gateway tooling is optional and opt-in via `sdk_adapter.gateway_tools.gateway_tool`. |
| Handoffs | SDK handoffs transfer conversation state without gateway intervention. |
| Hooks / lifecycle events | `AgentHooks` fire as defined in SDK module. |
| Dynamic instructions | Functions returning prompts run at execution time with context propagation. |
| Guardrails | Input/output guardrails execute via SDK `InputGuardrail` / `GuardrailFunctionOutput`. |
| Structured outputs | `output_type` and adapters like `ToolsToFinalOutputResult` flow through unchanged. |
| Streaming | `/v1/chat/completions` streaming mirrors SDK output (chunked SSE). |
| Security | ACLs + rate limits enforced per auto-discovered agent namespace. |
| Observability | Logs/metrics capture drop-in agents, tool calls, handoffs, and guardrails. |

## Acceptance Tests (Defined in `tests/test_dropin_agents_acceptance.py`)

1. **Model discovery:** Writing `HANDOFF_TRIAGE_AGENT` into `src/agents/TriageAgent/agent.py` and refreshing should expose the agent via `/v1/models` and `/admin/agents` without YAML changes.
2. **Streaming response:** Running `/v1/chat/completions` against a drop-in agent must stream chunks identical to the agent's Runner output.
3. **Tool execution:** An agent using `@function_tool` must invoke that tool via the SDK pipeline, with the gateway only mediating telemetry.
4. **Handoff path:** The Start→Multiply example must hand off control and return the downstream agent result through the chat API.
5. **Dynamic instructions:** The haiku/pirate/robot agent must honor randomly selected styles when executed through the gateway.
6. **Guardrail enforcement:** A guardrail-enabled agent must block/allow inputs exactly as when run via `Runner.run` directly.

> All acceptance tests are currently marked `xfail/skip` because the runtime lacks drop-in support. They provide executable documentation for the implementation work in Steps 2–4.

### Gateway-managed Tool Shims

Drop-in agents that wish to reuse HTTP/MCP/local tooling defined under `src/config/tools.yaml` can opt in via the helper `sdk_adapter.gateway_tools.gateway_tool(tool_name)`. The helper exposes a pre-wired `function_tool` that delegates to the gateway `ToolManager` while still running inside the OpenAI Agents SDK event loop. This shim is optional; pure SDK tools remain authoritative.

### Security Guardrails for Drop-in Modules

Operators can restrict which Python modules are executed by setting `default.dropin_module_allowlist` / `dropin_module_denylist` in `src/config/security.yaml`. The registry consults `SecurityManager.assert_agent_module_allowed()` for every discovered module, skipping and logging (`agent.dropin.blocked`) any entry that violates the policy. This ensures untrusted code cannot be imported without explicit approval.
