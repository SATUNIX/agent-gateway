# Agent Gateway – Drop-in SDK Enablement Plan

**Context:** The code review (see `docs/plans/CodeReview.md`) confirmed the gateway currently requires YAML-defined agent specs, ignores SDK-defined tools/handoffs/hooks, and forces custom runner wrappers. The goal is to allow engineers to create `src/agents/SomeAgent/agent.py` containing standard OpenAI Agents SDK definitions and have that agent automatically exposed as a `model` over `/v1/chat/completions`, with secure tool execution, streaming, and upstream routing. The following 10-step plan describes the concrete engineering work needed to reach that goal.

---

## Step 1 – Define Target Contract & Acceptance Tests
**Status:** [x] Completed  
- **Objective:** Translate the SDK expectations from `docs/plans/CodeReview.md` into executable requirements before making code changes.  
- **Key tasks:**  
  - Capture sample agents/tools from the review doc as fixtures (handoffs, hooks, dynamic instructions, guardrails).  
  - Define acceptance tests describing “drop a module under `src/agents/` and call `/v1/chat/completions` ➜ response streams back.”  
  - Specify compatibility matrix for Runner features we must support in this release.  
- **Deliverables:** ✅ `docs/plans/DropInAgents_TestPlan.md` + `tests/test_dropin_agents_acceptance.py` (skipped) outlining the required UX.

## Step 2 – Implement Agent Discovery & Registry Refactor
**Status:** [x] Completed  
- **Objective:** Replace the YAML-only registry with a loader that scans `src/agents/**/` for SDK modules and builds runtime metadata.  
- **Key tasks:**  
  - Walk the `agents` package (respecting `__init__` exclusions) and import discovered modules safely.  
  - Detect exported `Agent`, `Runner` factories, or helper functions without requiring YAML metadata.  
  - Keep YAML only for legacy overrides; the default flow must be “add `src/agents/NewThing/agent.py` → it auto-appears in `/v1/models` with no registry edit.”  
- **Deliverables:** ✅ `registry/discovery.py`, updated `AgentRegistry` merge logic, plus `tests/test_agent_discovery.py` verifying discovered agents appear without YAML edits.

## Step 3 – Align Executor With Native SDK Runner
**Status:** [x] Completed  
- **Objective:** Stop requiring custom `run_sync` wrappers; directly invoke SDK `Runner.run` (async) or `Agent` APIs.  
- **Key tasks:**  
  - Update `sdk_adapter` to detect whether the imported object is an `Agent`, callable returning an `Agent`, or a helper that already calls Runner, and accept raw `Agent` instances without any gateway-specific runner signature.  
  - Provide async-aware execution (no nested `asyncio.run`) and support context propagation, hooks, and guardrails.  
  - Ensure handoffs, tool behavior, and structured outputs are preserved from the SDK instance.  
- **Deliverables:** ✅ Refactored `sdk_adapter/adapter.py` to accept raw Agents/factories, plus new fixtures/tests in `tests/test_sdk_adapter.py` verifying async/sync + Agent execution paths.

## Step 4 – SDK-First Tools & Handoffs
**Status:** [x] Completed  
- **Objective:** Treat SDK-declared tools, handoffs, hook chains, and behaviors as the source of truth; only bridge to gateway primitives when absolutely necessary.  
- **Key tasks:**  
  - When loading an SDK agent, introspect `agent.tools`, `handoffs`, `tool_use_behavior`, guardrails, etc., and execute them as-is without normalizing into a new schema.  
  - Provide minimal shims only when an SDK agent explicitly opts into gateway-managed tools (e.g., to reuse existing MCP/local services); otherwise keep SDK definitions authoritative.  
  - Ensure tool invocation telemetry hooks into the gateway’s metrics/logging while leaving execution semantics untouched.  
- **Deliverables:** ✅ `sdk_adapter/context.py` + `sdk_adapter/gateway_tools.py` (optional `gateway_tool` shim), unit coverage in `tests/test_gateway_tools.py`, and docs/test-plan updates describing the opt-in bridge.

## Step 5 – Model Selection & Routing UX
**Status:** [x] Completed  
- **Objective:** Make discovered agents visible and selectable to the chat UI without manual configuration.  
- **Key tasks:**  
  - Add `/v1/models` (OpenAI format) plus `/admin/agents` enhancements that list dynamically loaded SDK agents.  
  - Map `ChatCompletionRequest.model` to the discovered agent IDs; provide aliases for backward compatibility.  
  - Implement hot-reload or watch mode so new folders become available without restarting the API server.  
