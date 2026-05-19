from __future__ import annotations

import json
from typing import Any

from account_intel.db import Database


def build_run_report(db: Database, run_id: str) -> dict[str, Any]:
    """Return a compact, human-readable snapshot of one workflow run."""
    run = db.get_run(run_id)
    events = db.list_events(run_id)
    with db.connect() as conn:
        company_rows = conn.execute(
            "SELECT company_id, name, domain, segment FROM companies WHERE run_id = ? ORDER BY name",
            (run_id,),
        ).fetchall()
        draft_rows = conn.execute(
            """
            SELECT
                d.draft_id,
                c.name AS company_name,
                d.subject,
                d.confidence,
                d.review_flag,
                d.status,
                d.evidence_refs,
                d.validation_notes
            FROM outreach_drafts d
            JOIN companies c ON c.company_id = d.company_id
            WHERE c.run_id = ?
            ORDER BY c.name, d.draft_id
            """,
            (run_id,),
        ).fetchall()

    companies = [dict(row) for row in company_rows]
    drafts = []
    for row in draft_rows:
        draft = dict(row)
        draft["evidence_refs"] = json.loads(draft["evidence_refs"])
        drafts.append(draft)

    return {
        "run": run,
        "summary": {
            "final_status": run["status"],
            "company_count": len(companies),
            "draft_count": len(drafts),
            "event_count": len(events),
        },
        "companies": companies,
        "drafts": drafts,
        "events": events,
    }
