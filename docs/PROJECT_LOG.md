# AI Account Intelligence Project Log

This log records important decisions, build progress, architecture notes, and why each technology choice exists.

## Current System Shape

The project is an AI account research workflow.

Simple flow:

```text
Zapier Table -> FastAPI -> PostgreSQL run record -> Worker -> Research / Analysis / Draft -> Status writeback
```

What this means:

- Zapier is the business entry point. A non-technical user can add a company row.
- FastAPI is the public door. It receives the request and creates a run.
- PostgreSQL is the memory. It stores run state, companies, findings, drafts, and events.
- The worker does the longer processing work.
- The AI layer prepares research, scoring, and outreach draft data.
- Humans still approve important outputs later through Slack.

## Important Design Rules

- Do not auto-send outreach emails.
- Store every important state change.
- Keep source evidence for company claims.
- Use public company data only.
- Keep offline test mode, even after adding real web research.
- Treat demo hosting as demo hosting, not production infrastructure.

## 2026-05-25 - Next Development Stage: Real Web Research

Decision:

Add a Tavily-backed research client before Slack, HubSpot, or full CrewAI runtime.

Why:

The workflow shell already works. Zapier can trigger the system, the API can create runs, the worker can process runs, and status can be written back. The biggest current gap is that research data is still offline fixture data. That is useful for teaching and tests, but it is not yet real account research.

Plain English:

The factory line works. Now we need to stop using practice material and start using real public web sources.

Technical choice:

Add `TavilyResearchClient` behind the existing `ResearchClient` interface.

Why this is a good architecture:

- The existing worker and crew code can stay mostly the same.
- Tests can continue using `OfflineResearchClient`.
- Real demo runs can use Tavily when `TAVILY_API_KEY` is present.
- This separates "where research comes from" from "how the workflow uses research."

Reference:

- Tavily Python SDK quickstart: https://docs.tavily.com/sdk/python/quick-start
- Tavily API introduction: https://docs.tavily.com/documentation/api-reference/introduction

Progress completed:

- Added tests for the new Tavily research boundary.
- Added `TavilyResearchClient`.
- Added `build_research_client`.
- Added `classify_source_type`.
- Added `RESEARCH_MODE=offline` to `.env.example`.
- Added `tavily-python>=0.7.24` to `requirements.txt`.
- Updated the worker so it can use offline mode or Tavily mode.
- Installed the Tavily Python SDK locally.
- Ran the full test suite: 26 tests passed.

Current limitation:

There is no local `.env` file yet, so no real Tavily API call was made today. The code is tested with a fake Tavily SDK, which proves our integration contract without spending API credits.

How to run real web research later:

```text
RESEARCH_MODE=tavily
TAVILY_API_KEY=<your Tavily key>
```

Then create a run and process it with the worker. The worker will use Tavily instead of offline fixture data.

## 2026-05-25 - Local `.env` and Tavily API Setup

Decision:

Use a local `.env` file for machine-specific settings and API keys.

Why:

Secrets should not live in code or GitHub. The repo keeps `.env.example` as the public template, while the real `.env` stays local and is ignored by git.

Plain English:

`.env.example` is the instruction sheet. `.env` is the private filled-out copy on this machine.

SDK explanation:

SDK means Software Development Kit. In this project, the Tavily SDK is the Python package `tavily-python`. It gives us `TavilyClient.search()` and `TavilyClient.extract()` so we do not need to manually build HTTP requests.

Progress completed:

- Added `account_intel.env.load_local_env`.
- Connected `.env` loading to `main.py` and local scripts.
- Added `python-dotenv` to requirements.
- Created local `.env` and confirmed git ignores it.
- Confirmed the Tavily key is present without printing it.
- Ran a live Tavily smoke test for Oscar Health.
- Fixed the Tavily query after discovering `site:hioscar.com` and long ICP signal queries returned zero results.
- Changed Tavily search to use a simple query plus domain variants such as `hioscar.com` and `www.hioscar.com`.
- Ran a local workflow smoke test using Tavily. Result: real source pages were stored and the run routed to `needs_human_research`.
- Fixed API tests so local `.env` API key settings do not leak into unit test expectations.
- Ran the full test suite: 27 tests passed.

