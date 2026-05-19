# Teaching Notes

This project is built in layers so a beginner can debug one system boundary at a
time.

## Layer 1: Agent Brain

The agent brain is the Researcher -> Analyst -> Writer flow. It answers:

- Can the system gather evidence?
- Can it score fit against an ICP?
- Can it draft outreach without inventing facts?

## Layer 2: Harness

The harness is the control system around the agents:

- state
- validation
- scope
- lifecycle
- event logs

This is why the database and validation code appear early. Real AI systems need
guardrails before external integrations.

## Layer 3: Business Workflow

Zapier, Slack, HubSpot, and Power BI are business workflow layers:

- Zapier starts a run.
- Slack lets a human approve or reject.
- HubSpot receives only approved records.
- Power BI explains workflow quality to management.

## Why Offline First?

The first implementation uses deterministic offline research fixtures. This
lets us prove the architecture before adding Tavily, live websites, or LLM
variability. Once the state machine and validation work, live AI tools can be
plugged into the same boundary.
