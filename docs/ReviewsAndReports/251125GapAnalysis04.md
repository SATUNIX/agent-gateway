# Gap Analysis Report

## Metadata
- Date: 2025-11-25
- Reviewer: Codex
- Codebase Version: fba3ca5

## Summary
The gateway largely covers declarative agents and basic SDK execution, but the drop-in UX still falls short of the goal: native Agent Builder-style tools hit the default security allowlist, streaming error handling is inconsistent, discovery observability misses diagnostics, the bundled SampleAgent is broken, and required observability documentation is missing. These gaps block a frictionless “drop in and serve via `/v1/chat/completions`” experience.

## Gaps Identified
| Gap Description | Location/Module | Impact | Suggested Remediation |
| --- | --- | --- | --- |
| Native SDK `@function_tool` executions are denied by default allowlist (`tooling.local_tools:*` only) and surface `PermissionError`, requiring YAML edits | `src/security/security.yaml`; `sdk_adapter.adapter._wrap_native_tool` → `security_manager.assert_tool_allowed` | Agent Builder drop-ins with native tools fail despite being supported, breaking the “no YAML edits” goal | Expand defaults or auto-allow native SDK tool modules for drop-ins, document the policy in README/Troubleshooting, and add a governance test to confirm |
| Streaming path returns 500 on AgentNotFound/ACL errors instead of 404/403 | `api/services/chat.py` (`stream_completion`) | Clients see generic 500s for missing/blocked models; behavior diverges from non-streaming route | Map `AgentNotFoundError` to 404 and ACL `PermissionError` to 403 in streaming responses; add regression test |
| Discovery diagnostics aren’t sent to the error recorder or drop-in failure metrics | `registry.discovery.AgentDiscoverer._record_diagnostic` | Import/dependency/security failures are only visible on `/admin/agents`, reducing observability and metrics | Forward diagnostics to `error_recorder` and `record_dropin_failure`, and assert coverage via tests |
| Bundled drop-in is broken (SampleAgent imports missing symbols) | `src/agents/SampleAgent/agent.py` | Persistent discovery errors and polluted catalog; no valid default SDK sample | Replace SampleAgent with the working Agent Builder example (e.g., `examples/agents/Simple_OpenAI_Agent/agent.py` logic) or simplify to a minimal, valid SDK agent |
| Observability doc referenced in README is missing; legacy 10-step plan reference is stale | `docs/systems/observability.md` (missing); README “observability” link; roadmap note | Dead links hinder onboarding and verification of logging/metrics expectations | Add `docs/systems/observability.md` summarizing logging/metrics/admin surfaces; update README/plan references to note the old plan is retired |

## Remediation Alignment
- Aligned with `docs/plans/Gap_Analysis_Report.md` focus on drop-in UX and observability. The above gaps block the promised “copy → run → chat” path and require code plus docs updates to close.

## Agent Pattern Alignment
- Discovery defaults target `src/agents/**` with extra paths including `examples/agents/**`, but the shipped SampleAgent is invalid, so users lack a working template in the primary discovery root.
- SDK runtime supports Agent Builder objects but native tool governance and missing observability diagnostics still diverge from the Spark/SampleAgent pattern.

## Conclusion
Goals are **not yet met**. Remaining gaps: native tool allowlist friction, streaming error mapping, missing diagnostic telemetry, broken default sample agent, and missing observability documentation. Closing these items is required for a V1-ready drop-in MVP.
