# Stage Status

## Implemented Now

- Stage 0 local project skeleton.
- ICP profiles.
- Offline Researcher fixture.
- Grounding validation.
- Analyst scoring.
- Writer evidence check.
- SQLite system of record with Postgres-shaped schema.
- Worker that processes queued runs.
- FastAPI endpoint definitions.
- Slack and HubSpot integration boundaries.
- Eval runner.
- BI-ready SQL views.
- Human-readable run report script.
- Integration boundary tests for Slack signature verification and HubSpot note
  payload generation.

## Not Yet Connected

- Real CrewAI Agent/Task runtime.
- Real Tavily Search/Extract calls.
- Running FastAPI server with installed dependencies.
- Zapier UI configuration.
- Slack app configuration.
- HubSpot private app configuration.
- Power BI `.pbix` file.

## Why This Is Still Useful

The hardest architecture decisions are already represented in code: state,
schema, validation, lifecycle, review decisions, and reporting views. External
tools can now be connected one by one without changing the core workflow.
