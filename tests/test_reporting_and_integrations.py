import hashlib
import hmac
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


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
            self.assertIn("dashboard_runs_view", view_names)

            with db.connect() as conn:
                columns = conn.execute("PRAGMA table_info(dashboard_runs_view)").fetchall()
            column_names = {column["name"] for column in columns}
            self.assertIn("started_at", column_names)
            self.assertIn("average_fit_score", column_names)
            self.assertIn("needs_human_review_count", column_names)
            self.assertIn("average_latency_ms", column_names)

    def test_power_bi_views_do_not_weight_company_metrics_by_finding_count(self):
        from account_intel.db import Database, now_iso

        with tempfile.TemporaryDirectory() as tmp:
            db = Database(f"sqlite:///{Path(tmp) / 'workflow.db'}")
            db.initialize()
            run_id = db.create_run(
                triggered_by="unit-test",
                icp_profile="healthcare_insurance_ops",
                companies=[
                    {"name": "One Finding Health", "domain": "one.example"},
                    {"name": "Three Finding Health", "domain": "three.example"},
                ],
            )
            companies = db.list_companies(run_id)
            finding_counts = [1, 3]
            fit_scores = [100, 0]
            analysis_confidences = [0.9, 0.5]
            draft_confidences = [0.8, 0.4]
            review_flags = ["ready_for_review", "needs_human_review"]

            for index, company in enumerate(companies):
                findings = [
                    {
                        "claim": f"Grounded finding {finding_index}",
                        "source_url": f"https://example.com/{index}/{finding_index}",
                        "source_type": "company_website",
                        "retrieved_at": now_iso(),
                        "grounding_passed": True,
                    }
                    for finding_index in range(finding_counts[index])
                ]
                db.save_research_findings(company["company_id"], findings)
                db.save_analysis(
                    company["company_id"],
                    "healthcare_insurance_ops",
                    {
                        "fit_score": fit_scores[index],
                        "pain_point_match": "test",
                        "buying_trigger": "test",
                        "risk_flags": [],
                        "recommended_angle": "test",
                        "confidence": analysis_confidences[index],
                    },
                )
                db.save_outreach_draft(
                    company["company_id"],
                    {
                        "subject": "Test draft",
                        "body": "Human-reviewed test draft.",
                        "confidence": draft_confidences[index],
                        "review_flag": review_flags[index],
                        "evidence_refs": [],
                    },
                    "sent_to_review",
                )

            with db.connect() as conn:
                lead_row = conn.execute(
                    "SELECT * FROM lead_runs_view WHERE run_id = ?", (run_id,)
                ).fetchone()
                quality_row = conn.execute(
                    "SELECT * FROM agent_quality_view WHERE run_id = ?", (run_id,)
                ).fetchone()

            self.assertAlmostEqual(lead_row["average_fit_score"], 50.0)
            self.assertAlmostEqual(quality_row["average_analysis_confidence"], 0.7)
            self.assertAlmostEqual(quality_row["average_draft_confidence"], 0.6)
            self.assertEqual(quality_row["ready_for_review_count"], 1)
            self.assertEqual(quality_row["needs_human_review_count"], 1)

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
            draft_id = db.list_outreach_drafts(run_id)[0]["draft_id"]
            db.update_draft_review(draft_id, "approved", "unit-reviewer")
            db.set_draft_hubspot_id(draft_id, "hubspot-note-123")

            report = build_run_report(db, run_id)

            self.assertEqual(report["run"]["run_id"], run_id)
            self.assertEqual(report["summary"]["draft_count"], 1)
            self.assertGreaterEqual(report["summary"]["finding_count"], 3)
            self.assertEqual(report["summary"]["analysis_count"], 1)
            self.assertGreaterEqual(report["summary"]["event_count"], 2)
            self.assertEqual(report["summary"]["crm_synced_count"], 1)
            self.assertIn(report["summary"]["final_status"], {"sent_to_review", "needs_human_research", "archived"})
            self.assertEqual(report["drafts"][0]["company_name"], "Northstar Health")
            self.assertEqual(report["drafts"][0]["status"], "synced_to_crm")
            self.assertEqual(report["drafts"][0]["reviewed_by"], "unit-reviewer")
            self.assertTrue(report["drafts"][0]["reviewed_at"])
            self.assertEqual(report["drafts"][0]["hubspot_object_id"], "hubspot-note-123")
            self.assertEqual(report["findings"][0]["company_name"], "Northstar Health")
            self.assertIn("source_url", report["findings"][0])
            self.assertEqual(report["analysis"][0]["company_name"], "Northstar Health")
            self.assertIn("fit_score", report["analysis"][0])

    def test_slack_signature_verification_accepts_valid_signature(self):
        from account_intel.integrations.slack import verify_slack_signature

        secret = "test-secret"
        timestamp = str(int(time.time()))
        body = b"payload=%7B%22type%22%3A%22block_actions%22%7D"
        base = b"v0:" + timestamp.encode("utf-8") + b":" + body
        signature = "v0=" + hmac.new(secret.encode("utf-8"), base, hashlib.sha256).hexdigest()

        self.assertTrue(verify_slack_signature(secret, timestamp, body, signature))

    def test_slack_review_message_from_report_includes_evidence_and_actions(self):
        from account_intel.integrations.slack import build_review_message_from_report

        report = {
            "run": {"run_id": "run_123", "status": "sent_to_review"},
            "analysis": [
                {
                    "company_name": "Oscar Health",
                    "fit_score": 88,
                    "pain_point_match": "member support triage",
                    "buying_trigger": "Public hiring and healthcare operations signals suggest workflow support needs.",
                    "recommended_angle": "AI-assisted exception triage with human approval",
                    "confidence": 0.82,
                    "risk_flags": [],
                }
            ],
            "drafts": [
                {
                    "draft_id": "draft_123",
                    "company_name": "Oscar Health",
                    "subject": "Idea for Oscar Health operations workflows",
                    "body": "Draft body for human review.",
                    "confidence": 0.82,
                    "review_flag": "ready_for_review",
                    "status": "sent_to_review",
                    "evidence_refs": ["finding_1", "finding_2"],
                }
            ],
            "findings": [
                {
                    "finding_id": "finding_1",
                    "company_name": "Oscar Health",
                    "claim": "Oscar helps healthcare clients improve member engagement.",
                    "source_url": "https://www.hioscar.com/plus-oscar",
                    "source_type": "company_website",
                },
                {
                    "finding_id": "finding_2",
                    "company_name": "Oscar Health",
                    "claim": "Oscar is hiring member support roles.",
                    "source_url": "https://www.hioscar.com/careers/member-care",
                    "source_type": "job_post",
                },
            ],
        }

        message = build_review_message_from_report(report)
        message_text = json.dumps(message)
        action_block = message["blocks"][-1]
        action_ids = {element["action_id"] for element in action_block["elements"]}

        self.assertIn("Review outreach draft for Oscar Health", message["text"])
        self.assertIn("Fit score", message_text)
        self.assertIn("88", message_text)
        self.assertIn("member support triage", message_text)
        self.assertIn("https://www.hioscar.com/plus-oscar", message_text)
        self.assertEqual(action_block["type"], "actions")
        self.assertEqual(action_ids, {"approve_draft", "reject_draft", "request_changes"})
        self.assertEqual(json.loads(action_block["elements"][0]["value"])["draft_id"], "draft_123")

    def test_slack_webhook_sender_posts_message_payload(self):
        from account_intel.integrations.slack import SlackWebhookClient

        calls = []

        def fake_post(url, payload, timeout_seconds):
            calls.append({"url": url, "payload": payload, "timeout_seconds": timeout_seconds})
            return {"ok": True}

        client = SlackWebhookClient(webhook_url="https://hooks.slack.test/services/demo", post_json=fake_post)
        response = client.post_message({"text": "Review outreach draft", "blocks": []})

        self.assertEqual(response, {"ok": True})
        self.assertEqual(calls[0]["url"], "https://hooks.slack.test/services/demo")
        self.assertEqual(calls[0]["payload"]["text"], "Review outreach draft")
        self.assertEqual(calls[0]["timeout_seconds"], 10)

    def test_slack_webhook_sender_accepts_json_ok_response(self):
        from account_intel.integrations.slack import parse_slack_webhook_response

        response = parse_slack_webhook_response('{"ok":true}')

        self.assertEqual(response, {"ok": True, "response": {"ok": True}})

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

    def test_hubspot_note_payload_includes_required_timestamp(self):
        from account_intel.integrations.hubspot import HubSpotClient

        payload = HubSpotClient(token="fake-token").create_note_payload(
            "Northstar Health",
            {
                "subject": "Idea for operations workflows",
                "body": "Human-approved outreach draft.",
            },
            [],
        )

        timestamp = payload["properties"].get("hs_timestamp")
        self.assertIsInstance(timestamp, str)
        self.assertTrue(timestamp.isdigit())

    def test_hubspot_sync_finds_company_and_associates_note(self):
        from account_intel.integrations.hubspot import HubSpotClient

        calls = []
        responses = [
            {"results": [{"id": "company-123"}]},
            {"id": "note-456"},
        ]

        def fake_request(url, token, method, payload, timeout_seconds):
            calls.append(
                {
                    "url": url,
                    "token": token,
                    "method": method,
                    "payload": payload,
                    "timeout_seconds": timeout_seconds,
                }
            )
            return responses.pop(0)

        client = HubSpotClient(token="private-token", request_json=fake_request)
        note_id = client.create_note(
            "Northstar Health",
            {
                "company_domain": "northstar.example",
                "subject": "Workflow idea",
                "body": "A human-approved draft.",
            },
            ["https://northstar.example/about"],
        )

        self.assertEqual(note_id, "note-456")
        self.assertTrue(calls[0]["url"].endswith("/crm/v3/objects/companies/search"))
        self.assertEqual(
            calls[0]["payload"]["filterGroups"][0]["filters"][0],
            {"propertyName": "domain", "operator": "EQ", "value": "northstar.example"},
        )
        self.assertTrue(calls[1]["url"].endswith("/crm/v3/objects/notes"))
        association = calls[1]["payload"]["associations"][0]
        self.assertEqual(association["to"]["id"], "company-123")
        self.assertEqual(association["types"][0]["associationTypeId"], 190)

    def test_hubspot_sync_creates_company_when_domain_is_not_found(self):
        from account_intel.integrations.hubspot import HubSpotClient

        calls = []
        responses = [
            {"results": []},
            {"id": "company-new"},
            {"id": "note-new"},
        ]

        def fake_request(url, token, method, payload, timeout_seconds):
            calls.append({"url": url, "payload": payload})
            return responses.pop(0)

        client = HubSpotClient(token="private-token", request_json=fake_request)
        note_id = client.create_note(
            "New Health",
            {"company_domain": "newhealth.example", "subject": "Idea", "body": "Draft"},
            [],
        )

        self.assertEqual(note_id, "note-new")
        self.assertTrue(calls[1]["url"].endswith("/crm/v3/objects/companies"))
        self.assertEqual(
            calls[1]["payload"],
            {"properties": {"name": "New Health", "domain": "newhealth.example"}},
        )


if __name__ == "__main__":
    unittest.main()
