# 251125 Gap Analysis – Agent Gateway Drop-In UX

## Goal & Scope
- Target UX: drop any OpenAI Agents SDK module (e.g., Agent Builder exports under `src/agents/<Name>/agent.py`) and have it exposed securely via `/v1/chat/completions` without YAML edits or tooling friction.
- Scope: core gateway/runtime (API, registry/discovery, executor, SDK adapter, tooling, security, tests/docs). The `examples/` tree was excluded per request.

## High-Severity Gaps
1) **Tool-less declarative pipeline** (`src/agents/executor.py`)
- The payload sent to upstream chat completions never includes tool definitions or tool_choice/parallel tool call hints. Upstream models therefore cannot emit `tool_calls` based on `agents.yaml`/security tool allowlists; the tool loop only works in tests because `FakeChat` fabricates tool calls. Impact: gateway-managed tools are effectively unusable for declarative agents and for SDK agents that expect upstream-orchestrated tools. Action: include tool schemas from `tool_manager` when building payloads, honor `tool_choice`, and route tool call deltas back through `tool_manager` with provenance.

2) **SDK adapter drops context and streaming** (`src/sdk_adapter/adapter.py`)
- `_run_openai_agent` collapses the full message stack into a single prompt string (last user message) before calling `Runner.run`, losing assistant/tool context and multi-turn history. No streaming support; uses `asyncio.run` inside a thread, and returns a final string only. Gateway-managed tools are only reachable if authors manually wrap them with `use_gateway_tool`, and native `function_tool` calls bypass gateway metrics/ACLs. Impact: Spark/SampleAgent-style exports will not behave like they do in Agent Builder (missing context, missing streaming/tool traces). Action: preserve the full message list when invoking OpenAI Agents SDK (convert to `TResponseInputItem`), add true streaming/delta support, and enforce/emit gateway tool telemetry even for native SDK tools.

3) **Discovery defaults silently drop agents** (`src/registry/agents.py`)
- `_spec_from_export` requires upstream/model defaults (from YAML or `__gateway__`). If absent, the agent is skipped with only an in-memory diagnostic; nothing is logged to `/admin/agents/errors` or Prometheus drop-in counters. Result: a copied Agent Builder folder can simply vanish from `/v1/models` with no surface signal. Action: provide fallbacks from `Settings` (env overrides), emit diagnostics to `error_recorder`/`metrics.record_dropin_failure`, and expose them via `/admin/agents/errors`.

4) **Corrupted registry cleanup path** (`src/registry/agents.py:404-417`)
- `__del__` references undefined variables (`kind`, `message`, `export`, `severity`), raising `NameError` at GC and suggesting unfinished diagnostic logging. Action: remove or fix the destructor; move the intended metric/error recording into `_record_diagnostic` or the watch loop.

5) **Broken test artifacts** (`tests/test_smoke_gateway.py`, `tests/fixtures/async_sdk_agent.py`)
- Both files contain leftover patch markers (`*** End Patch`) and malformed content; the smoke test file is currently invalid Python. Impact: test collection fails, hiding regressions and CI signal. Action: clean the files and restore the intended fixtures/tests.

6) **Metrics schema drift** (`api/routes/admin.py`, `api/models/admin.py` vs `api/metrics.py`)
- `MetricsResponse` surfaces only basic latency counters; tool invocations/failures, per-tool breakdowns, and drop-in failure counts are dropped even though `GatewayMetrics.snapshot()` returns them. Operators cannot see tool health or discovery issues via `/metrics`. Action: expand the response model/route to return the full snapshot and align Prometheus exposure.

7) **Documentation reference is broken**
- Multiple docs (e.g., `docs/ReviewsAndReports/Old_Review_and_PLan/DEVPLAN.md`) point to `docs/plans/Gap_Analysis_Report.md`, which does not exist. Impact: onboarding to the remediation plan dead-ends. Action: add the referenced plan or update links to the current analysis.

## Additional Findings
- **Synthetic streaming only**: `api/services/streaming.py` slices a completed response into SSE chunks; upstream streaming and tool-call deltas are not forwarded. This mismatches OpenAI-compatible streaming expectations.
- **Discovery/watch coverage**: watch mode only reacts to `agent.py` changes; helper modules/`requirements.txt` edits in a drop-in folder will not trigger reloads in watch mode (they rely on periodic mtime checks instead).
- **Discovery telemetry gaps**: dependency/validation failures recorded via `_record_diagnostic` are not pushed to `error_recorder` or drop-in Prometheus counters, despite docs claiming visibility.
- **Security pattern limitations**: `AuthContext` allowlist matching supports only exact, `*`, or `<namespace>/*`; broader globbing (`*Agent`, `labs/*planner*`) isn’t honored despite doc hints. If intended, fnmatch-style patterns are needed.
- **SDK tool governance**: native SDK `function_tool` executions are outside gateway observability/ACLs unless authors swap to `use_gateway_tool()`. This undercuts the “centralized tooling” promise; document or enforce a wrapper.

## Recommended Remediation Plan (priority order)
1. Clean the broken test/fixture files so CI is trustworthy again.
2. Fix registry cleanup and discovery telemetry: remove the bad destructor, emit diagnostics to `/admin/agents/errors` and drop-in metrics, and add default upstream/model fallbacks.
3. Wire tool definitions and choices into upstream payloads, then route returned tool calls through `tool_manager` with security/metrics; add real streaming passthrough for both declarative and SDK flows.
4. Upgrade the SDK adapter for OpenAI Agents: preserve full conversation context, avoid `asyncio.run` anti-patterns, and add streaming plus gateway-tool enforcement/metrics for native tools.
5. Expand `/admin/metrics` (and docs) to surface tool and discovery stats; ensure Prometheus mirrors the same fields.
6. Improve watch-mode coverage (include helper/requirements changes or document limitations) and align security pattern matching with documented expectations.

## Residual Risks
- Until tool schemas and streaming are fixed, the advertised “drop-in SDK agents” experience will diverge from Agent Builder/Spark behavior, especially for tool-heavy workflows.
- Lack of surfaced discovery telemetry can lead to silent production outages when agents are skipped.
- Broken tests/fixtures reduce confidence in any future changes until cleaned.
