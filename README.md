# AI Account Intelligence & Outreach Ops System

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

## Current Implementation Status

Implemented:

- ICP configuration layer.
- Offline deterministic Researcher fixture.
- Grounding validation.
- Analyst scoring.
- Writer evidence check.
- SQLite-backed system of record with Postgres-shaped tables.
- Worker that processes queued runs.
- FastAPI endpoint definitions.
- Slack and HubSpot integration boundaries.
- Eval runner and BI-ready views.
- Human-readable run report script.

Next manual setup:

- Install FastAPI/Uvicorn dependencies for API serving.
- Add real Tavily-backed research client.
- Configure Slack app and Zapier trigger.
- Connect HubSpot private app.
- Build Power BI dashboard from the database views.

Start with [docs/CLASSROOM_WALKTHROUGH.md](docs/CLASSROOM_WALKTHROUGH.md) if
you are learning the system from scratch. Use
[docs/NEXT_STAGE_REAL_CREWAI_TAVILY.md](docs/NEXT_STAGE_REAL_CREWAI_TAVILY.md)
when you are ready to replace the offline fixture with live CrewAI and Tavily.

## Claim Boundaries

Safe claim after full setup:

> Built a CrewAI-style account intelligence workflow that researches healthcare
> and insurance target accounts, scores ICP fit using configurable profiles,
> drafts source-grounded outreach, routes drafts through human approval, stores
> run state in PostgreSQL-shaped tables, and exposes BI-ready reporting views.

Do not claim production rollout, HIPAA compliance, clinical validation, patient
impact, or automated email sending.
