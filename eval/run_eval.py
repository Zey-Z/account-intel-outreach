from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from account_intel.db import Database  # noqa: E402
from account_intel.worker import Worker  # noqa: E402


def main() -> None:
    data = yaml.safe_load((ROOT / "eval" / "test_companies.yaml").read_text(encoding="utf-8"))
    db = Database(os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'eval.db'}"))
    db.initialize()
    run_id = db.create_run(
        triggered_by="eval",
        icp_profile="healthcare_insurance_ops",
        companies=[{"name": item["name"], "domain": item["domain"]} for item in data["companies"]],
    )
    Worker(db=db, icp_path=ROOT / "icp_profiles.yaml").process_next()
    run = db.get_run(run_id)
    events = db.list_events(run_id)
    drafts = db.list_outreach_drafts(run_id)
    processed = [event for event in events if event["event_type"] == "company_processed"]
    avg_fit = sum(event["payload"]["fit_score"] for event in processed) / max(1, len(processed))
    needs_review = sum(1 for draft in drafts if draft["review_flag"] == "needs_human_review")
    actuals = load_company_actuals(db, run_id)
    rubric_results = [
        evaluate_company_rubric(
            company_name=item["name"],
            expected=item.get("expected", {}),
            actual=actuals.get(item["name"], {}),
        )
        for item in data["companies"]
    ]
    rubric_passed = sum(1 for result in rubric_results if result["passed"])
    rubric_failed = len(rubric_results) - rubric_passed
    print("Evaluation report")
    print(f"run_id={run_id}")
    print(f"status={run['status']}")
    print(f"companies={len(processed)}")
    print(f"average_fit_score={avg_fit:.1f}")
    print(f"needs_human_review={needs_review}")
    print(f"events={len(events)}")
    print(f"rubric_passed={rubric_passed}")
    print(f"rubric_failed={rubric_failed}")
    for result in rubric_results:
        outcome = "PASS" if result["passed"] else "FAIL"
        print(
            f"- {result['company']}: {outcome} "
            f"fit_score={result['fit_score']} status={result['status']}"
        )
        for failure in result["failures"]:
            print(f"  - {failure}")


def evaluate_company_rubric(
    company_name: str,
    expected: dict,
    actual: dict,
) -> dict:
    failures: list[str] = []
    fit_score = int(actual.get("fit_score", 0))
    min_fit_score = int(expected.get("min_fit_score", 0))
    if fit_score < min_fit_score:
        failures.append(f"fit_score {fit_score} < expected {min_fit_score}")

    status = str(actual.get("status", "missing"))
    expected_status = expected.get("must_route_to")
    if expected_status and status != expected_status:
        failures.append(f"status {status} != expected {expected_status}")

    text = str(actual.get("text", "")).lower()
    missing_terms = [
        str(term)
        for term in expected.get("required_terms", [])
        if str(term).lower() not in text
    ]
    if missing_terms:
        failures.append(f"missing required terms: {', '.join(missing_terms)}")

    return {
        "company": company_name,
        "passed": not failures,
        "failures": failures,
        "fit_score": fit_score,
        "status": status,
    }


def load_company_actuals(db: Database, run_id: str) -> dict[str, dict]:
    actuals: dict[str, dict] = {}
    for company in db.list_companies(run_id):
        company_id = company["company_id"]
        with db.connect() as conn:
            analysis = conn.execute(
                "SELECT * FROM analysis_outputs WHERE company_id = ?",
                (company_id,),
            ).fetchone()
            draft = conn.execute(
                "SELECT * FROM outreach_drafts WHERE company_id = ?",
                (company_id,),
            ).fetchone()
            findings = conn.execute(
                "SELECT claim FROM research_findings WHERE company_id = ?",
                (company_id,),
            ).fetchall()
        text_parts = [row["claim"] for row in findings]
        if analysis:
            text_parts.extend(
                [
                    analysis["pain_point_match"],
                    analysis["buying_trigger"],
                    analysis["recommended_angle"],
                    analysis["risk_flags"],
                ]
            )
        if draft:
            text_parts.extend([draft["subject"], draft["body"], draft["validation_notes"]])
        actuals[company["name"]] = {
            "fit_score": analysis["fit_score"] if analysis else 0,
            "status": draft["status"] if draft else "missing",
            "text": " ".join(part for part in text_parts if part),
        }
    return actuals


if __name__ == "__main__":
    main()