Live smoke test result:

```text
Company: Oscar Health
Pages extracted: 4
Findings stored: 4
Final status: needs_human_research
Reason: real sources were found, but current simple scoring logic did not route the draft to ready review.
```

Architecture note:

This confirms the research layer can now use real public web sources. The next likely improvement is not more API setup; it is improving finding quality and reporting so the system can show source evidence more clearly.

## 2026-05-25 - Finding Quality Layer

Decision:

Improve `pages_to_candidate_findings` so it does not blindly use the first sentence from each web page.

Why:

Real web pages contain navigation text, phone numbers, page titles, legal footers, and marketing headers. If we send that raw text directly to the Analyst and Writer, the workflow may look like it is grounded, but the evidence will be low quality.

Plain English:

Tavily gives us the page. The finding quality layer chooses the useful sentence from the page.

Progress completed:

- Added a test showing that phone numbers and page headers should not become research claims.
- Added `select_research_claim`.
- Added candidate filtering for short/noisy text.
- Added simple scoring with business keywords such as healthcare, member, operations, support, clients, claims, and workflow.
- Ran a live Oscar Health workflow again.
- Ran the full test suite: 28 tests passed.

Live smoke test result:

```text
Company: Oscar Health
Findings stored: 4
Example cleaner finding: Helping healthcare clients drive improved efficiency, growth and superior engagement with their members and patients.
Final status: needs_human_research
```

Interpretation:

The research layer is now better. The next bottleneck is the Analyst logic. It still uses simple keyword scoring, so it may under-score a company even when the evidence is meaningful.

## 2026-05-25 - Analyst Scoring Calibration

Decision:

Improve the Analyst scoring logic before adding Slack or HubSpot.

Why:

The workflow can now collect real source-backed findings. The next risk is bad judgment: if the Analyst under-scores a strong company, good leads get stuck in `needs_human_research`; if it over-scores everything, the system looks unreliable.

Plain English:

Research answers: "What did we find?"

Analyst answers: "Does this matter for our ICP?"

Progress completed:

- Added tests for strong healthcare operations evidence.
- Added a test that normal public patient language should not automatically trigger a PHI risk flag.
- Improved scoring for member support, healthcare operations, technology platform, public hiring, and press release signals.
- Changed risk detection to focus on stronger clinical/PHI phrases like diagnosis, patient data, medical records, and PHI.
- Capped heuristic fit scores at 88 so the system does not claim fake-perfect certainty.
- Ran a live Oscar Health workflow after the change.
- Ran the full test suite: 30 tests passed.

Live smoke test result:

```text
Company: Oscar Health
Final status: sent_to_review
Fit score: 88
Confidence: 0.82
Review flag: ready_for_review
Pain point match: member support triage, healthcare operations workflow support
```

Interpretation:

The workflow now has a stronger research-to-analysis path. A real company with source-backed healthcare operations signals can move to human review, while the score remains calibrated rather than pretending to be perfect.

## 2026-05-25 - Human-Readable Run Report

Decision:

Expand `build_run_report` to include source findings and analysis outputs.

Why:

Slack review should not show only an AI-written draft. A human reviewer needs the evidence trail: what the AI claimed, where the claim came from, what score the Analyst gave, and why the draft is ready for review.

Plain English:

Before this change, the report said: "Here is the draft."

After this change, the report says: "Here is the draft, here is the score, and here are the sources behind it."

Progress completed:

- Added report test coverage for `finding_count` and `analysis_count`.
- Added `findings` to the run report.
- Added `analysis` to the run report.
- Decoded analysis risk flags from stored JSON.
- Verified the latest Tavily run report shows Oscar Health's source claims and URLs.
- Ran the full test suite: 30 tests passed.

Latest report check:

```text
Run status: sent_to_review
Finding count: 4
Analysis count: 1
Fit score: 88
Pain point match: member support triage, healthcare operations workflow support
```

Architecture note:

This report shape is the bridge between backend workflow and Slack human review. The next Slack message can be built from this report instead of manually querying many tables.

## 2026-05-25 - Slack Review Message Payload

Decision:

Build and test the Slack review message before wiring live Slack delivery.

Why:

