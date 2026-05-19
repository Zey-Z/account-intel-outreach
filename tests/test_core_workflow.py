import tempfile
import unittest
from pathlib import Path


class CoreWorkflowTests(unittest.TestCase):
    def test_load_healthcare_icp_profile(self):
        from account_intel.config import load_icp_profiles

        profiles = load_icp_profiles(Path("icp_profiles.yaml"))

        self.assertIn("healthcare_insurance_ops", profiles)
        profile = profiles["healthcare_insurance_ops"]
        self.assertIn("claims", " ".join(profile.pain_points).lower())
        self.assertGreaterEqual(len(profile.buying_signals), 3)

    def test_grounding_rejects_claim_not_present_in_source_text(self):
        from account_intel.grounding import ground_findings
        from account_intel.models import SourceEvidence

        findings = [
            SourceEvidence(
                claim="Acme Health uses AI to automate prior authorization.",
                source_url="https://example.com/acme",
                source_type="company_website",
                retrieved_at="2026-05-18T00:00:00Z",
                grounding_passed=False,
            )
        ]

        grounded = ground_findings(
            findings,
            {"https://example.com/acme": "Acme Health provides claims analytics for payers."},
        )

        self.assertEqual(len(grounded), 0)

    def test_writer_evidence_check_flags_unsupported_draft_fact(self):
        from account_intel.models import OutreachDraft, SourceEvidence
        from account_intel.validation import validate_writer_evidence

        findings = [
            SourceEvidence(
                claim="Northstar Health serves regional payer operations teams.",
                source_url="https://example.com/northstar",
                source_type="company_website",
                retrieved_at="2026-05-18T00:00:00Z",
                grounding_passed=True,
            )
        ]
        draft = OutreachDraft(
            subject="Reducing claim review friction",
            body="I saw Northstar Health recently raised $90M and is expanding into Europe.",
            confidence=0.82,
            review_flag="ready_for_review",
            evidence_refs=[],
        )

        updated = validate_writer_evidence(draft, findings)

        self.assertEqual(updated.review_flag, "needs_human_review")
        self.assertIn("unsupported", updated.validation_notes.lower())

    def test_database_run_lifecycle_and_event_logging(self):
        from account_intel.db import Database

        with tempfile.TemporaryDirectory() as tmp:
            db = Database(f"sqlite:///{Path(tmp) / 'workflow.db'}")
            db.initialize()

            run_id = db.create_run(
                triggered_by="unit-test",
                icp_profile="healthcare_insurance_ops",
                companies=[{"name": "Northstar Health", "domain": "northstar.example"}],
            )
            db.update_run_status(run_id, "researching")
            db.log_event(run_id, "research_started", {"company_count": 1})

            run = db.get_run(run_id)
            events = db.list_events(run_id)

            self.assertEqual(run["status"], "researching")
            self.assertEqual(events[0]["event_type"], "research_started")
            self.assertEqual(events[0]["payload"]["company_count"], 1)

    def test_database_accepts_postgres_url_for_neon_deployment(self):
        from account_intel.db import Database

        db = Database("postgresql://user:pass@example.neon.tech/neondb?sslmode=require")

        self.assertEqual(db.backend, "postgres")


if __name__ == "__main__":
    unittest.main()
