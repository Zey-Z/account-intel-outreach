import hashlib
import hmac
import json
import tempfile
import time
import unittest
from pathlib import Path


class ReportingAndIntegrationTests(unittest.TestCase):
    def test_database_exposes_power_bi_quality_and_cost_views(self):
        from account_intel.db import Database

        with tempfile.TemporaryDirectory() as tmp:
            db = Database(f"sqlite:///{Path(tmp) / 'workflow.db'}")
            db.initialize()

            with db.connect() as conn:
                rows = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'view'"
                ).fetchall()

            view_names = {row["name"] for row in rows}
            self.assertIn("lead_runs_view", view_names)
            self.assertIn("outreach_performance_view", view_names)
            self.assertIn("agent_quality_view", view_names)
            self.assertIn("cost_latency_view", view_names)

    def test_build_run_report_summarizes_run_drafts_and_events(self):
        from account_intel.db import Database
        from account_intel.reporting import build_run_report
        from account_intel.worker import Worker

        with tempfile.TemporaryDirectory() as tmp:
            db = Database(f"sqlite:///{Path(tmp) / 'workflow.db'}")
            db.initialize()
            run_id = db.create_run(
                triggered_by="unit-test",
                icp_profile="healthcare_insurance_ops",
                companies=[{"name": "Northstar Health", "domain": "northstar.example"}],
            )
            Worker(db=db, offline=True).process_next()

            report = build_run_report(db, run_id)

            self.assertEqual(report["run"]["run_id"], run_id)
            self.assertEqual(report["summary"]["draft_count"], 1)
            self.assertGreaterEqual(report["summary"]["event_count"], 2)
            self.assertIn(report["summary"]["final_status"], {"sent_to_review", "needs_human_research", "archived"})
            self.assertEqual(report["drafts"][0]["company_name"], "Northstar Health")

    def test_slack_signature_verification_accepts_valid_signature(self):
        from account_intel.integrations.slack import verify_slack_signature

        secret = "test-secret"
        timestamp = str(int(time.time()))
        body = b"payload=%7B%22type%22%3A%22block_actions%22%7D"
        base = b"v0:" + timestamp.encode("utf-8") + b":" + body
        signature = "v0=" + hmac.new(secret.encode("utf-8"), base, hashlib.sha256).hexdigest()

        self.assertTrue(verify_slack_signature(secret, timestamp, body, signature))

    def test_hubspot_note_payload_keeps_sources_with_draft(self):
        from account_intel.integrations.hubspot import HubSpotClient

        payload = HubSpotClient(token="fake-token").create_note_payload(
            "Northstar Health",
            {
                "subject": "Idea for operations workflows",
                "body": "Human-approved outreach draft.",
            },
            ["https://example.com/source-1", "https://example.com/source-2"],
        )

        note_body = payload["properties"]["hs_note_body"]
        self.assertIn("Idea for operations workflows", note_body)
        self.assertIn("Human-approved outreach draft.", note_body)
        self.assertIn("https://example.com/source-1", note_body)
        self.assertIn("https://example.com/source-2", note_body)


if __name__ == "__main__":
    unittest.main()
