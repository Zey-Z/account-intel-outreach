from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from account_intel.config import load_icp_profiles
from account_intel.crew import AccountIntelligenceCrew
from account_intel.db import Database
from account_intel.integrations.hubspot import HubSpotClient
from account_intel.research_tools import build_research_client


logger = logging.getLogger("account_intel.worker")


class Worker:
    def __init__(
        self,
        db: Database,
        icp_path: Path | None = None,
        offline: bool | None = None,
        hubspot_client: Any | None = None,
    ):
        self.db = db
        self.icp_path = icp_path or Path("icp_profiles.yaml")
        mode = None if offline is None else ("offline" if offline else "tavily")
        selected_mode = (mode or os.getenv("RESEARCH_MODE", "offline")).lower()
        self.offline = selected_mode in {"offline", "fixture", "mock"}
        self.crew = AccountIntelligenceCrew(research_client=build_research_client(mode=mode))
        self.hubspot_client = hubspot_client if hubspot_client is not None else self._hubspot_client_from_env()

    def process_next(self) -> str | None:
        run = self.db.claim_next_queued_run()
        if run is None:
            return None
        run_id = run["run_id"]
        profiles = load_icp_profiles(self.icp_path)
        profile = profiles[run["icp_profile"]]
        self.db.log_event(run_id, "worker_started", {"icp_profile": profile.key})
        try:
            final_status = "archived"
            successful_companies = 0
            last_company_error: Exception | None = None
            for company in self.db.list_companies(run_id):
                try:
                    result = self.crew.run_company(company["name"], company["domain"], profile)
                except Exception as exc:
                    last_company_error = exc
                    logger.warning(
                        json.dumps(
                            {
                                "event": "company_failed",
                                "run_id": run_id,
                                "company": company["name"],
                                "error": str(exc),
                            },
                            sort_keys=True,
                        )
                    )
                    self.db.log_event(
                        run_id,
                        "company_failed",
                        {
                            "company": company["name"],
                            "domain": company["domain"],
                            "error": str(exc),
                        },
                        company_id=company["company_id"],
                    )
                    continue
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
                successful_companies += 1
                final_status = self._dominant_status(final_status, result.status)
            if successful_companies == 0:
                raise RuntimeError(str(last_company_error) if last_company_error else "No companies were processed.")
            self.db.update_run_status(run_id, final_status)
            self.db.log_event(run_id, "worker_completed", {"status": final_status})
            return run_id
        except Exception as exc:
            self.db.increment_retry(run_id)
            self.db.update_run_status(run_id, "failed")
            self.db.log_event(run_id, "worker_failed", {"error": str(exc)})
            logger.error(
                json.dumps({"event": "worker_failed", "run_id": run_id, "error": str(exc)}, sort_keys=True),
                exc_info=True,
            )
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
            self._sync_approved_draft(draft_id)
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

    def sync_approved_drafts(self) -> dict[str, list[str]]:
        if self.hubspot_client is None:
            return {"synced": [], "failed": []}
        result = {"synced": [], "failed": []}
        for draft in self.db.list_approved_drafts_without_hubspot():
            if self._sync_approved_draft(draft["draft_id"]):
                result["synced"].append(draft["draft_id"])
            else:
                result["failed"].append(draft["draft_id"])
        return result

    def _sync_approved_draft(self, draft_id: str) -> bool:
        if self.hubspot_client is None:
            return False
        draft = self.db.get_draft_sync_context(draft_id)
        if draft.get("hubspot_object_id"):
            return True
        run_id = draft["run_id"]
        source_urls = self.db.list_source_urls_for_draft(draft_id)
        try:
            hubspot_object_id = self.hubspot_client.create_note(draft["company_name"], draft, source_urls)
            self.db.set_draft_hubspot_id(draft_id, hubspot_object_id)
            self.db.log_event(
                run_id,
                "crm_synced",
                {
                    "draft_id": draft_id,
                    "hubspot_object_id": hubspot_object_id,
                    "company_name": draft["company_name"],
                },
                company_id=draft["company_id"],
            )
            logger.info(
                json.dumps(
                    {
                        "event": "crm_synced",
                        "run_id": run_id,
                        "draft_id": draft_id,
                        "hubspot_object_id": hubspot_object_id,
                    },
                    sort_keys=True,
                )
            )
            return True
        except Exception as exc:
            self.db.log_event(
                run_id,
                "crm_sync_failed",
                {
                    "draft_id": draft_id,
                    "company_name": draft["company_name"],
                    "error": str(exc),
                },
                company_id=draft["company_id"],
            )
            logger.warning(
                json.dumps(
                    {
                        "event": "crm_sync_failed",
                        "run_id": run_id,
                        "draft_id": draft_id,
                        "error": str(exc),
                    },
                    sort_keys=True,
                )
            )
            return False

    @staticmethod
    def _hubspot_client_from_env() -> HubSpotClient | None:
        token = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN", "").strip()
        if not token:
            return None
        return HubSpotClient(token=token)

    @staticmethod
    def _dominant_status(current: str, candidate: str) -> str:
        priority = {"sent_to_review": 4, "needs_human_research": 3, "archived": 2, "failed": 1}
        return candidate if priority.get(candidate, 0) >= priority.get(current, 0) else current
