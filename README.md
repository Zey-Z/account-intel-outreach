# AI Account Intelligence & Outreach Ops System

[![CI](https://github.com/Zey-Z/account-intel-outreach/actions/workflows/ci.yml/badge.svg)](https://github.com/Zey-Z/account-intel-outreach/actions/workflows/ci.yml)

Portfolio-grade multi-agent workflow for account research, ICP fit scoring,
source-grounded outreach drafting, human review, and reporting.

## What This Builds

This is not an auto-send email bot. It is a human-approved account intelligence
workflow:

1. A target company enters the system.
2. Researcher gathers public source evidence.
3. Analyst scores fit against a configurable ICP.
4. Writer drafts outreach without sending it.
5. Validation checks evidence and confidence.
6. A human reviews before anything can sync to CRM.

## Local Quickstart

```powershell
$env:PYTHONPATH="C:\Users\jinze\projects\account-intel-outreach\src"
python scripts\init_db.py
python scripts\create_sample_run.py
python scripts\run_worker.py
python scripts\show_latest_run.py
python eval\run_eval.py
```

Run tests:

```powershell
$env:PYTHONPATH="C:\Users\jinze\projects\account-intel-outreach\src"
python -m unittest discover -s tests -v
```

## Zapier Entry Security

Public workflow endpoints are protected by an optional API key. Set
`ACCOUNT_INTEL_API_KEY` in Render before connecting Zapier. When this value is
set, Zapier must send this header on every API call:

```text
X-API-Key: your-secret-value
```

Protected endpoints:

- `POST /runs`
- `GET /runs/latest`
- `GET /runs/{run_id}`
- `POST /worker/process-next`

`GET /health` stays public so Render can check whether the service is alive.

## Current Implementation Status

Implemented:

- ICP configuration layer.
- Offline deterministic Researcher fixture.
- Stable source registry for official source seeding.
- Real CrewAI Agent/Task/Crew runtime switch via `AGENT_RUNTIME=crewai`.
- Grounding validation.
- Analyst scoring.
- Writer evidence check.
- SQLite-backed system of record with Postgres-shaped tables.
- Worker that processes queued runs.
- FastAPI endpoint definitions.
- Live Slack human-review workflow.
- Approved-only HubSpot note sync path.
- Retry endpoint and company-level failure isolation.
- Optional in-process worker poller for demo/internal processing.
- Eval runner and BI-ready views.
- API-key-protected CSV reporting endpoints.
- Human-readable run report script.
- GitHub Actions CI that runs the offline unit test suite without secrets.
- GitHub Actions deploy workflow that triggers Render only after tests pass.
- Versioned database migrations with `schema_migrations` tracking.

Next manual setup:

- Turn on real CrewAI runtime in Render after setting LLM credentials.
- Build Power BI dashboard from the database views.
- Add the `RENDER_DEPLOY_HOOK_URL` GitHub secret if automatic deploys are not
  configured yet.

Start with [docs/CLASSROOM_WALKTHROUGH.md](docs/CLASSROOM_WALKTHROUGH.md) if
you are learning the system from scratch. Use
[docs/NEXT_STAGE_REAL_CREWAI_TAVILY.md](docs/NEXT_STAGE_REAL_CREWAI_TAVILY.md)
when you are ready to replace the offline fixture with live CrewAI and Tavily.

## Claim Boundaries

Safe claim after full setup:

> Built a CrewAI-based account intelligence workflow that researches healthcare
> and insurance target accounts, scores ICP fit using configurable profiles,
> drafts source-grounded outreach, routes drafts through human approval, stores
> run state in PostgreSQL-shaped tables, syncs approved drafts to HubSpot notes,
> and exposes BI-ready reporting views and CSV exports.

Do not claim production rollout, HIPAA compliance, clinical validation, patient
impact, or automated email sending.
