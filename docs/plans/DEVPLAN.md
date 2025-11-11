# Agent Gateway Drop-In Readiness – 10-Step Development Plan

Goal: Any engineer can drop an OpenAI Agents SDK module (e.g., `src/agents/SampleAgent/agent.py` from Agent Builder) into the repo and have it exposed securely via `/v1/chat/completions` without editing YAML or wrestling with tooling. This plan remediates the gaps documented in `docs/plans/Gap_Analysis_Report.md` and aligns the codebase with the Spark/SampleAgent patterns.

---

## 1. Discovery & Registry Resilience ✅
- **Problem:** `src/registry/discovery.py` only considers hard-coded export names and swallows import errors; `src/registry/agents.py` silently drops agents.
- **Work:**  
  - Allow configurable export names (default `agent`, `build_agent`, etc.) via `GATEWAY_AGENT_EXPORTS`.  
  - Capture import failures (missing deps, syntax errors) with structured diagnostics stored in memory and surfaced via `/admin/agents`.  
  - Persist module hash + mtime to avoid redundant re-imports when unchanged.
- **Acceptance:** Dropping SampleAgent registers automatically, and `/admin/agents` reports success/errors per file.

## 2. Automatic Defaults & Per-Agent Overrides ✅
- **Problem:** Agents require `defaults.upstream/model` in YAML; no in-code overrides.
- **Work:**  
  - Update `src/config/settings.py` + `src/registry/models.py` to provide safe defaults (fallback to `default` namespace + configured upstream).  
  - Support optional `__gateway__ = {"model": "...", "upstream": "..."}` metadata inside agent modules for per-agent overrides.  
  - Log validation issues instead of silently skipping agents.
- **Acceptance:** Example SampleAgent works with zero YAML; overrides show in `/v1/models`.

## 3. Dependency Awareness & Installer Hooks ✅
- **Problem:** Missing `openai-agents` or agent-specific deps cause opaque failures.
- **Work:**  
  - Allow optional `requirements.txt` next to each agent module and detect missing wheels during discovery.  
  - Add CLI (`scripts/install_agent_deps.py`) plus documentation to bulk-install agent dependencies.  
  - Emit actionable errors when deps are missing.
- **Acceptance:** If Spark’s folder declares deps, `POST /agents/refresh` warns and helper script installs them.

## 4. Security Policy Flexibility
- **Problem:** `src/security/security.yaml` allowlists are coarse; adding agents requires file edits and reloads.
- **Work:**  
  - Introduce per-namespace defaults and short-lived overrides exposed via `/security/preview` and `/security/override`.  
  - Log every allow/deny decision with agent path + policy reason.  
  - Document workflow in `docs/guides/OperatorRunbook.md`.
- **Acceptance:** Operators can temporarily permit SampleAgent without redeploying, and logs capture decisions.

## 5. Tooling Bridge & Metrics
- **Problem:** SDK tools must be decorated and can’t easily reuse gateway-managed tools.
- **Work:**  
  - Expand `src/sdk_adapter/gateway_tools.py` to auto-register gateway tools for SDK agents (with caching + metrics).  
  - Ensure `src/tooling/manager.py` records tool provenance (SDK vs gateway).  
  - Provide docs + SampleAgent snippet showing both native and gateway tools.
- **Acceptance:** SampleAgent can call local `@function_tool`s plus `gateway_tool("fetch_doc")` seamlessly with telemetry.

## 6. Structured Error Reporting & Observability
- **Problem:** 502 errors hide root causes; logs lack context.
- **Work:**  
  - Enhance `RequestLoggingMiddleware` (src/api/middleware.py) and `src/observability/logging.py` to attach `agent_id`, `module_path`, `error_stage`.  
  - Add `/admin/agents/errors` endpoint summarizing recent discovery/runtime issues.  
  - Emit Prometheus counters for drop-in import failures and tool violations.
- **Acceptance:** When SampleAgent has a typo, admin endpoints clearly show the reason without reproducing locally.

## 7. Hot Reload & Watch Mode
- **Problem:** `/agents/refresh` rescans synchronously; no auto-watch.
- **Work:**  
  - Integrate `watchfiles` (optional dependency) to monitor `src/agents/**` and trigger incremental reloads.  
  - Cache discovery results by folder to reduce import churn.  
  - Expose `GATEWAY_AGENT_WATCH=1` env toggle for dev mode.
- **Acceptance:** Editing SampleAgent triggers reload within seconds; production mode remains manual.

## 8. Drop-In Acceptance Suite
- **Problem:** `tests/test_dropin_agents_acceptance.py` is TODO; no regression protection.
- **Work:**  
  - Materialize fixtures (SampleAgent, Spark, guardrails, handoffs) and run them through FastAPI test client to assert `/v1/models`, `/v1/chat/completions` (streaming + tool usage).  
  - Add targeted tests for dependency errors, security overrides, and gateway-tool bridging.  
  - Wire into `make test` and CI.
- **Acceptance:** CI fails on any regression affecting drop-in agents; SampleAgent scenario is covered.

## 9. Documentation & UX Refresh
- **Problem:** Docs mention old workflows; new features must be discoverable.
- **Work:**  
  - Update `docs/guides/DropInAgentGuide.md`, `docs/guides/SDKOnboarding.md`, `docs/README.md`, and `AGENTS.md` with the simplified UX (copy SampleAgent folder, optional metadata, dependency helper).  
  - Provide copy/paste template mirroring the SampleAgent snippet, including best practices for instructions, tools, and security expectations.  
  - Add troubleshooting matrix tying errors to plan features.
- **Acceptance:** A new engineer can follow the guide end-to-end without touching YAML and successfully serve SampleAgent.

## 10. Release & Operational Automation
- **Problem:** No automated guarantees that drop-in readiness remains intact.
- **Work:**  
  - Extend `.github/workflows/ci.yml` (or equivalent) to run lint + acceptance suite + dependency audit (`scripts/nightly_audit.py`).  
  - Add release checklist referencing security overrides, dependency helper, and doc updates.  
  - Track metrics (success/fail counts) and surface in `docs/plans/LaunchReadinessReview.md`.
- **Acceptance:** Releases require green drop-in tests; nightly job alerts on dependency/security issues affecting agents.

---

Delivering these steps ensures the Agent Gateway meets the target UX: developers simply drop a compliant OpenAI Agents SDK file like the SampleAgent example into `src/agents/<Name>/agent.py`, and the gateway handles discovery, configuration, tooling, observability, and security automatically. By closing the documented gaps and enforcing continuous validation, the platform becomes dependable for production drop-in agents.
