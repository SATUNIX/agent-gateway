# 251125 Development Plan 03 — Complete Drop-In Agent UX

## Goal
Close the gaps identified in `251125GapAnalysis03.md` so any OpenAI Agents SDK module (e.g., Agent Builder exports under `examples/agents/<Name>/agent.py` or the configured discovery root) is discoverable, secure, tool-governed, and stream-capable via `/v1/chat/completions` without YAML edits.

## Target UX Summary
- Drop in an Agent Builder-style folder under `examples/agents/<Name>/agent.py` (or configured discovery root) with optional `requirements.txt`; discovery auto-registers it under `/v1/models` and respects namespace/upstream defaults and security allowlists/overrides.
- `/v1/chat/completions` streams content and tool_call deltas using the configured upstream client; SDK and declarative agents share tool execution via `tool_manager` with metrics/ACLs and request/context logging.
- Developers rely on gateway-managed docs (`DropInAgentGuide`, `SDKOnboarding`, observability reference) with `/admin/agents`, `/admin/metrics`, `/admin/agents/errors` exposing health/diagnostics.

## Scope
- Included: API surface, registries/discovery (including `examples/agents/**`), executor, `sdk_adapter`, tool governance/manager, security manager/policies, tests, and documentation.
- Excluded: Unrelated container assets.

## Progress Tracker
- [x] Step 1 — Align discovery with `examples/agents` and unblock SDK adapter runtime path
- [x] Step 2 — Allow Agent Builder tools while preserving governance
- [x] Step 3 — Restore Agents SDK parity (context, streaming, tool loop)
- [x] Step 4 — Documentation and observability alignment

## Step 1 — Align discovery with `examples/agents` and unblock SDK adapter runtime path
**Purpose / rationale:** Ensure the documented/example agent location is discoverable and the SDK adapter loads.
**Tasks:**
- Add `examples/agents/**` to the discovery path/defaults (config + registry wiring) and cover it with acceptance tests/fixtures.
- Fix the malformed `try` block and import `ChatCompletionChoice` in `sdk_adapter/adapter.py`; add a smoke test that imports the module.
- Add a regression test that runs a basic SDK drop-in through `AgentExecutor` (non-streaming) to confirm ChatCompletionResponse construction succeeds from the examples path.
- Confirm dependency guards surface actionable errors when the SDK is missing (aligning with `agents/__init__.py`).
**Exit criteria:** Example agents under `examples/agents/**` are listed via `/v1/models` and callable; `sdk_adapter` imports cleanly; basic SDK drop-in invocation via `/v1/chat/completions` returns a valid response; new tests pass.

## Step 2 — Allow Agent Builder tools while preserving governance
**Purpose / rationale:** Support native `@function_tool` usage (Spark/SampleAgent) while keeping tool metrics/ACL enforcement.
**Tasks:**
- Relax `_enforce_sdk_tool_governance` to permit native SDK tools by auto-wrapping or instrumenting them to route through `tool_manager` with `source="sdk"` metrics.
- Keep enforcement for security violations (disallowed modules) with clear error messages; ensure gateway_tool wrappers remain supported and marked.
- Update docs (`DropInAgentGuide`, `SDKOnboarding`) and tests to cover both native function tools and gateway-managed tools.
**Exit criteria:** Agent Builder/SampleAgent fixtures with native tools execute successfully; tool invocations for SDK agents emit metrics/ACL checks; governance errors only occur for blocked tools.

## Step 3 — Restore Agents SDK parity (context, streaming, tool loop)
**Purpose / rationale:** Make SDK executions mirror Agent Builder behavior, preserving context, tool calls, and streaming semantics.
**Tasks:**
- Convert ChatCompletionRequest messages into SDK `TResponseInputItem` structures (roles, tool_calls, content blocks) before invoking `Runner.run` with the gateway upstream client.
- Stream Runner deltas/tool_calls to SSE (`/v1/chat/completions?stream=true`), executing tool calls via `tool_manager` mid-stream with policy enforcement and logging request IDs.
- Record upstream request metrics for SDK runs and honor policy limits (max_tokens/tool hops) across streaming and non-streaming paths.
- Add tests for multi-turn context preservation, SDK streaming with tool calls, and upstream client usage (including a SampleAgent-style fixture).
**Exit criteria:** SDK drop-ins stream content/tool_call deltas through the gateway, tool_manager handles SDK tool calls, upstream metrics reflect SDK traffic, and new tests pass.

## Step 4 — Documentation and observability alignment
**Purpose / rationale:** Remove dead links and document the updated SDK behaviors and operational expectations.
**Tasks:**
- Add or restore `docs/README.md` and an observability reference (or retarget README/AGENTS links) describing metrics/logging surfaces.
- Update gap/plan references to the live `docs/plans/Gap_Analysis_Report.md` and ensure new behaviors are reflected in `DropInAgentGuide` and `SDKOnboarding`.
- Note updated tool-governance/streaming behavior in README/Troubleshooting and ensure admin endpoints surface relevant diagnostics.
**Exit criteria:** No missing documentation references; observability guidance is present; docs align with the new SDK execution model and are linked from the gap/plan files.
