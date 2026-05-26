from __future__ import annotations

from typing import Any

from account_intel.db import Database, decode_json_value


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
        finding_rows = conn.execute(
            """
            SELECT
                rf.finding_id,
                c.name AS company_name,
                rf.claim,
                rf.source_url,
                rf.source_type,
                rf.retrieved_at,
                rf.grounding_passed
            FROM research_findings rf
            JOIN companies c ON c.company_id = rf.company_id
            WHERE c.run_id = ?
            ORDER BY c.name, rf.finding_id
            """,
            (run_id,),
        ).fetchall()
        analysis_rows = conn.execute(
            """
            SELECT
                a.analysis_id,
                c.name AS company_name,
                a.icp_profile,
                a.fit_score,
                a.pain_point_match,
                a.buying_trigger,
                a.risk_flags,
                a.recommended_angle,
                a.confidence
            FROM analysis_outputs a
            JOIN companies c ON c.company_id = a.company_id
            WHERE c.run_id = ?
            ORDER BY c.name, a.analysis_id
            """,
            (run_id,),
        ).fetchall()

    companies = [dict(row) for row in company_rows]
    findings = [dict(row) for row in finding_rows]
    drafts = []
    for row in draft_rows:
        draft = dict(row)
        draft["evidence_refs"] = decode_json_value(draft["evidence_refs"])
        drafts.append(draft)
    analysis = []
    for row in analysis_rows:
        item = dict(row)
        item["risk_flags"] = decode_json_value(item["risk_flags"])
        analysis.append(item)

    return {
        "run": run,
        "summary": {
            "final_status": run["status"],
            "company_count": len(companies),
            "finding_count": len(findings),
            "analysis_count": len(analysis),
            "draft_count": len(drafts),
            "event_count": len(events),
        },
        "companies": companies,
        "findings": findings,
        "analysis": analysis,
        "drafts": drafts,
        "events": events,
    }