Slack is the human approval surface. The message must show the draft, score, reason, and source evidence. If it only shows the draft, the reviewer is being asked to trust the AI without evidence.

Plain English:

Slack is the approval desk. The message is the case file.

Progress completed:

- Added `build_review_message_from_report`.
- Built Slack Block Kit payload from the run report.
- Included fit score, confidence, status, review flag, pain point match, buying trigger, recommended angle, source evidence, risk flags, subject, draft, and action buttons.
- Added Approve, Reject, and Request changes buttons.
- Added `SlackWebhookClient` as a small delivery boundary for incoming webhook posting.
- Tested the message builder and webhook sender with fake local data.
- Built a local Slack message from the latest Oscar Health report.
- Ran the full test suite: 32 tests passed.

Local Slack payload check:

```text
Text: Review outreach draft for Oscar Health
Block count: 8
Actions: approve_draft, reject_draft, request_changes
```

Architecture note:

This is not live Slack posting yet. It is the correct next step because message quality should be tested before external delivery. The next live step is creating a Slack app or incoming webhook and adding the webhook URL to local `.env`.

## 2026-05-25 - Server-Side Slack Review Sender

Decision:

Add a secured API endpoint that sends the latest review message from the same server/database that will receive Slack button clicks.

Why:

Sending from local SQLite works for a visual Slack test, but button clicks go to Render. If the Slack message uses a local draft ID and the button handler uses Render/Neon, the handler may not find the draft. The review message and button handler should use the same environment.

Plain English:

The desk that sends the approval card should be the same desk that receives the approval decision.

Progress completed:

- Added `POST /slack/send-latest-review`.
- Secured it with `X-API-Key`.
- The endpoint builds the latest run report, creates the Slack review payload, and sends it to `SLACK_WEBHOOK_URL`.
- Added `SLACK_WEBHOOK_URL` to `.env.example`, `render.yaml`, and deployment docs.
- Added test coverage for server-side Slack sending.
- Ran the full test suite: 33 tests passed.

Next manual setup:

Configure these variables in Render:

```text
SLACK_WEBHOOK_URL=<Slack incoming webhook URL>
SLACK_SIGNING_SECRET=<Slack app signing secret>
```

Then use:

```text
POST https://<render-url>/slack/send-latest-review
Header: X-API-Key: <ACCOUNT_INTEL_API_KEY>
```

## 2026-05-25 - Slack Button Feedback

Decision:

Return a visible ephemeral confirmation after Slack button clicks.

Why:

The backend successfully updated draft status, but Slack did not visibly change. That confused the reviewer. A human approval workflow should show feedback when a decision is recorded.

Plain English:

The button was working, but Slack was not saying "got it." Now it should.

Progress completed:

- Added a test for Slack interaction confirmation response.
- Updated `/slack/interactions` to return `response_type=ephemeral`.
- Kept `replace_original=False` so the original review message stays visible.
- Verified local tests: 34 tests passed.

Observed live state before this fix:

```text
Slack click reached Render.
Draft status changed in Neon.
Slack UI did not visibly confirm the click.
```

## 2026-05-26 - Slack Original Message UI Update

Decision:

After a reviewer clicks Approve, Reject, or Request changes, replace the original Slack review card with a read-only version.

Why:

The database status update was already working, but the reviewer still saw the old buttons in Slack. That makes the workflow feel broken because the human cannot tell whether the decision was accepted.

Plain English:

Slack was like a waiter who wrote down your order but never said "got it." Now the card changes after the click, so the reviewer can see the decision was recorded.

Progress completed:

- Added a regression test for Slack original-message replacement.
- Added a Slack message builder that removes the action buttons after a decision.
- Updated `/slack/interactions` to call Slack's `response_url` and replace the original review card.

Architecture note:

Slack's `response_url` is a temporary callback URL included in an interaction payload. It lets the app update the specific message where the button was clicked. This keeps the human review surface in sync with the database state.

## 2026-05-26 - Slack Direct Interaction Response

Decision:

Return the replacement Slack message directly from `/slack/interactions` instead of only posting an update to `response_url`.

Why:

Live testing showed the database changed to `approved`, but the Slack card still did not visually change. That proved the button handler worked and the remaining issue was UI feedback. Directly returning the replacement message is simpler: Slack sends the button click, and the API immediately answers with the new version of the card.

