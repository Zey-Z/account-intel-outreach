# Classroom Walkthrough

This note explains the system as if you are building your first serious CS
project. The goal is not just to run code. The goal is to understand why each
piece exists.

## 1. The Problem

A business team has target companies. Before contacting them, someone needs to
answer three questions:

1. What is this company doing?
2. Is it a good fit for our product or service?
3. What should a human say next?

The system lets AI do the first draft of that work, but a human still approves
the final action.

## 2. Why We Do Not Start With Zapier

Zapier is an entry door, not the brain of the system. A multi-agent research run
can take minutes. Zapier is better at saying "a new company arrived" than at
running the whole AI workflow.

So the architecture is:

```text
Zapier -> FastAPI -> database queue -> worker -> agent flow -> database -> Slack review
```

This lets each layer have one job.

## 3. Why We Built Offline First

Live AI systems are noisy. Search APIs can fail. LLM outputs can change. Website
content can move.

For a first implementation, we use deterministic offline research fixtures. This
means the same input gives the same output every time. That lets us test the
state machine, database writes, validation, and reporting before adding live
Tavily and CrewAI calls.

## 4. The Core Data Model

- `runs`: one batch job.
- `companies`: the accounts inside that job.
- `research_findings`: source-backed claims.
- `analysis_outputs`: fit score and rationale.
- `outreach_drafts`: draft plus human review status.
- `run_events`: timeline, errors, latency, and token estimates.

Think of the database as the system's memory. The agents can be wrong or
unpredictable, but the workflow state must stay inspectable.

## 5. The Harness

The harness is the control layer around the agents:

- It decides status transitions.
- It validates evidence.
- It logs failures.
- It records review decisions.

This is the difference between a prompt demo and an agent workflow.

## 6. What To Run First

```powershell
$env:PYTHONPATH="C:\Users\jinze\projects\account-intel-outreach\src"
python scripts\init_db.py
python scripts\create_sample_run.py
python scripts\run_worker.py
python scripts\show_latest_run.py
```

After this, read the JSON report. Look for:

- final run status
- companies processed
- draft status
- event history
- evidence references

## 7. What Comes Next

After the offline system is clear, connect one external boundary at a time:

1. Real Tavily search/extract.
2. Real CrewAI Agent/Task objects.
3. FastAPI server.
4. Zapier webhook.
5. Slack approval.
6. HubSpot sync.
7. Power BI dashboard.

If something breaks, you will know which boundary caused it.
