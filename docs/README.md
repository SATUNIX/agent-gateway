# Agent Gateway Documentation

This folder contains the living documentation for the Agent Gateway. Start here for navigation to guides, references, plans, and reports.

## Structure
- `guides/`
  - `DropInAgentGuide.md` — How to add OpenAI Agents SDK modules (drop-ins), tooling, and watch mode.
  - `SDKOnboarding.md` — Onboarding flow for SDK authors (tools, dependencies, tests, overrides).
  - `OperatorRunbook.md` — Day-2 operations, overrides, metrics, and refresh endpoints.
  - `Troubleshooting.md` — Common errors and remediations.
- `plans/`
  - `Gap_Analysis_Report.md` — Live gap-tracking reference for the drop-in UX.
  - `LaunchReadinessReview.md` — Release readiness checklist.
- `ReviewsAndReports/` — Historical and current gap analyses and development plans.

## Observability Reference
- Logs: Structured JSON with `request_id`, `agent_id`, `module_path`, `error_stage`, and tool/upstream events.
- Metrics:
  - Admin: `GET /admin/metrics` returns `tool_breakdown`, `dropin_failures`, request counts/latency, and tool metrics.
  - Prometheus: `GET /metrics/prometheus` when enabled; includes request, tool, upstream, and drop-in failure counters/histograms.
- Recent errors: `GET /admin/agents/errors` exposes the in-memory ring buffer of discovery/runtime issues.
- Request context: `x-request-id` header is accepted/returned; middleware sets correlation IDs and log context.

## Key Links
- Drop-in guide: `guides/DropInAgentGuide.md`
- SDK onboarding: `guides/SDKOnboarding.md`
- Troubleshooting: `guides/Troubleshooting.md`
- Live gap reference: `plans/Gap_Analysis_Report.md`
- Current reports: `ReviewsAndReports/251125GapAnalysis03.md`, `ReviewsAndReports/251125DevelopmentPlan03.md`
