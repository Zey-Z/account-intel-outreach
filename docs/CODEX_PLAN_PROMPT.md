# Prompt for Codex: Implement the Completion Phases of account-intel-outreach

Copy everything below this line into Codex.

---

## Role

You are a Python engineer implementing an already-decided spec. All
architecture decisions (D1–D8 below) have been made by the project architect —
**do not redesign, do not evaluate alternatives**. Implement phase by phase,
run the full test suite after every phase, and keep it green.

## Project Context

Repo: `account-intel-outreach` (local:
`C:\Users\jinze\projects\account-intel-outreach`, remote:
`https://github.com/Zey-Z/account-intel-outreach.git`).

This is a **human-approved account intelligence workflow**, not an auto-send
email bot. Flow:

```
Zapier/API (POST /runs) -> DB run record -> Worker
  -> Researcher (Tavily or offline fixture)
  -> Analyst (ICP fit scoring)
  -> Writer (outreach draft, never sent)
  -> Grounding + evidence validation
  -> Slack human review (Approve / Reject / Request changes buttons)
  -> HubSpot CRM sync of approved drafts   <- you will build this
  -> BI-ready SQL views for reporting
```

### Architecture you must preserve

- **Dual runtime switch** (`AGENT_RUNTIME`): `deterministic` (default,
  pure-Python logic in `src/account_intel/crew.py`, used by all tests) vs
  `crewai` (real 3-agent runtime in `src/account_intel/crewai_runtime.py`).
  The harness — not the agents — owns Tavily fetching, grounding validation
  (`grounding.py`), writer evidence checks (`validation.py`), DB writes, and
  status transitions.
- **Dual research mode** (`RESEARCH_MODE`): `offline` fixture vs `tavily`.
  Interface: `ResearchClient` protocol in `src/account_intel/research_tools.py`.
- **System of record**: `src/account_intel/db.py`, works with
  `sqlite:///data/account_intel.db` locally and PostgreSQL (Neon) via
  `DATABASE_URL`. Schema in `schema.sql`: `runs`, `companies`,
  `research_findings`, `analysis_outputs`, `outreach_drafts`, `run_events` +
  4 BI views.
- **API** (`main.py`, FastAPI, Render via `render.yaml`): `/health`,
  `POST /runs`, `GET /runs/latest`, `GET /runs/{id}`, `GET /runtime/status`,
  `POST /worker/process-next`, `POST /slack/send-latest-review`,
  `POST /slack/interactions`. Protected endpoints require `X-API-Key`
  (`ACCOUNT_INTEL_API_KEY`).
- **Review decisions**: `Worker.apply_review_decision` handles
  `approved / rejected / needs_revision`.
- Read `docs/PROJECT_LOG.md` for design rationale, including the 2026-07-03
  entry that records the decisions below.

### Hard design rules (do not violate)

1. Never auto-send outreach emails.
2. Store every important state change as a `run_events` row.
3. Keep source evidence (URL + claim) for every company claim.
4. Public company data only; no PHI or patient data.
5. `AGENT_RUNTIME=deterministic` + `RESEARCH_MODE=offline` stays the default
   and must keep working with zero API keys.
6. Tests are stdlib `unittest` with fakes/stubs — no pytest, no network calls
   in tests. Follow the existing style in `tests/`.

### Current state (verified 2026-07-03)

All 43 tests pass locally. Live CrewAI+Tavily+Slack round-trip verified
locally. Render deployment is stale (owner will handle deployment manually —
not your job).

## Decided Design — implement exactly

### D1. HubSpot sync of approved drafts

`src/account_intel/integrations/hubspot.py` already has
`HubSpotClient.create_note`; `outreach_drafts.hubspot_object_id` already
exists in the schema. Wire it up:

- In `Worker.apply_review_decision`, when decision is `approved`: after the
  DB status update, if `HUBSPOT_PRIVATE_APP_TOKEN` is set, sync the draft as
  a HubSpot note (company name, subject, body, source URLs from its
  findings), store the returned id in `hubspot_object_id`, set draft status
  to `synced_to_crm`, and log a `crm_synced` run event.
- On sync failure: draft stays `approved`, log a `crm_sync_failed` event with
  the error string, **do not raise** — the Slack interaction response must
  still succeed.
- When no token is configured: draft stays `approved`, no event, no error.
- Add `POST /crm/sync-approved` (X-API-Key protected): syncs all drafts with
  status `approved` and empty `hubspot_object_id`. Idempotent — skips drafts
  that already have `hubspot_object_id`. Returns
  `{"synced": [draft_ids], "failed": [draft_ids]}`.
