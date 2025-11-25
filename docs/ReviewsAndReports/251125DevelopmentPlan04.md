# 251125 Development Plan 04 — Complete Drop-In Agent UX

## Goal
Close the gaps identified in `251125GapAnalysis04.md` so that any valid OpenAI Agents SDK module dropped under `./src/agents/<AgentName>/agent.py` is exposed as an OpenAI-compliant model via `/v1/chat/completions` (streaming and tool-calling) without YAML edits, with clear observability and security governance.

## Target UX Summary
- Engineer places `./src/agents/<AgentName>/agent.py` (Agent Builder-style export).
- Agent is auto-discovered/registered as a model and listed by `/v1/models` (respecting security allowlists/overrides).
- Callable via `/v1/chat/completions` with streaming/tool-calling parity for SDK and declarative agents.
- Tooling governance (allowlists/metrics), security, and observability (logs/metrics/admin diagnostics) are enforced and documented.

## Scope
- Included: API (chat streaming error handling), registry/discovery diagnostics, executor/SDK adapter governance, security defaults for native SDK tools, sample drop-in in `src/agents`, docs (README, observability).
- Excluded: Modifying `examples/` behavior at runtime (used only as a source template), container/packaging changes.

## Progress Tracker
- [x] Step 1 — Fix streaming error handling parity
- [x] Step 2 — Improve discovery diagnostics and sample agent validity
- [x] Step 3 — Align native SDK tool governance defaults
- [x] Step 4 — Update documentation and observability references

## Step 1 — Fix streaming error handling parity
**Purpose / rationale:** Ensure streaming chat responses surface accurate 404/403 errors instead of 500s, matching non-streaming behavior and reducing client friction.
**Tasks:**
- Update `api/services/chat.py` streaming path to map `AgentNotFoundError` to 404 and ACL `PermissionError` to 403.
- Add regression test covering `/v1/chat/completions?stream=true` for unknown/denied agents.
- Verify metrics/log context still record request-level data on early error returns.
**Exit criteria:** Streaming requests return 404 for missing agents and 403 for ACL denials; tests pass and no regression in successful streaming.

## Step 2 — Improve discovery diagnostics and sample agent validity
**Purpose / rationale:** Make discovery failures observable and ensure the shipped sample agent is valid so users have a working drop-in in the primary discovery root.
**Tasks:**
- Wire `registry.discovery.AgentDiscoverer` diagnostics into `error_recorder` and `record_dropin_failure`.
- Add unit/acceptance coverage to assert diagnostics appear in `/admin/agents/errors` and metrics counters increment.
- Replace `src/agents/SampleAgent/agent.py` with the working Agent Builder-style example (from `examples/agents/Simple_OpenAI_Agent/agent.py`) or a minimal valid SDK agent.
- Confirm `/v1/models` lists the sample agent and `/admin/agents` shows no lingering discovery errors.
**Exit criteria:** Discovery errors are recorded and counted; SampleAgent loads without diagnostics; acceptance tests for discovery/agents endpoints pass.

## Step 3 — Balance native SDK tool governance and UX
**Purpose / rationale:** Preserve security by requiring explicit allowlisting for native `@function_tool` calls, while providing a low-friction path and guardrails so drop-ins stay compatible with Agent Builder patterns.
**Tasks:**
- Keep a restrictive default allowlist but document the expected `security.yaml` entry for native SDK tools (sample patterns and a minimal starter entry).
- Add automated governance tests: one that proves native tools are blocked by default, and another that proves they succeed when the allowlist entry is present, with metrics labeled `source="sdk"`.
- Expose a diagnostic/preflight hint (e.g., clearer error message or admin guidance) so operators know to add the allowlist entry.
- Update Troubleshooting/README to explain the security-first default and how to opt in per tool/module.
**Exit criteria:** Default posture remains explicit allowlisting; operators have clear instructions and diagnostics to enable native SDK tools; governance tests cover both blocked and allowed cases; metrics/logs continue to capture SDK tool usage when allowed.

## Step 4 — Update documentation and observability references
**Purpose / rationale:** Eliminate dead links and clarify security/observability expectations for drop-ins.
**Tasks:**
- Add `docs/systems/observability.md` covering logs, metrics (`/admin/metrics`, Prometheus), recent errors, and request ID propagation.
- Update README and relevant guides to note the native tool allowlist requirement/behavior and that the legacy “AgentGateway_10-Step_Development_Plan.md” is retired.
- Cross-link the new observability doc from README and Gap/Plan references.
**Exit criteria:** README and guides have accurate links; observability doc exists; documentation reflects current security/tool governance behavior.

## Step 5 — Error messaging audit and polish
**Purpose / rationale:** Deliver clear, user-friendly error messaging across the application, with structured logging and clean exits, so users know what went wrong, why, and how to fix it without raw tracebacks.
**Tasks:**
- Inventory error paths (API routes, registry/discovery, executor/SDK adapter, tooling, security) and define standardized messages that include cause, likely user action, and remediation hints.
- Centralize message strings in dedicated classes under `src/registry/` for organized reuse and to keep text out of business logic.
- Update error handling to emit friendly responses while still logging full context via the existing logging pipeline and error recorder; avoid unhandled tracebacks.
- Add tests to validate message clarity and that structured logs/error recorder entries still fire.
**Exit criteria:** Error responses are polished and consistent; messages are sourced from centralized classes in `src/registry/`; logs/metrics/error recorder continue to capture details; tests cover representative error cases.
