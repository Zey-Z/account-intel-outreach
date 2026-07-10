# Power BI Dashboard

The dashboard uses a local, reviewable snapshot of the protected reporting API.
No API key or database password is stored inside the `.pbix` file.

## Refresh the snapshot

Run:

```powershell
python scripts/export_powerbi_data.py
```

This writes:

- `data/dashboard_runs_view.csv` - one row per workflow run.
- `data/outreach_performance_view.csv` - draft review outcomes.
- `data/snapshot_manifest.json` - source, time, and row counts.

## Dashboard measures

The report uses these business definitions:

- Total Runs: distinct count of `run_id`.
- Average Fit Score: average of `average_fit_score`.
- Grounding Rate: average of `grounding_rate`, formatted as a percentage.
- Human Review Workload: sum of `needs_human_review_count`.
- Failure Events: sum of `failure_event_count`.
- Average Latency: average of `average_latency_ms`, displayed in seconds.

All values are portfolio test-context metrics based on public company data.
