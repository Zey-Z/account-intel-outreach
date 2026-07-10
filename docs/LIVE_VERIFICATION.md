# Live Verification Record

This document records what was actually exercised in the portfolio deployment.
It is evidence of a test deployment, not a claim of enterprise production use.

## Verification Snapshot

Date: 2026-07-09  
Environment: Render web service + Neon PostgreSQL  
Runtime: CrewAI agents + Tavily research  
Repository: `Zey-Z/account-intel-outreach`

## What This Record Proves

This is a traceable portfolio deployment record. It combines four different
types of evidence instead of treating one successful screenshot as proof of the
whole system:

| Evidence type | What was checked |
|---|---|
| Automated | Ruff, 82 unit tests, and Docker image build. |
| Service | Public health, protected deep health, runtime mode, and request tracing. |
| Business flow | Research, fit scoring, drafting, Slack approval, and HubSpot filing. |
| Reporting | Protected CSV contract, 15-run snapshot, and refreshed Power BI artifact. |

## Automated Quality Gates

- The complete offline test suite passed: 82 tests.
- The protected pull request required Ruff lint, unit tests, and a real Docker
  image build. All six push/PR check records passed before merge.
- Pull request `#1` was squash-merged as commit `164108d6`.
- The Render deploy job ran only after the test gate passed.
- GitHub Actions run evidence:
  - CI: `https://github.com/Zey-Z/account-intel-outreach/actions/runs/29069363447`
  - Test-gated deploy: `https://github.com/Zey-Z/account-intel-outreach/actions/runs/29069363508`
  - Pull request: `https://github.com/Zey-Z/account-intel-outreach/pull/1`

## Live Service Checks

- `GET /health` returned HTTP 200.
- Protected `GET /health/deep` returned HTTP 200 and confirmed PostgreSQL
  connectivity with 20.331 ms database latency during verification.
- Protected `GET /runtime/status` reported `crewai` agent runtime and `tavily`
  research mode at deployed commit `164108d6`.
- The deep-health response included `X-Request-Id`
  `60ac3f42-aa04-48ac-902c-1893a5833407`, proving request tracing reached the
  live service.
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

The system did not send an email. A human approved the draft in Slack. The
approval buttons were replaced with a recorded decision, proving the review
round trip while preserving the no-auto-send control.

## CRM Verification

- The Slack approval created a HubSpot Note associated with Oscar Health.
- HubSpot returned object ID `382074375877`.
- The run event log recorded `crm_synced` and the Slack message update succeeded.
- After deployment, startup reconciliation repaired the stale run summary from
  `sent_to_review` to `synced_to_crm`, set `finished_at`, and recorded one
  `run_status_reconciled` event.

## Power BI Artifact

- Created `powerbi/AI_Account_Intelligence_Dashboard.pbix` in Power BI Desktop.
- The first page contains six workflow KPIs, run count by status, and average
  fit score by status.
- The PBIX reads local CSV snapshots so it contains no Neon password or API key.
- A schema-validating exporter and manifest define the repeatable refresh path.
- The deployed `dashboard_runs_view` endpoint returned HTTP 200 with 15 run
  rows, and the saved PBIX was refreshed from that official snapshot.

## Container Verification

- A clean Docker image was built from `python:3.12-slim`.
- The container ran as `appuser` with UID 1000, not as the root administrator.
- Its `/health` endpoint returned HTTP 200.
- Docker reported the container as `healthy` using the built-in health check.

## Final Release Sync

Date: 2026-07-10

- Pull request `#2` was squash-merged as final commit `818d052`.
- All six PR checks passed before merge.
- Main-branch CI run `#18` completed successfully:
  `https://github.com/Zey-Z/account-intel-outreach/actions/runs/29070988596`.
- Test-gated deploy run `#10` completed successfully:
  `https://github.com/Zey-Z/account-intel-outreach/actions/runs/29070988586`.
- The live `/runtime/status` endpoint reported commit
  `818d052ad303de6e2a23d1ae1fe1dd1cc8971301`, CrewAI, and Tavily.
- The protected deep-health endpoint returned HTTP 200 against PostgreSQL with
  24.088 ms observed database latency.
- The Power BI artifact was refreshed from 15 deployed run rows and now shows
  the grounding rate as `100%` rather than the raw decimal `1.00`.

## Documentation Release Baseline

Date: 2026-07-10

- Pull request `#3` presented the completed system as an external-facing product
  story and was merged as commit `799894c`.
- All six pull-request checks passed before merge.
- The repository landing page now links directly to this verification record,
  the production-readiness explanation, the dashboard guide, and the updated
  learning walkthrough.
- This documentation change did not alter the verified workflow behavior
  recorded above.

## Remaining Operating Boundary

- Render's free/demo hosting and single-process in-memory rate limiter are not an
  enterprise high-availability setup.
- The metrics above are test-context results from a portfolio deployment.