Plain English:

Instead of saying "I will update the card later," the API now answers Slack with "show this updated card right now."

Progress completed:

- Updated the Slack interaction test to require `replace_original=true` in the direct response.
- Removed the extra response-url POST from the button handler.
- Kept the database status update before the UI response.
- Verified local tests: 34 tests passed.

## 2026-05-26 - Slack Message Update Strategy

Decision:

Use a two-layer Slack update strategy after review buttons are clicked:

1. Prefer Slack Web API `chat.update` when `SLACK_BOT_TOKEN`, channel ID, and message timestamp are available.
2. Fall back to Slack `response_url` replacement when bot-token update is unavailable.

Why:

Live testing proved the database update worked, but the Slack card did not visually change. Slack's current docs describe `response_url` as the message-response path for interactions and `chat.update` as the normal API path for updating non-ephemeral messages. The system now supports both and records which path was used.

Plain English:

Before, we knew the kitchen got the order, but the waiter never updated the table. Now the system tries the strongest update method first, has a backup method, and writes down what happened.

Progress completed:

- Added `SlackWebApiClient` for `chat.update`.
- Added response-url fallback.
- Added `slack_review_message_update` event logging.
- Added tests for both Slack update paths.
- Verified local tests: 35 tests passed.

## 2026-05-26 - Real CrewAI Runtime Boundary

Decision:

Add a real CrewAI runtime behind the existing `AccountIntelligenceCrew.run_company()` contract, selected by `AGENT_RUNTIME=crewai`.

Why:

The system already had a reliable business workflow shell: API, worker, database, Tavily research boundary, validation, and Slack review. The next important capability gap was that the Researcher / Analyst / Writer roles were still deterministic Python logic rather than real CrewAI Agent / Task / Crew orchestration.

Plain English:

We changed the brain without changing the body. The worker, database, Slack review, Zapier entry, and reporting still see the same output shape, but the internal reasoning can now be handled by a real three-agent CrewAI crew.

Progress completed:

- Added `CrewAIAccountRuntime`.
- Added CrewAI Pydantic output schemas for Researcher, Analyst, and Writer tasks.
- Added three CrewAI agents: `Senior Account Researcher`, `GTM Fit Strategist`, and `Personalized Outreach Copywriter`.
- Added sequential CrewAI task orchestration with `Process.sequential`.
- Kept Tavily/page fetching and grounding checks in the harness for source control.
- Added `AGENT_RUNTIME`, `CREWAI_LLM`, and `OPENAI_API_KEY` configuration documentation.

Architecture note:

The runtime switch is intentionally conservative. `AGENT_RUNTIME=deterministic` remains the default for tests and low-cost demos. `AGENT_RUNTIME=crewai` enables the real CrewAI path after LLM credentials are configured.

## 2026-05-26 - Stable Source Seeds and Review Routing

Decision:

Add a curated source registry for stable official company pages, and route grounded-fit accounts to Slack review even when the draft itself is marked `needs_human_review`.

Why:

The first live CrewAI smoke test produced grounded findings and a valid fit score, but routed to `needs_human_research` because the writer confidence flag was conservative. That mixed up two different human actions:

- `needs_human_research` means the system lacks enough source evidence.
- `needs_human_review` means the draft needs a human reviewer before approval.

Plain English:

If the research folder has enough evidence, send the case to the review desk. The reviewer can still decide the draft needs edits.

Progress completed:

- Added `source_registry.yaml` with stable Oscar Health source seeds.
- Updated Tavily research to extract registry seed URLs before search-result URLs.
- Kept facts live: the registry stores source URLs and field hints, not claims.
- Updated status routing so grounded accounts with `fit_score >= 60` enter Slack review.
- Clarified the Writer prompt: `needs_human_review` means "send to Slack for a person," not "block the account."
- Added regression tests for source seeding and review routing.

Architecture note:

This is a better pattern than hardcoding company facts. The system hardcodes where to look and what fields matter, while Tavily and CrewAI still read current public pages at runtime.

## 2026-05-29 - Local Live Smoke Test and Script Entry Hardening

Decision:

