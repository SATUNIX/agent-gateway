# Gap Analysis Report

## Metadata
- Date: 2025-11-25
- Reviewer: Codex
- Codebase Version: fba3ca5

## Summary
- Declarative streaming/tool loop is present, but the Agents SDK path is currently broken by syntax/import errors in `src/sdk_adapter/adapter.py`, so drop-in agents cannot execute.
- Tool governance blocks native `@function_tool` usage, so Agent Builder-style drop-ins fail despite being the target pattern; SDK streaming remains synthetic and bypasses gateway tool/metrics flows.
- The intended drop-in location (per README/example screenshot) is `examples/agents/**`, but discovery defaults to `src/agents/**`, so example agents are not surfaced as `/v1/models`.
- Documentation references (`docs/README.md`, `docs/systems/observability.md`) are missing, limiting verification of observability guidance and doc hierarchy.

## Gaps Identified
| Gap Description | Location/Module | Impact | Suggested Remediation |
| --- | --- | --- | --- |
| SDK adapter contains a malformed `try` block and missing `ChatCompletionChoice` import, causing import-time failures for any SDK agent | `src/sdk_adapter/adapter.py` | Gateway crashes or raises on drop-in load; `/v1/models` and `/v1/chat/completions` cannot serve SDK agents, blocking the drop-in goal | Fix indentation/imports, add adapter import smoke test, and run drop-in acceptance to ensure SDK paths load |
| Hard block on native Agents SDK tools (`__gateway_tool__` required) conflicts with Agent Builder/SampleAgent patterns | `src/sdk_adapter/adapter.py::_enforce_sdk_tool_governance` | Agent Builder exports using `@function_tool` fail before execution; docs promise copy/paste support with native tools | Allow native SDK tools and auto-instrument them through `tool_manager`/metrics/ACLs, reserving hard blocks for security violations; update docs/tests accordingly |
| Drop-in discovery ignores `examples/agents/**` even though example agents and README screenshots live there | Discovery defaults in `config/settings.py`; `registry.agents.AgentRegistry` | Example agents are invisible to `/v1/models`, breaking the documented drop-in location and confusing users | Expand discovery roots or defaults to include `examples/agents/**` (configurable), and add tests/docs confirming that folder is discoverable |
| Agents SDK execution drops SDK semantics (no TResponseInputItem conversion, synthetic streaming, no gateway tool loop or upstream metrics) | `src/sdk_adapter/adapter.py::_run_openai_agent`, `_build_runner_input`; `agents.executor.stream_completion` (SDK path) | Agent Builder outputs are flattened to a final string; tool calls are not routed via the gateway; streaming is buffered and omits tool deltas; upstream calls go unobserved | Map ChatCompletion messages to SDK input items, stream Runner deltas/tool calls to SSE, execute SDK tool calls via `tool_manager` with metrics/security, and record upstream usage; extend acceptance tests for streaming/tool flows |
| Referenced documentation is missing (`docs/README.md`, `docs/systems/observability.md`) | README.md, AGENTS.md references | Onboarding and observability alignment cannot be verified against cited sources; contributors face dead links | Add or restore the referenced docs (or retarget links to existing guides) and capture observability expectations alongside the live gap/plan docs |

## Remediation Alignment
- The live reference (`docs/plans/Gap_Analysis_Report.md`) is present, and prior gaps around missing SDK dependency, drop-in diagnostics, and declarative streaming/tool execution have been partially addressed (openai-agents is a dependency, discovery diagnostics surface errors, and declarative streaming executes tools).
- Alignment remains incomplete because the SDK adapter path is currently broken and governance blocks Agent Builder-native tools, leaving the core drop-in UX unresolved relative to the live gap plan.

## Agent Pattern Alignment
- Discovery, defaults, and diagnostics align with drop-ins under `src/agents/**`, but the documented/example location `examples/agents/**` is not discovered by default.
- Runtime behavior diverges: Agent Builder-style agents with native tools are rejected, SDK runs flatten outputs and skip gateway tool governance/streaming parity, so README/example agents cannot execute as-is or be listed as models.

## Conclusion
The gateway does not meet the goal of serving Agent Builder-style drop-ins (including the example under `examples/agents/`) via `/v1/chat/completions` without friction. SDK runtime errors, over-strict tool governance, the undiscovered example path, and missing docs block execution and verification. Goals remain unmet until these gaps are closed.
