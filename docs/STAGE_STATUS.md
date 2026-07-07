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
- SQLite system of record with Postgres-shaped schema.
- Worker that processes queued runs.
- FastAPI endpoint definitions.
- Zapier entry trigger path.
- Live Slack human-review workflow.
- HubSpot integration boundary.
- Approved-only HubSpot note sync path.
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
- Versioned database migrations with `schema_migrations` tracking.
- Structured API request logging with per-request `X-Request-Id`.
- In-memory rate limiting on public write/worker endpoints.
- API-key-protected deep health check for database reachability.
- BI-ready SQL views.
- Human-readable run report script.
- Integration boundary tests for Slack signature verification and HubSpot note
  payload generation.

## Not Yet Connected

- Live CrewAI runtime smoke test with an LLM key.
- Power BI `.pbix` file.
- GitHub secret `RENDER_DEPLOY_HOOK_URL` for automatic Render deploys, if not
  already configured.

## Why This Is Still Useful

The hardest architecture decisions are already represented in code: state,
schema, validation, lifecycle, review decisions, and reporting views. External
tools can now be connected one by one without changing the core workflow.
