import tempfile
import unittest
from pathlib import Path


class WorkerAndApiTests(unittest.TestCase):
    def test_health_endpoint_reports_ok(self):
        from main import app

        route = next(route for route in app.routes if getattr(route, "path", None) == "/health")
        response = route.endpoint()

        self.assertEqual(response, {"status": "ok"})

    def test_worker_processes_queued_run_to_review_or_archive(self):
        from account_intel.db import Database
        from account_intel.worker import Worker

        with tempfile.TemporaryDirectory() as tmp:
            db = Database(f"sqlite:///{Path(tmp) / 'workflow.db'}")
            db.initialize()
            run_id = db.create_run(
                triggered_by="unit-test",
                icp_profile="healthcare_insurance_ops",
                companies=[{"name": "Northstar Health", "domain": "northstar.example"}],
            )

            worker = Worker(db=db, offline=True)
            worker.process_next()

            run = db.get_run(run_id)
            drafts = db.list_outreach_drafts(run_id)
            events = db.list_events(run_id)

            self.assertIn(run["status"], {"sent_to_review", "needs_human_research", "archived"})
            self.assertEqual(len(drafts), 1)
            self.assertTrue(any(event["event_type"] == "worker_completed" for event in events))

    def test_worker_handles_multiple_companies_without_duplicate_finding_ids(self):
        from account_intel.db import Database
        from account_intel.worker import Worker

        with tempfile.TemporaryDirectory() as tmp:
            db = Database(f"sqlite:///{Path(tmp) / 'workflow.db'}")
            db.initialize()
            run_id = db.create_run(
                triggered_by="unit-test",
                icp_profile="healthcare_insurance_ops",
                companies=[
                    {"name": "Northstar Health", "domain": "northstar.example"},
                    {"name": "PayerOps Cloud", "domain": "payerops.example"},
                ],
            )

            worker = Worker(db=db, offline=True)
            worker.process_next()

            drafts = db.list_outreach_drafts(run_id)
            events = db.list_events(run_id)

            self.assertEqual(len(drafts), 2)
            self.assertEqual(
                len([event for event in events if event["event_type"] == "company_processed"]),
                2,
            )

    def test_request_changes_rewrites_once_and_returns_to_review(self):
        from account_intel.db import Database
        from account_intel.worker import Worker

        with tempfile.TemporaryDirectory() as tmp:
            db = Database(f"sqlite:///{Path(tmp) / 'workflow.db'}")
            db.initialize()
            run_id = db.create_run(
                triggered_by="unit-test",
                icp_profile="healthcare_insurance_ops",
                companies=[{"name": "Northstar Health", "domain": "northstar.example"}],
            )
            worker = Worker(db=db, offline=True)
            worker.process_next()
            draft = db.list_outreach_drafts(run_id)[0]

            worker.apply_review_decision(
                draft_id=draft["draft_id"],
                decision="needs_revision",
                reviewed_by="reviewer@example.com",
                revision_note="Make the opening less salesy.",
            )

            updated = db.get_outreach_draft(draft["draft_id"])
            self.assertEqual(updated["status"], "sent_to_review")
            self.assertEqual(updated["revision_count"], 1)
            self.assertIn("less salesy", updated["revision_note"])


if __name__ == "__main__":
    unittest.main()
