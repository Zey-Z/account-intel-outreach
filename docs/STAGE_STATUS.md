# Stage Status

## Implemented Now

- Stage 0 local project skeleton.
- ICP profiles.
- Offline Researcher fixture.
- Real Tavily Search/Extract research boundary.
- Real CrewAI Agent/Task/Crew runtime switch.
- Grounding validation.
- Analyst scoring.
- Writer evidence check.
- SQLite local development plus Neon PostgreSQL cloud system of record.
- Worker with atomic database-backed queue claiming.
- FastAPI endpoint definitions.
- Zapier entry trigger path.
- Live Slack human-review workflow.
- Approved-only HubSpot Company lookup plus associated Note sync path.
- Idempotent CRM catch-up endpoint for approved drafts.
- API retry endpoint for failed runs.
- Company-level worker failure isolation.
- Optional in-process worker poller for demo/internal processing.
- Eval runner with 6-company fixture set and per-company grounding rate.
- CrewAI Writer knowledge guidance from approved messaging files.
- API-key-protected CSV reporting endpoints for BI views.
- Lazy database singleton in the FastAPI service.
- Exact pinned Python dependency versions.
- GitHub Actions CI for the offline unit test suite.
- GitHub Actions deploy workflow gated by the test suite.
- Encrypted Render Deploy Hook connected to GitHub Actions.
- Versioned database migrations with `schema_migrations` tracking.
- Structured API request logging with per-request `X-Request-Id`.
- In-memory rate limiting on public write/worker endpoints.
- API-key-protected deep health check for database reachability.
- Optional Docker containerization path.
- Production readiness documentation with known limitations.
- BI-ready SQL views.
- Power BI Desktop dashboard with workflow KPIs and status/quality charts.
- Human-readable run report script.
- Integration boundary tests for Slack signature verification and HubSpot note
  payload generation.

## Remaining External Verification

- Merge the protected pull request and verify migration `0004` plus the
  `dashboard_runs_view` CSV endpoint on Render.
- Refresh the saved PBIX from the deployed endpoint after that migration is
  live.

## Why This Is Still Useful

The hardest architecture decisions are already represented in code: state,
schema, validation, lifecycle, review decisions, and reporting views. External
tools can now be connected one by one without changing the core workflow.
