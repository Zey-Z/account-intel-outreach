from __future__ import annotations

from pathlib import Path

from account_intel.config import load_icp_profiles
from account_intel.crew import AccountIntelligenceCrew
from account_intel.db import Database


class Worker:
    def __init__(self, db: Database, icp_path: Path | None = None, offline: bool = True):
        self.db = db
        self.icp_path = icp_path or Path("icp_profiles.yaml")
        self.offline = offline
        self.crew = AccountIntelligenceCrew()

    def process_next(self) -> str | None:
        run = self.db.next_queued_run()
        if run is None:
            return None
        run_id = run["run_id"]
        profiles = load_icp_profiles(self.icp_path)
        profile = profiles[run["icp_profile"]]
        self.db.update_run_status(run_id, "researching")
        self.db.log_event(run_id, "worker_started", {"icp_profile": profile.key})
        try:
            final_status = "archived"
            for company in self.db.list_companies(run_id):
                result = self.crew.run_company(company["name"], company["domain"], profile)
                finding_ids = self.db.save_research_findings(
                    company["company_id"],
                    [finding.to_dict() for finding in result.research.findings],
                )
                self.db.update_run_status(run_id, "research_completed")
                self.db.save_analysis(company["company_id"], profile.key, result.analysis.to_dict())
                self.db.update_run_status(run_id, "analysis_completed")
                draft_payload = result.draft.to_dict()
                draft_payload["evidence_refs"] = finding_ids or draft_payload["evidence_refs"]
                self.db.save_outreach_draft(company["company_id"], draft_payload, result.status)
                self.db.update_run_status(run_id, "draft_created")
                self.db.log_event(
                    run_id,
                    "company_processed",
                    {
                        "company": company["name"],
                        "status": result.status,
                        "fit_score": result.analysis.fit_score,
                        "token_estimate": result.token_estimate,
                        "latency_ms": result.latency_ms,
                    },
                    company_id=company["company_id"],
                )
                final_status = self._dominant_status(final_status, result.status)
            self.db.update_run_status(run_id, final_status)
            self.db.log_event(run_id, "worker_completed", {"status": final_status})
            return run_id
        except Exception as exc:
            self.db.increment_retry(run_id)
            self.db.update_run_status(run_id, "failed")
            self.db.log_event(run_id, "worker_failed", {"error": str(exc)})
            raise

    def apply_review_decision(
        self,
        draft_id: str,
        decision: str,
        reviewed_by: str,
        revision_note: str | None = None,
    ) -> None:
        if decision == "approved":
            self.db.update_draft_review(draft_id, "approved", reviewed_by)
        elif decision == "rejected":
            self.db.update_draft_review(draft_id, "rejected", reviewed_by)
        elif decision == "needs_revision":
            self.db.update_draft_review(
                draft_id,
                "sent_to_review",
                reviewed_by,
                revision_note=revision_note,
                increment_revision=True,
            )
        else:
            raise ValueError(f"Unsupported review decision: {decision}")

    @staticmethod
    def _dominant_status(current: str, candidate: str) -> str:
        priority = {"sent_to_review": 4, "needs_human_research": 3, "archived": 2, "failed": 1}
        return candidate if priority.get(candidate, 0) >= priority.get(current, 0) else current
