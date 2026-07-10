# Classroom Walkthrough

This guide explains the completed system as if you are building your first
serious software project. The goal is not to memorize framework names. The goal
is to understand what job each part performs and why the boundaries matter.

## 1. The Business Job

A B2B team has a list of target companies. Before a person contacts one of
them, the team needs to answer three questions:

1. What is this company doing, based on public evidence?
2. Does it match the team's ideal customer profile (ICP)?
3. What is a reasonable first message for a human to review?

This system prepares those answers. It never sends an email automatically.

Think of it as an AI research desk with a human approval counter. The AI
prepares the folder; a person decides whether the folder moves forward.

## 2. One Run From Start to Finish

```text
Zapier or API
  -> FastAPI creates a run
  -> PostgreSQL stores it as queued
  -> Worker claims the run
  -> Researcher gathers public evidence
  -> Analyst scores ICP fit
  -> Writer drafts from accepted evidence
  -> Harness validates the result
  -> Slack asks a human to approve, reject, or revise
  -> Approved work becomes a HubSpot note
  -> Power BI reports workflow and quality metrics
```

The important idea is separation of responsibility. Each layer has one main
job, so a failure can be located instead of becoming one large mystery.

## 3. Why Zapier Is the Door, Not the Brain

Zapier gives a business user a familiar, spreadsheet-like starting point. A new
company row can call `POST /runs` without asking the user to open a terminal.

The full AI run can take longer than a normal web request. FastAPI therefore
accepts the request, creates a tracking ID, and returns quickly. The worker does
the longer job separately.

Plain English: the front desk gives you a claim ticket; the back office prepares
the file.

## 4. Why There Are Two Runtime Modes

The repository supports two agent modes and two research modes:

| Setting | Test/default mode | Live mode |
|---|---|---|
| `AGENT_RUNTIME` | `deterministic` | `crewai` |
| `RESEARCH_MODE` | `offline` | `tavily` |

Deterministic + offline mode gives the same answer every time and needs no API
keys. That is why 82 automated tests can run safely in GitHub Actions.

CrewAI + Tavily mode is the deployed demonstration. It uses three real Agent /
Task roles and current public web research.

Offline data is therefore a test instrument, not the final product. A flight
simulator does not mean the airplane is fake; it means risky behavior can be
tested without taking off.

## 5. What the Three Agents Do

### Researcher

Receives a company, domain, and ICP profile. Tavily searches and extracts
public pages. Findings retain the claim, URL, source type, retrieval time, and
grounding result.

### Analyst

Uses accepted findings and the selected ICP to produce a fit score, rationale,
buying trigger, risks, recommended angle, and confidence.

### Writer

Creates a draft from the accepted evidence. It does not send anything. Evidence
references let the validator check whether the draft introduced a new fact.

CrewAI coordinates these reasoning roles. It does not own final workflow state,
database writes, approval decisions, or CRM sync.

## 6. What the Harness Does

The harness is ordinary Python code around the agents. It:

- checks structured output and score ranges;
- rejects unsupported findings;
- checks draft facts against accepted evidence;
- controls status transitions;
- writes results and events to PostgreSQL;
- retries bounded external failures;
- routes uncertain work to a person.

This is the main difference between a prompt demo and a controlled AI workflow.
The agents propose; the harness verifies and operates.

## 7. Why PostgreSQL Matters

The database is the system of record. Six core tables divide the information:

- `runs`: one workflow request and its current status;
- `companies`: target accounts inside the run;
- `research_findings`: claims and source evidence;
- `analysis_outputs`: fit score and rationale;
- `outreach_drafts`: draft, confidence, and review decision;
- `run_events`: the chronological audit trail.

The worker changes a queued run to researching in one atomic database action.
This prevents two workers from processing the same run at the same time.

Plain English: two employees may reach for the same folder, but only one can
sign it out.

## 8. Why Slack Comes Before HubSpot

Slack is part of the control system, not just a notification channel. A reviewer
can approve, reject, or request one revision. Slack requests are verified with
the app signing secret before the database state changes.

Only an approved draft can be synced to HubSpot. The CRM client finds or creates
the company and files the approved draft as an associated Note with source
links. Rejected drafts never enter the CRM.

This design keeps human accountability at the business decision point.

## 9. How Power BI Receives Safe Data

PostgreSQL views summarize workflow, quality, review, cost, and latency data.
Protected API endpoints export two validated CSV files. Power BI reads the local
snapshot, not the Neon password or API key.

The dashboard is a management surface. It answers questions such as:

- How many runs were processed?
- How often did evidence pass grounding?
- How much work required human review?
- Where did failures or delays occur?

## 10. What Makes the Deployment More Than a Local Demo

- GitHub Actions runs Ruff, 82 unit tests, and a Docker image build.
- The Render deploy hook runs only after its test gate passes.
- Database migrations apply in version order.
- Requests receive an `X-Request-Id` for log tracing.
- Write endpoints have a demo-scale rate limiter.
- `/health/deep` checks real database reachability.
- Docker provides a portable, non-root container path.

These controls make the portfolio deployment observable and repeatable. Render
free hosting, an in-process worker, and an in-memory rate limiter still keep it
below an enterprise high-availability deployment.

## 11. A Good Learning Order

Do not read the repository from top to bottom. Follow one run:

1. Read `POST /runs` in `main.py` to see intake.
2. Read `Worker.process_next()` to see orchestration.
3. Read `crewai_runtime.py` to see the three agent tasks.
4. Read `grounding.py` and `validation.py` to see the safety checks.
5. Read `db.py` and `migrations/` to see state and history.
6. Read `integrations/slack.py` and `integrations/hubspot.py` to see human and CRM boundaries.
7. Read `powerbi/README.md` to see the reporting contract.

Then run the zero-key local path from the root README. Inspect the resulting run
report and answer: what was the input, what state changed, what evidence was
stored, and why did the draft take its final route?

## 12. The One-Sentence Architecture Lesson

Use AI for uncertain reasoning, deterministic code for rules, a database for
memory, a worker for long-running execution, and a person for consequential
decisions.