Use local latest code to run a real CrewAI/Tavily/OpenAI smoke test against the shared database when Render is still on an old deployment.

Why:

Render's dashboard requires account login, and `/runtime/status` showed the hosted service was still running an old commit. Local live testing let us verify the actual workflow logic without waiting on a manual cloud deploy.

Plain English:

The cloud copy was behind, so we tested the newest kitchen locally with the real ingredients: Neon, Tavily, OpenAI, and Slack. That tells us whether the recipe works before asking Render to serve it.

Progress completed:

- Installed missing local dependencies from `requirements.txt`, including CrewAI.
- Fixed utility scripts so they can be run directly from the repo root without manually setting `PYTHONPATH`.
- Added a regression test that imports each utility script without `PYTHONPATH`.
- Ran a real Oscar Health workflow with `AGENT_RUNTIME=crewai` and `RESEARCH_MODE=tavily`.
- Verified the result now reaches `sent_to_review` with 5 grounded findings, 1 analysis output, and 1 outreach draft.
- Sent the reviewed run to Slack through `scripts/send_latest_slack_review.py`.
- Confirmed Render is still deployed at old commit `4c772df`, while GitHub latest is `ca26b7c`.

Architecture note:

This confirms the source-seeding and review-routing logic works in the current code. The remaining gap is deployment state, not workflow logic.

## 2026-07-03 - Completion Phase Design Decisions

Decision:

Fix the design for the remaining work as eight decisions (D1-D8) and delegate implementation to a coding agent working from `docs/CODEX_PLAN_PROMPT.md`.

Why:

An architecture audit found the workflow core healthy (43 tests passing, live CrewAI/Tavily/Slack round-trip verified) but with one dead-end feature and several operational gaps. Deciding the design up front keeps the coding agent from redesigning working boundaries.

Plain English:

The blueprint is finished; a builder now follows it room by room.

Decisions:

- D1: Sync approved drafts to HubSpot as notes inside `apply_review_decision`, with a `synced_to_crm` status, `crm_synced`/`crm_sync_failed` events, an idempotent `POST /crm/sync-approved` catch-up endpoint, and graceful no-token behavior. Sync failure never breaks the Slack response.
- D2: Optional in-process worker poller controlled by `WORKER_POLL_SECONDS` (default off), instead of a paid Render cron service.
- D3: `POST /runs/{run_id}/retry` requeues failed runs, capped at 3 attempts.
- D4: Per-company failure isolation in the worker loop; a run only fails when every company fails.
- D5: Eval gains 3+ companies and per-company grounding rate, still offline by default.
- D6: `knowledge_base/` messaging docs feed the CrewAI writer prompt as tone/positioning guidance only, capped at 1500 characters; facts still come only from grounded findings.
- D7: BI views exposed as API-key-protected CSV endpoints for Power BI, avoiding a database connector dependency.
- D8: Pin dependency versions; cache the Database instance in `main.py`.

Out of scope for the coding agent:

Render redeploy, env var flips, and all dashboard/secret setup stay manual owner steps.

## 2026-07-03 - Approved Drafts Sync to HubSpot Notes

Decision:

Wire approved Slack review decisions to HubSpot note creation, and add a catch-up API for approved drafts that were not synced yet.

Why:

The workflow could already create a reviewable draft and record an approval, but the approved output stopped inside the local system. A real business workflow needs a controlled handoff into the team's CRM after a human decision.

Plain English:

Slack is the approval desk. HubSpot is the filing cabinet. Once a reviewer approves a draft, the system files the approved draft and its source links into HubSpot as a note. If the filing cabinet is unavailable, the approval still stands and the error is written down for follow-up.

Progress completed:

- `Worker.apply_review_decision()` now attempts HubSpot sync after an `approved` decision when a HubSpot client/token is configured.
- Successful sync stores `hubspot_object_id`, moves the draft to `synced_to_crm`, and logs a `crm_synced` event.
- Failed sync leaves the draft `approved`, logs `crm_sync_failed`, and does not break the Slack interaction.
- Added idempotent `POST /crm/sync-approved` for approved drafts that still need CRM sync.
- Added tests using a fake HubSpot client, with no network calls.