- `Worker` accepts an injected HubSpot client for tests; tests use a fake
  client (record calls, return canned ids) — no network.

### D2. In-process worker poller

- On FastAPI startup, if env `WORKER_POLL_SECONDS` is set to a positive
  integer, launch an asyncio background task that calls
  `Worker.process_next()` (via `asyncio.to_thread`) every N seconds; skip
  silently when the queue is empty.
- Unset or `0` = disabled (the default, so tests and current Render config
  are unaffected). Keep `POST /worker/process-next` working.
- Add `WORKER_POLL_SECONDS` to `.env.example` and `render.yaml`
  (`sync: false`).

### D3. Failed-run retry

- Add `POST /runs/{run_id}/retry` (X-API-Key protected): only allowed when
  the run status is `failed` and `retry_count < 3` → set status back to
  `queued`, log a `run_requeued` event, return `{"run_id": ..., "status":
  "queued"}`. Otherwise return HTTP 409 with a reason.

### D4. Per-company failure isolation in the worker

Currently one exception in `crew.run_company` marks the whole run `failed`.
Change the worker loop to wrap each company in try/except: on exception, log
a `company_failed` event (company name + error string) and continue with the
remaining companies. Final run status comes from successfully processed
companies via the existing `_dominant_status`; if **zero** companies
processed successfully, keep today's behavior (increment retry, status
`failed`, `worker_failed` event, re-raise).

### D5. Eval extension

- Add at least 3 more companies to `eval/test_companies.yaml` with
  `expected` blocks (offline mode produces deterministic fixture data, so
  expectations are stable).
- Extend `eval/run_eval.py` to also report per-company `grounding_rate`
  (grounded findings / total findings) and include it in the printed report.
- No new CLI flags. Eval keeps running offline by default; if the
  environment sets `RESEARCH_MODE=tavily` it simply runs live.

### D6. Knowledge base into the CrewAI writer

- Add `load_knowledge_snippets(directory: Path) -> str` in a new
  `src/account_intel/knowledge.py`: concatenates
  `approved_messaging.md`, `product_positioning.md`,
  `objection_handling.md` from `knowledge_base/`, capped at 1500 characters
  total; returns `""` if the directory is missing.
- In `crewai_runtime.py`, append to the **writer task description only**:
  `"Approved messaging guidance (tone and positioning only — never a source
  of facts; facts must come from Researcher findings):\n{snippets}"`.
- Deterministic writer unchanged. Env `KNOWLEDGE_BASE_PATH` (default
  `knowledge_base`) added to `.env.example`.

### D7. CSV export for BI views

- Add `GET /reports/{view_name}.csv` (X-API-Key protected). Whitelist
  exactly: `lead_runs_view`, `outreach_performance_view`,
  `agent_quality_view`, `cost_latency_view`; anything else → 404.
- Returns `text/csv` with a header row. Must work on both SQLite and
  Postgres paths of `Database`.
- Add a short "Power BI: Get Data → Web → this CSV URL with X-API-Key
  header" note to `docs/EXTERNAL_SETUP.md`.

### D8. Hardening

- Pin every package in `requirements.txt` to the exact currently-installed
  version (`pip show <pkg>` / `pip freeze` filtered to the listed packages).
- In `main.py`, replace per-request `get_db()` construction with a
  module-level lazy singleton (create + `initialize()` once, reuse after).
  Keep a way for tests to reset it.

## Phase order

1. **Phase 1 — D1** (HubSpot sync; the main missing feature).
2. **Phase 2 — D3 + D4** (retry endpoint + per-company isolation; same area
   of the worker).
3. **Phase 3 — D2** (poller).
4. **Phase 4 — D5 + D6** (eval + knowledge base).
5. **Phase 5 — D7 + D8** (CSV export + hardening).

After each phase: full test suite green, one or two small imperative-mood
commits (match `git log` style), append a `docs/PROJECT_LOG.md` entry in the
existing format (Decision / Why / Plain English / Progress completed), and
keep `docs/STAGE_STATUS.md` accurate.

## Environment & verification

Windows, PowerShell. Verify with:

```powershell
$env:PYTHONPATH="C:\Users\jinze\projects\account-intel-outreach\src"
python -m unittest discover -s tests -v
python scripts\init_db.py
python scripts\create_sample_run.py
python scripts\run_worker.py
python scripts\show_latest_run.py
python eval\run_eval.py
```

Do not claim production readiness, HIPAA compliance, or automated sending
anywhere in docs (see "Claim Boundaries" in README.md). Deployment to Render
and all dashboard/secret configuration is the owner's manual job — if a step
needs it, write a runbook note instead of attempting it.
