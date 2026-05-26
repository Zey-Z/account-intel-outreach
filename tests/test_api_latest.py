import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main


class ApiLatestRunTests(unittest.TestCase):
    def setUp(self):
        self.original_database_url = main.DATABASE_URL
        self.original_api_key = main.API_KEY
        main.API_KEY = ""

    def tearDown(self):
        main.DATABASE_URL = self.original_database_url
        main.API_KEY = self.original_api_key

    def test_get_latest_run_returns_most_recent_run_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            main.DATABASE_URL = f"sqlite:///{Path(tmp) / 'api.db'}"

            created = asyncio.run(
                main.create_run(
                    {
                        "company_name": "Oscar Health",
                        "domain": "hioscar.com",
                        "icp_profile": "healthcare_insurance_ops",
                        "triggered_by": "unit-test",
                    }
                )
            )
            latest = asyncio.run(main.get_latest_run())

        self.assertEqual(latest["run"]["run_id"], created["run_id"])
        self.assertEqual(latest["run"]["status"], "queued")

    def test_create_run_rejects_missing_api_key_when_configured(self):
        main.API_KEY = "test-secret"

        with self.assertRaises(main.HTTPException) as caught:
            asyncio.run(
                main.create_run(
                    {
                        "company_name": "Oscar Health",
                        "domain": "hioscar.com",
                        "icp_profile": "healthcare_insurance_ops",
                    }
                )
            )

        self.assertEqual(caught.exception.status_code, 401)

    def test_create_run_accepts_matching_api_key_when_configured(self):
        with tempfile.TemporaryDirectory() as tmp:
            main.DATABASE_URL = f"sqlite:///{Path(tmp) / 'api.db'}"
            main.API_KEY = "test-secret"

            created = asyncio.run(
                main.create_run(
                    {
                        "company_name": "Oscar Health",
                        "domain": "hioscar.com",
                        "icp_profile": "healthcare_insurance_ops",
                    },
                    x_api_key="test-secret",
                )
            )

        self.assertEqual(created["status"], "queued")

    def test_latest_run_rejects_missing_api_key_when_configured(self):
        main.API_KEY = "test-secret"

        with self.assertRaises(main.HTTPException) as caught:
            asyncio.run(main.get_latest_run())

        self.assertEqual(caught.exception.status_code, 401)

    def test_worker_endpoint_rejects_missing_api_key_when_configured(self):
        main.API_KEY = "test-secret"

        with self.assertRaises(main.HTTPException) as caught:
            asyncio.run(main.process_next())

        self.assertEqual(caught.exception.status_code, 401)

    def test_worker_endpoint_runs_blocking_worker_in_thread(self):
        calls = []

        class FakeWorker:
            def __init__(self, db, icp_path):
                self.db = db
                self.icp_path = icp_path

            def process_next(self):
                calls.append("worker-called")
                return "run_123"

        async def fake_to_thread(func):
            calls.append("to-thread-called")
            return func()

        with patch("main.Worker", FakeWorker):
            with patch("main.to_thread", fake_to_thread):
                response = asyncio.run(main.process_next())

        self.assertEqual(response, {"processed_run_id": "run_123"})
        self.assertEqual(calls, ["to-thread-called", "worker-called"])

    def test_send_latest_slack_review_posts_latest_report_message(self):
        from account_intel.db import Database
        from account_intel.worker import Worker

        calls = []

        def fake_post_message(self, message):
            calls.append({"webhook_url": self.webhook_url, "message": message})
            return {"ok": True, "response": "ok"}

        with tempfile.TemporaryDirectory() as tmp:
            main.DATABASE_URL = f"sqlite:///{Path(tmp) / 'api.db'}"
            main.API_KEY = "test-secret"
            db = Database(main.DATABASE_URL)
            db.initialize()
            run_id = db.create_run(
                triggered_by="unit-test",
                icp_profile="healthcare_insurance_ops",
                companies=[{"name": "Northstar Health", "domain": "northstar.example"}],
            )
            Worker(db=db, offline=True).process_next()

            with patch.dict(os.environ, {"SLACK_WEBHOOK_URL": "https://hooks.slack.test/services/demo"}):
                with patch("account_intel.integrations.slack.SlackWebhookClient.post_message", fake_post_message):
                    response = asyncio.run(main.send_latest_slack_review(x_api_key="test-secret"))

        self.assertEqual(response["run_id"], run_id)
        self.assertTrue(response["sent"])
        self.assertEqual(calls[0]["webhook_url"], "https://hooks.slack.test/services/demo")
        self.assertIn("Review outreach draft", calls[0]["message"]["text"])

    def test_slack_interaction_falls_back_to_response_url_update(self):
        from account_intel.db import Database
        from account_intel.worker import Worker

        calls = []

        def fake_post_message(self, message):
            calls.append({"webhook_url": self.webhook_url, "message": message})
            return {"ok": True, "response": "ok"}

        class FakeRequest:
            def __init__(self, payload):
                self.payload = payload

            async def body(self):
                return b"payload={}"

            async def form(self):
                return {"payload": json.dumps(self.payload)}

        with tempfile.TemporaryDirectory() as tmp:
            main.DATABASE_URL = f"sqlite:///{Path(tmp) / 'api.db'}"
            db = Database(main.DATABASE_URL)
            db.initialize()
            run_id = db.create_run(
                triggered_by="unit-test",
                icp_profile="healthcare_insurance_ops",
                companies=[{"name": "Northstar Health", "domain": "northstar.example"}],
            )
            Worker(db=db, offline=True).process_next()
            draft = db.list_outreach_drafts(run_id)[0]
            payload = {
                "response_url": "https://hooks.slack.test/interaction-response",
                "user": {"id": "U_TEST", "username": "reviewer"},
                "message": {
                    "blocks": [
                        {"type": "section", "text": {"type": "mrkdwn", "text": "Review card"}},
                        {
                            "type": "actions",
                            "elements": [
                                {
                                    "type": "button",
                                    "text": {"type": "plain_text", "text": "Approve"},
                                    "action_id": "approve_draft",
                                }
                            ],
                        },
                    ]
                },
                "actions": [
                    {
                        "action_id": "approve_draft",
                        "value": json.dumps({"draft_id": draft["draft_id"], "decision": "approved"}),
                    }
                ],
            }

            with patch.dict(os.environ, {"SLACK_SIGNING_SECRET": ""}):
                with patch("account_intel.integrations.slack.SlackWebhookClient.post_message", fake_post_message):
                    response = asyncio.run(
                        main.slack_interactions(
                            FakeRequest(payload),
                            x_slack_request_timestamp=None,
                            x_slack_signature=None,
                        )
                    )
            response_body = json.loads(response.body.decode("utf-8"))
            updated = db.get_outreach_draft(draft["draft_id"])
            events = db.list_events(run_id)

        self.assertEqual(updated["status"], "approved")
        self.assertTrue(calls)
        self.assertEqual(calls[0]["webhook_url"], "https://hooks.slack.test/interaction-response")
        self.assertTrue(calls[0]["message"]["replace_original"])
        self.assertNotIn("actions", [block["type"] for block in calls[0]["message"]["blocks"]])
        self.assertEqual(response_body["response_type"], "ephemeral")
        self.assertIn("Decision recorded: approved", response_body["text"])
        slack_events = [event for event in events if event["event_type"] == "slack_review_message_update"]
        self.assertEqual(slack_events[0]["payload"]["method"], "response_url")
        self.assertTrue(slack_events[0]["payload"]["ok"])

    def test_slack_interaction_prefers_chat_update_when_bot_token_is_configured(self):
        from account_intel.db import Database
        from account_intel.worker import Worker

        calls = []

        def fake_update_message(self, channel_id, message_ts, message):
            calls.append(
                {
                    "token": self.bot_token,
                    "channel_id": channel_id,
                    "message_ts": message_ts,
                    "message": message,
                }
            )
            return {"ok": True, "response": {"ok": True, "ts": message_ts}}

        class FakeRequest:
            def __init__(self, payload):
                self.payload = payload

            async def body(self):
                return b"payload={}"

            async def form(self):
                return {"payload": json.dumps(self.payload)}

        with tempfile.TemporaryDirectory() as tmp:
            main.DATABASE_URL = f"sqlite:///{Path(tmp) / 'api.db'}"
            db = Database(main.DATABASE_URL)
            db.initialize()
            run_id = db.create_run(
                triggered_by="unit-test",
                icp_profile="healthcare_insurance_ops",
                companies=[{"name": "Northstar Health", "domain": "northstar.example"}],
            )
            Worker(db=db, offline=True).process_next()
            draft = db.list_outreach_drafts(run_id)[0]
            payload = {
                "response_url": "https://hooks.slack.test/interaction-response",
                "user": {"id": "U_TEST", "username": "reviewer"},
                "channel": {"id": "C_TEST"},
                "message": {
                    "ts": "1710000000.123456",
                    "blocks": [
                        {"type": "section", "text": {"type": "mrkdwn", "text": "Review card"}},
                        {"type": "actions", "elements": []},
                    ],
                },
                "actions": [
                    {
                        "action_id": "approve_draft",
                        "value": json.dumps({"draft_id": draft["draft_id"], "decision": "approved"}),
                    }
                ],
            }

            with patch.dict(os.environ, {"SLACK_SIGNING_SECRET": "", "SLACK_BOT_TOKEN": "test-bot-token"}):
                with patch("account_intel.integrations.slack.SlackWebApiClient.update_message", fake_update_message):
                    response = asyncio.run(
                        main.slack_interactions(
                            FakeRequest(payload),
                            x_slack_request_timestamp=None,
                            x_slack_signature=None,
                        )
                    )
            response_body = json.loads(response.body.decode("utf-8"))
            events = db.list_events(run_id)

        self.assertEqual(calls[0]["token"], "test-bot-token")
        self.assertEqual(calls[0]["channel_id"], "C_TEST")
        self.assertEqual(calls[0]["message_ts"], "1710000000.123456")
        self.assertNotIn("actions", [block["type"] for block in calls[0]["message"]["blocks"]])
        self.assertEqual(response_body["response_type"], "ephemeral")
        slack_events = [event for event in events if event["event_type"] == "slack_review_message_update"]
        self.assertEqual(slack_events[0]["payload"]["method"], "chat.update")
        self.assertTrue(slack_events[0]["payload"]["ok"])


if __name__ == "__main__":
    unittest.main()