## 2026-07-03 - Retry and Company-Level Failure Isolation

Decision:

Add a retry endpoint for failed runs and isolate worker errors at the company level.

Why:

One failing company should not destroy the whole batch. At the same time, a run that truly fails should have a controlled way to return to the queue instead of requiring manual database edits.

Plain English:

If one folder in a stack is messy, keep processing the other folders and mark the messy one for follow-up. If the whole stack fails, put the stack back on the work tray only a limited number of times.

Progress completed:

- Added `POST /runs/{run_id}/retry`, protected by `X-API-Key`.
- Failed runs can be requeued while `retry_count < 3`; invalid retries return HTTP 409.
- Added `run_requeued` event logging.
- Worker now logs `company_failed` and continues when one company fails.
- A run still becomes `failed` when every company fails.
- Added tests for partial failure, total failure, retry success, and retry rejection.

## 2026-07-03 - Optional In-Process Worker Poller

Decision:

Add an optional FastAPI startup poller controlled by `WORKER_POLL_SECONDS`.

Why:

The API already had a manual worker endpoint, but a demo or internal pilot should be able to process queued runs without someone pressing `/worker/process-next` each time. The poller stays off by default so tests and current deployments do not change behavior unless explicitly configured.

Plain English:

The service can now check its own inbox every few seconds. If there is a queued run, it processes it. If the inbox is empty, it quietly waits until the next check.

Progress completed:

- Added `worker_poll_once()` and `worker_poll_loop()` in `main.py`.
- Added FastAPI startup hook `start_worker_poller()`.
- `WORKER_POLL_SECONDS=0` or unset keeps the poller disabled.
- Added `WORKER_POLL_SECONDS` to `.env.example` and `render.yaml`.
- Added tests for disabled startup, enabled startup, and one poll iteration.

Architecture note:

This is not a production queue. It is a lightweight demo/internal-pilot runner. A production queue would still need atomic job claiming, worker supervision, backoff, and concurrency control.

## 2026-07-03 - Eval Grounding Rates and Writer Knowledge Guidance

Decision:

Extend the offline eval set and feed lightweight approved messaging guidance into only the CrewAI Writer task.

Why:

The eval report needed a clearer quality signal than pass/fail, and the real CrewAI writer needed reusable positioning guidance without letting internal playbooks become target-company facts.

Plain English:

The test bench now has more sample companies and reports how much of each company's output is backed by sources. The writer also gets a short style card, like "say this kind of thing, avoid that kind of claim," but it still must get facts from research evidence.

Progress completed:

- Expanded `eval/test_companies.yaml` from 3 to 6 companies.
- Added per-company `grounding_rate` to eval actuals and printed reports.
- Added `src/account_intel/knowledge.py` for capped knowledge snippet loading.
- CrewAI Writer task now appends approved messaging guidance from `KNOWLEDGE_BASE_PATH`.
- Deterministic runtime remains unchanged.
- Added tests for knowledge loading, writer prompt guidance, and eval grounding rates.

## 2026-07-03 - CSV Reporting Endpoint and Runtime Hardening

Decision:

Expose BI-ready views as API-key-protected CSV endpoints, reuse a lazy database singleton in `main.py`, and pin Python dependencies to exact installed versions.

Why:

Power BI should be able to read reporting views without direct database access, and the API should not recreate the database wrapper for every request. Exact dependency pins also make local, Render, and reviewer environments more predictable.

Plain English:

The reporting layer now has a clean export window. Power BI can ask the service for a CSV report, the service checks the API key, then returns only one of the approved report views. The API also keeps one database handle ready instead of rebuilding it over and over.

Progress completed:

- Added `GET /reports/{view_name}.csv` with a strict 4-view whitelist.
- CSV responses include header rows, even when a view has no data.
- Added `reset_db_singleton()` so tests can reset the lazy database instance.
- Pinned all packages in `requirements.txt` to currently installed versions.
- Documented Power BI Web CSV setup with `X-API-Key`.
- Added tests for CSV export, whitelist rejection, and database singleton reuse.

## 2026-07-03 - HubSpot Note Timestamp Requirement

Decision:

Add `hs_timestamp` to every HubSpot note payload.

Why:

