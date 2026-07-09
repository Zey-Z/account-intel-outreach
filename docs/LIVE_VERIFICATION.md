# Live Verification Record

This document records what was actually exercised in the portfolio deployment.
It is evidence of a test deployment, not a claim of enterprise production use.

## Verification Snapshot

Date: 2026-07-09  
Environment: Render web service + Neon PostgreSQL  
Runtime: CrewAI agents + Tavily research  
Repository: `Zey-Z/account-intel-outreach`

## Automated Quality Gates

- The complete offline test suite passed: 77 tests.
- GitHub Actions CI completed successfully for commit `c9a1f8b`.
- The Render deploy job ran only after the test gate passed.
- GitHub Actions run evidence:
  - CI: `https://github.com/Zey-Z/account-intel-outreach/actions/runs/29048704581`
  - Test-gated deploy: `https://github.com/Zey-Z/account-intel-outreach/actions/runs/29048704699`

## Live Service Checks

- `GET /health` returned HTTP 200.
- Protected `GET /health/deep` returned HTTP 200 and confirmed PostgreSQL
  connectivity.
- Protected `GET /runtime/status` reported `crewai` agent runtime and `tavily`
  research mode at deployed commit `c9a1f8b`.
- Invalid ICP input returned HTTP 400 instead of creating a stuck worker run.

## Real Workflow Smoke Test

Company: Oscar Health  
Run ID: `06abd522-daff-46db-a311-785fd38cceaf`

Observed result:

- The API accepted the request and stored it as `queued`.
- The automatic worker claimed the run exactly once.
- CrewAI and Tavily produced five public-source findings.
- All five findings passed the source-grounding check.
- The analyst produced a fit score of 65.
- The writer produced one draft and routed it to human review.
- The run reached `sent_to_review` with zero retries.
- Slack accepted the review message.

The system did not send an email. A human must still approve, reject, or request
changes. This is an intentional business control, not an unfinished automation.

## CRM Verification Boundary

The HubSpot integration now searches for or creates a Company and creates an
approved Note associated with that Company. Unit tests verify the exact HubSpot
payload, including the default Note-to-Company association. The new live smoke
test still requires a human Slack approval before its CRM filing can be observed.

## Container Verification

- A clean Docker image was built from `python:3.12-slim`.
- The container ran as `appuser` with UID 1000, not as the root administrator.
- Its `/health` endpoint returned HTTP 200.
- Docker reported the container as `healthy` using the built-in health check.

## Honest Remaining Boundary

- Render's free/demo hosting and single-process in-memory rate limiter are not an
  enterprise high-availability setup.
- A real Power BI `.pbix` artifact has not yet been created; the SQL views and
  protected CSV feeds are ready for it.
- The metrics above are test-context results from a portfolio deployment.

