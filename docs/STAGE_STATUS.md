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
- Eval runner.
- BI-ready SQL views.
- Human-readable run report script.
- Integration boundary tests for Slack signature verification and HubSpot note
  payload generation.

## Not Yet Connected

- Live CrewAI runtime smoke test with an LLM key.
- HubSpot private app configuration.
- Power BI `.pbix` file.

## Why This Is Still Useful

The hardest architecture decisions are already represented in code: state,
schema, validation, lifecycle, review decisions, and reporting views. External
tools can now be connected one by one without changing the core workflow.