Live approval testing showed Slack review decisions were recorded correctly, but HubSpot note creation returned HTTP 400. HubSpot requires a timestamp for notes so the CRM can place the note on the activity timeline.

Plain English:

HubSpot needs both the note text and a clock time. Without the clock time, it knows what we want to save, but not where to place it in the company's history.

Progress completed:

- Reproduced the live failure after Slack approval: draft moved to `approved`, but CRM sync logged `crm_sync_failed`.
- Added a regression test requiring `hs_timestamp` in HubSpot note payloads.
- Added millisecond timestamp generation to `HubSpotClient.create_note_payload()`.
- Verified the targeted test and the full test suite pass locally.

## 2026-07-03 - CRM Sync Evidence in Run Reports

Decision:

Expose review and HubSpot sync fields directly in `build_run_report()`.

Why:

The system already stored CRM sync results, but demo viewers had to inspect low-level event logs to see the HubSpot note ID. The run report should show the business outcome directly.

Plain English:

The report is the dashboard window. If the note reached HubSpot, the window should say so clearly instead of making someone dig through the engine room.

Progress completed:

- Added draft body, reviewer, review timestamp, revision fields, and `hubspot_object_id` to report drafts.
- Added `crm_synced_count` to the report summary.
- Added a regression test that simulates review approval and HubSpot sync, then verifies the report shows the CRM evidence.

## 2026-07-06 - GitHub Actions CI Gate

Decision:

Add a GitHub Actions CI workflow that runs the full offline unit test suite on every push and pull request to `main`.

Why:

The project now has enough moving parts that manual local testing is not enough. CI gives the repo a repeatable quality gate: code can be checked in, but the project record shows whether the test suite still passes without any private API keys.

Plain English:

CI is the automatic test checkpoint. Every time code is pushed, GitHub opens the hood, installs the project, and runs the tests before anyone trusts the change.

Progress completed:

- Added `.github/workflows/ci.yml`.
- CI uses the Python version in `.python-version`.
- CI installs `requirements.txt`, sets `PYTHONPATH=src`, and runs `python -m unittest discover -s tests -v`.
- Added a CI badge to `README.md`.

## 2026-07-06 - Test-Gated Deploy and Versioned Migrations

Decision:

Add a GitHub Actions deploy workflow gated by tests, and replace one-shot schema initialization with versioned database migrations.

Why:

Deploying directly after a push is risky if tests are red. Updating database structure without a migration history is also risky because future changes become hard to reason about and hard to replay. A production-readiness story needs both a deploy gate and a database upgrade path.

Plain English:

The deploy workflow is a locked door: tests must pass before Render can be asked to redeploy. The migration table is the database's checklist: it remembers which schema updates have already been applied.

Progress completed:

- Added `.github/workflows/deploy.yml` with a test job and a deploy job that depends on it.
- Deploy uses `RENDER_DEPLOY_HOOK_URL` and fails loudly if the secret is missing.
- Added `migrations/0001_init.sql` with SQLite and Postgres schema sections.
- Added `schema_migrations` tracking through `Database.initialize()`.
- Kept `schema.sql` as a compatibility note pointing to `migrations/`.
- Added tests proving migrations are idempotent and applied in filename order.
- Documented Render deploy hook setup and migration usage in `docs/DEPLOY_RENDER_NEON.md`.

## 2026-07-06 - Request Tracing, Rate Limiting, and Deep Health

Decision:

Add structured request logs, a per-request trace header, demo-safe rate limiting, and a protected deep health check.

Why:

Once a workflow is deployed, the next question is not only "does it run?" but "can we see what happened when it fails or gets noisy traffic?" Request tracing gives each API call an ID, rate limiting reduces accidental or abusive repeated calls, and deep health checks whether the database path is actually reachable.

Plain English:

The basic `/health` endpoint says the front door opens. The deep health check walks inside and verifies the filing cabinet is still reachable. The request ID is the claim ticket for each visit, and rate limiting is the front desk rule that stops one visitor from repeatedly pressing the button too fast.

Progress completed:

