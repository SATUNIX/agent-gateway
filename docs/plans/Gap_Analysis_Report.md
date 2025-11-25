# Gap Analysis Report (Live Reference)

Scope: Track current gaps for the drop-in Agent UX (exclude `examples/`). Any OpenAI Agents SDK module placed under `src/agents/<Name>/agent.py` should be exposed securely via `/v1/chat/completions` without YAML edits, with gateway-managed tooling, observability, and security.

Canonical sources:
- Current detailed gaps: `docs/ReviewsAndReports/251125GapAnalysis02.md`
- Active remediation plan: `docs/ReviewsAndReports/251125devplan02.md`

Status Highlights:
- SDK compatibility, streaming/tool-call handling, and gateway tooling governance are in progress via `251125devplan02.md`.
- Keep metrics/admin surfaces aligned with `GatewayMetrics.snapshot()` and ensure documentation links resolve to this file for gap alignment.

Notes:
- `examples/` remains out of scope for gap tracking per project guidance.
- Update this reference when a new gap analysis is published to maintain a single live target for plans and onboarding docs.
