# Real CrewAI + Tavily Runtime

The project now supports both a deterministic learning/runtime mode and a real
CrewAI runtime mode.

## Goal

Keep the same inputs, outputs, database tables, and status machine. Only replace
the internals of the agent brain.

```text
Default:
OfflineResearchClient -> deterministic AccountIntelligenceCrew

Real agent mode:
Tavily Search/Extract -> CrewAI Researcher/Analyst/Writer tasks -> same schemas
```

## Step 1: Install Runtime Dependencies

```powershell
pip install -r requirements.txt
```

Then verify:

```powershell
crewai --version
python -c "import fastapi, crewai; print('runtime ok')"
```

## Step 2: Add API Keys

Copy `.env.example` to `.env` and set:

```text
OPENAI_API_KEY=
TAVILY_API_KEY=
```

Use public company data only. Do not use PHI, patient data, private personal
data, or internal customer data.

## Step 3: Choose Runtime Mode

For normal local tests and cheap demos:

```text
RESEARCH_MODE=offline
AGENT_RUNTIME=deterministic
```

For real web research but deterministic Analyst/Writer logic:

```text
RESEARCH_MODE=tavily
AGENT_RUNTIME=deterministic
```

For the full CrewAI multi-agent runtime:

```text
RESEARCH_MODE=tavily
AGENT_RUNTIME=crewai
OPENAI_API_KEY=<your LLM key>
CREWAI_LLM=<optional model setting>
```

## Runtime Design

The worker and database do not change. `AccountIntelligenceCrew.run_company()`
keeps returning the same `CrewResult`.

The real CrewAI runtime creates:

- `Senior Account Researcher`
- `GTM Fit Strategist`
- `Personalized Outreach Copywriter`

Each agent receives a task with `output_pydantic`, so the system can convert the
agent result back into our typed workflow schema. The harness still owns Tavily
page fetching, grounding validation, writer evidence checks, database writes,
and status transitions.

## Step 5: Re-run Existing Tests

```powershell
$env:PYTHONPATH="C:\Users\jinze\projects\account-intel-outreach\src"
python -m unittest discover -s tests -v
```

The tests are the safety net. If the real CrewAI implementation breaks the
schema, state machine, or validation layer, tests should catch it.