- Added FastAPI middleware that logs one JSON line per request with method, path, status code, latency, and request ID.
- Added `X-Request-Id` to API responses.
- Added `LOG_LEVEL` configuration for server logging.
- Replaced the worker poller's bare `print()` with structured logger calls.
- Added worker logger calls for company failures, worker failures, CRM sync success, and CRM sync failure.
- Added a single-instance sliding-window rate limiter on `POST /runs` and `POST /worker/process-next`.
- Added `GET /health/deep`, protected by `X-API-Key`, with database latency and degraded-mode reporting.
- Added tests for request logging, rate limiting, and degraded deep health behavior.

## 2026-07-06 - Docker Path and Production Readiness Writeup

Decision:

Add an optional Docker container path and a plain-language production readiness document.

Why:

The live demo still runs on Render's Python runtime, but a production-minded project should show that the app can also be packaged in a standard container. The readiness document makes the engineering boundary explicit: what is hardened, what is demo-grade, and what should not be overclaimed.

Plain English:

Docker is the moving box for the app. The production readiness document is the inspection report: it says which safety checks exist and which parts are still lightweight.

Progress completed:

- Added a root `Dockerfile` using Python 3.12 slim and `uvicorn main:app`.
- Added `.dockerignore` so local secrets, Git metadata, and local database files are not copied into the image.
- Added optional Docker build/run instructions to `docs/DEPLOY_RENDER_NEON.md`.
- Added `docs/PRODUCTION_READINESS.md` covering CI/CD, migrations, request tracing, rate limiting, deep health, containerization, and known limitations.
- Added `LOG_LEVEL` and `RATE_LIMIT_PER_MINUTE` to environment templates.
- Updated `README.md` with a Production Deployment section while keeping claim boundaries intact.
- Added tests that guard the Docker artifacts and production readiness document.

## 2026-07-09 - Automated Deploy Hook and Atomic Worker Claiming

Decision:

Connect GitHub's test-gated deploy workflow to Render and make queue pickup an
atomic database operation.

Why:

The tests were green, but GitHub could not trigger Render because the encrypted
deploy-hook secret was missing. The worker also selected a queued run before
changing its status, which meant two workers could select the same run at the
same time.

Plain English:

GitHub now has the private doorbell for Render. The worker queue also works like
a sign-out desk: only one worker can take a folder, even if two ask at once.

Progress completed:

- Stored Render's Deploy Hook as the GitHub Actions secret
  `RENDER_DEPLOY_HOOK_URL` and re-ran the failed deploy workflow successfully.
- Added `Database.claim_next_queued_run()` with SQLite and Postgres locking.
- Stored a `run_claimed` event in the same transaction as the status change.
- Added query indexes for queue, company, finding, draft, and event lookups.
- Added a two-worker concurrency regression test.
- Updated official GitHub Actions to Node 24-compatible major versions.
- Completed HubSpot Company lookup/create and associated approved Notes with the
  correct Company record using HubSpot's default Note-to-Company relationship.
- Added bounded retry handling for temporary HubSpot rate-limit and server
  errors, while keeping failed syncs in the existing catch-up workflow.
- Added API validation for company names and ICP profile keys.
- Moved worker setup inside failure handling so malformed queued runs become
  visible `failed` runs with retry counts and events instead of getting stuck.
- Built the Docker image from a clean Python base and started a real container;
  `/health` returned HTTP 200.
- Removed the unused `crewai-tools` top-level dependency.
- Hardened the Docker runtime with an unprivileged user and built-in health
  check.

## 2026-07-09 - Dated Live Verification Record

Decision:

Keep a dated, evidence-based record of the exact CI, cloud, workflow, and
container checks that were completed.

Why:

A portfolio project should distinguish implemented code from behavior that was
actually observed in the deployed environment. This also keeps test-context
metrics from turning into unsupported production claims later.

Plain English:

This is the project's inspection sticker. It lists what was tested, when it was
tested, and what still needs a human decision.

Progress completed:

- Added `docs/LIVE_VERIFICATION.md` with GitHub Actions run evidence.
- Recorded live Render health, runtime, invalid-input, and Neon-backed workflow
  checks.
- Recorded the Oscar Health smoke run, its grounded findings, review route, and
  zero-retry result.
- Recorded Docker user, endpoint, and built-in health-check evidence.
- Kept the pending human Slack decision and Power BI artifact explicit.