- **Deliverables:** ✅ New `/v1/models` route (`api/routes/models.py` + schemas) wired into FastAPI, drop-in metadata surfaced via `registry/discovery.py`, and serialization tests in `tests/test_models_endpoint.py`.

## Step 6 – Security & Sandbox Hardening
**Status:** [x] Completed  
- **Objective:** Ensure dynamically imported SDK modules execute within the existing auth/rate-limit/tool-allowlist constraints.  
- **Key tasks:**  
  - Enforce namespace ACLs on discovered agents (e.g., folder path = namespace).  
  - Validate imported modules against a configurable allowlist/denylist; document expectations for untrusted code.  
  - Extend tool security checks to cover SDK-defined tools (e.g., verifying underlying module paths).  
- **Deliverables:** ✅ `security/manager.py` module allow/deny enforcement (configurable via `src/config/security.yaml`), registry integration that logs/blocks disallowed modules, and regression tests in `tests/test_security_manager.py`, `tests/test_agent_discovery.py`, and `tests/test_gateway_tools.py`.

## Step 7 – Streaming, Error, and Observability Coverage
**Status:** [x] Completed  
- **Objective:** Guarantee streaming responses, errors, and metrics behave identically for SDK and declarative agents.  
- **Key tasks:**  
  - Ensure SDK runs yield incremental output for `/v1/chat/completions` streaming mode (chunk generator backed by Runner events).  
  - Emit structured logs/metrics for handoffs, hooks, guardrails, and tool calls originating from SDK agents.  
- **Deliverables:** ✅ Centralized SSE helpers (`api/services/streaming.py` + tests), logging for SDK agent lifecycle in `sdk_adapter/adapter.py`, and documentation/test updates validating streaming output.

## Step 8 – Documentation & Developer Workflow
**Status:** [x] Completed  
- **Objective:** Provide a clear workflow describing how to author, drop in, test, and hot-reload SDK agents locally.  
- **Key tasks:**  
  - Update README + new “Drop-in Agent Guide” referencing the examples from `docs/plans/CodeReview.md`.  
  - Document folder conventions, naming → model ID mapping, supported Runner features, and limitations.  
  - Publish troubleshooting steps for import errors, tool permission failures, and streaming diagnostics.  
- **Deliverables:** ✅ `docs/guides/DropInAgentGuide.md`, reorganized docs index (`docs/references/README.md`), enhanced README (cross-platform quick start, drop-in workflow, troubleshooting), and updated references in `docs/plans/DropInAgents_TestPlan.md`.

## Step 9 – End-to-End UAT & Backend Matrix
**Status:** [ ] Pending  
- **Objective:** Validate the new drop-in flow against multiple front-ends (Open WebUI, curl, SDK clients) and upstreams (OpenAI, LM Studio, Ollama).  
- **Key tasks:**  
  - Build automation that spins up sample agents (from the review doc) and runs scripted conversations via each client.  
  - Record successes/failures per backend, including streaming, tool calls, handoffs, and guardrails.  
- **Deliverables:** UAT report + compatibility matrix referenced by operators.

## Step 10 – Launch Readiness & Sign-off
**Status:** [ ] Pending  
- **Objective:** Certify that Steps 1–9 are complete, the gateway meets the drop-in requirement, and packaging/CI artifacts are in place.  
- **Key tasks:**  
  - Re-run acceptance tests, security scans, and observability checks.  
  - Produce final release notes describing the drop-in capability and migration guidance from YAML agents.  
  - Obtain stakeholder approval and tag the release.  
- **Deliverables:** Launch Readiness Review packet + release candidate images/SBOMs.

---

### Success Criteria After Completing the Plan
- Engineers can add `src/agents/<AgentName>/agent.py` containing vanilla OpenAI Agents SDK code and see `<AgentName>` automatically exposed via `/v1/models`/`/v1/chat/completions` without touching YAML.  
- SDK-defined tools, handoffs, hooks, guardrails, and output types run unchanged through the gateway, with full streaming support and observability.  
- Security policies, rate limits, and tool allowlists continue to apply to dynamically discovered agents.  
- Documentation, tests, and CI/CD artifacts cover the new workflow end-to-end, enabling confident local or production deployments.
