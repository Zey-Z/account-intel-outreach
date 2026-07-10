from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen

REPORT_COLUMNS = {
    "dashboard_runs_view": [
        "run_id",
        "triggered_by",
        "started_at",
        "finished_at",
        "icp_profile",
        "status",
        "company_count",
        "retry_count",
        "average_fit_score",
        "grounding_rate",
        "finding_count",
        "grounded_finding_count",
        "average_analysis_confidence",
        "average_draft_confidence",
        "ready_for_review_count",
        "needs_human_review_count",
        "event_count",
        "token_estimate",
        "average_latency_ms",
        "failure_event_count",
    ],
    "outreach_performance_view": [
        "status",
        "review_flag",
        "draft_count",
        "average_confidence",
    ],
}


def fetch_report_csv(
    base_url: str,
    api_key: str,
    view_name: str,
    opener: Callable[..., Any] = urlopen,
) -> str:
    if view_name not in REPORT_COLUMNS:
        raise ValueError(f"Unsupported Power BI view: {view_name}")
    if not api_key.strip():
        raise ValueError("ACCOUNT_INTEL_API_KEY is required for Power BI export.")

    request = Request(
        f"{base_url.rstrip('/')}/reports/{view_name}.csv",
        headers={"X-API-Key": api_key},
    )
    with opener(request, timeout=60) as response:
        content = response.read().decode("utf-8-sig")

    reader = csv.reader(io.StringIO(content))
    header = next(reader, [])
    expected = REPORT_COLUMNS[view_name]
    if header != expected:
        raise ValueError(
            f"Unexpected columns for {view_name}: expected {expected}, received {header}"
        )
    return content


def export_powerbi_snapshot(
    base_url: str,
    api_key: str,
    output_dir: str | Path,
    opener: Callable[..., Any] = urlopen,
) -> dict[str, Any]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    row_counts: dict[str, int] = {}

    for view_name in REPORT_COLUMNS:
        content = fetch_report_csv(base_url, api_key, view_name, opener=opener)
        output_path = destination / f"{view_name}.csv"
        output_path.write_text(content, encoding="utf-8-sig", newline="")
        row_counts[view_name] = max(0, len(list(csv.reader(io.StringIO(content)))) - 1)

    manifest = {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "source": base_url.rstrip("/"),
        "views": row_counts,
        "classification": "public-company portfolio test data",
    }
    (destination / "snapshot_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest
