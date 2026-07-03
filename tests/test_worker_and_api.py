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

    def test_approved_draft_syncs_to_hubspot_when_client_is_configured(self):
        from account_intel.db import Database
        from account_intel.worker import Worker

        class FakeHubSpotClient:
            def __init__(self):
                self.calls = []

            def create_note(self, company_name, draft, source_urls):
                self.calls.append(
                    {
                        "company_name": company_name,
                        "draft": draft,
                        "source_urls": source_urls,
                    }
                )
                return "hubspot-note-123"

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
            fake_hubspot = FakeHubSpotClient()

            Worker(db=db, offline=True, hubspot_client=fake_hubspot).apply_review_decision(
                draft_id=draft["draft_id"],
                decision="approved",
                reviewed_by="reviewer@example.com",
            )

            updated = db.get_outreach_draft(draft["draft_id"])
            events = db.list_events(run_id)

        self.assertEqual(updated["status"], "synced_to_crm")
        self.assertEqual(updated["hubspot_object_id"], "hubspot-note-123")
        self.assertEqual(fake_hubspot.calls[0]["company_name"], "Northstar Health")
        self.assertIn("subject", fake_hubspot.calls[0]["draft"])
        self.assertGreaterEqual(len(fake_hubspot.calls[0]["source_urls"]), 1)
        self.assertTrue(any(event["event_type"] == "crm_synced" for event in events))

    def test_hubspot_sync_failure_keeps_draft_approved_and_logs_event(self):
        from account_intel.db import Database
        from account_intel.worker import Worker

        class FailingHubSpotClient:
            def create_note(self, company_name, draft, source_urls):
                raise RuntimeError("HubSpot is unavailable")

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

            Worker(db=db, offline=True, hubspot_client=FailingHubSpotClient()).apply_review_decision(
                draft_id=draft["draft_id"],
                decision="approved",
                reviewed_by="reviewer@example.com",
            )

            updated = db.get_outreach_draft(draft["draft_id"])
            events = db.list_events(run_id)

        self.assertEqual(updated["status"], "approved")
        self.assertIsNone(updated["hubspot_object_id"])
        failure_events = [event for event in events if event["event_type"] == "crm_sync_failed"]
        self.assertEqual(len(failure_events), 1)
        self.assertIn("HubSpot is unavailable", failure_events[0]["payload"]["error"])

    def test_sync_approved_drafts_skips_already_synced_drafts(self):
        from account_intel.db import Database
        from account_intel.worker import Worker

        class FakeHubSpotClient:
            def __init__(self):
                self.calls = []

            def create_note(self, company_name, draft, source_urls):
                self.calls.append(draft["draft_id"])
                return f"hubspot-{len(self.calls)}"

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
            db.update_draft_review(draft["draft_id"], "approved", "reviewer@example.com")
            fake_hubspot = FakeHubSpotClient()
            sync_worker = Worker(db=db, offline=True, hubspot_client=fake_hubspot)

            first = sync_worker.sync_approved_drafts()
            second = sync_worker.sync_approved_drafts()

            updated = db.get_outreach_draft(draft["draft_id"])

        self.assertEqual(first, {"synced": [draft["draft_id"]], "failed": []})
        self.assertEqual(second, {"synced": [], "failed": []})
        self.assertEqual(fake_hubspot.calls, [draft["draft_id"]])
        self.assertEqual(updated["status"], "synced_to_crm")


if __name__ == "__main__":
    unittest.main()
