# Power BI Dashboard

`AI_Account_Intelligence_Dashboard.pbix` is the management view of the agent
workflow. It turns run history into a small control tower for volume, quality,
review workload, failures, and latency.

## What the Dashboard Answers

- How many account-intelligence runs were processed?
- What was the average ICP fit score?
- What share of collected findings passed grounding?
- How much work needed human review?
- How many failure events occurred?
- How long did processing take?
- Which final statuses contain the most runs?

The first page contains six KPI cards plus run-count-by-status and
average-fit-score-by-status charts.

## Data Flow

```text
Neon PostgreSQL views
  -> protected FastAPI CSV endpoints
  -> schema-validating Python exporter
  -> local CSV snapshot + manifest
  -> Power BI Desktop
```

Power BI does not connect with the Neon password. The exporter calls the
protected reporting API with `X-API-Key`, checks the exact column contract, and
writes a reviewable local snapshot. The `.pbix` therefore contains no database
password or API key.

## Refresh the Snapshot

Set these values in the local `.env` file:

```text
ACCOUNT_INTEL_BASE_URL=https://account-intel-outreach.onrender.com
ACCOUNT_INTEL_API_KEY=<the same protected API key used by Render>
```

Then run:

```powershell
python scripts\export_powerbi_data.py
```

The exporter writes:

- `powerbi/data/dashboard_runs_view.csv` - one row per workflow run;
- `powerbi/data/outreach_performance_view.csv` - grouped draft-review outcomes;
- `powerbi/data/snapshot_manifest.json` - generation time, source, row counts,
  and data classification.

After export, open the PBIX in Power BI Desktop and select **Refresh**. Confirm
that the manifest row counts agree with the imported tables before saving.

## Reporting Contract

### `dashboard_runs_view`

One row per run, including status, company count, fit score, grounding rate,
confidence, review counts, event count, token estimate, latency, and failures.

### `outreach_performance_view`

Grouped review results, including final draft status, review flag, draft count,
and average draft confidence.

The exporter rejects missing, reordered, or unexpected columns. This is a
deliberate schema-drift alarm: a database change should not silently produce a
misleading dashboard.

## Business Measures

| Measure | Definition |
|---|---|
| Total Runs | Distinct count of `run_id`. |
| Average Fit Score | Average of `average_fit_score`. |
| Grounding Rate | Average of `grounding_rate`, formatted as a percentage. |
| Human Review Workload | Sum of `needs_human_review_count`. |
| Failure Events | Sum of `failure_event_count`. |
| Average Latency | Average of `average_latency_ms`, displayed in seconds. |

## Verification Checklist

1. The exporter completes without a schema error.
2. `snapshot_manifest.json` names the expected Render service.
3. Manifest row counts equal the CSV row counts.
4. Power BI table row counts match the manifest.
5. Grounding Rate is formatted as a percentage, not a raw decimal.
6. KPI totals agree with a direct aggregation of the CSV snapshot.
7. No credential appears in the CSV, manifest, or PBIX.

The verified portfolio snapshot contains 15 deployed test-context runs. All
reported values use public company data and should not be presented as customer
production metrics.
