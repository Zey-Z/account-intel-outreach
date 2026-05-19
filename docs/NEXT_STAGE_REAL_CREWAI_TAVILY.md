# Next Stage: Real CrewAI + Tavily

The current project proves the workflow harness with deterministic offline data.
The next stage replaces the offline research fixture with live tools.

## Goal

Keep the same inputs, outputs, database tables, and status machine. Only replace
the internals of the agent brain.

```text
Current:
OfflineResearchClient -> AccountIntelligenceCrew

Next:
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

## Step 3: Replace Research Client

Implement a Tavily-backed `ResearchClient` with the same method:

```python
search_and_extract(company_name, domain, profile) -> list[ExtractedPage]
```

This keeps the rest of the workflow unchanged.

## Step 4: Replace Deterministic Crew Internals

Create CrewAI agents for:

- Researcher
- Analyst
- Writer

Each task should return the same schema currently used by the deterministic
implementation. Do not let the agent write directly to the database. The worker
should still own persistence and status transitions.

## Step 5: Re-run Existing Tests

```powershell
$env:PYTHONPATH="C:\Users\jinze\projects\account-intel-outreach\src"
python -m unittest discover -s tests -v
```

The tests are the safety net. If the real CrewAI implementation breaks the
schema, state machine, or validation layer, tests should catch it.
