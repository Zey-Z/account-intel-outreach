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
