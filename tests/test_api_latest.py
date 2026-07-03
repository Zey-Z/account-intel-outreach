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
        if hasattr(main, "reset_db_singleton"):
            main.reset_db_singleton()

    def tearDown(self):
        main.DATABASE_URL = self.original_database_url
        main.API_KEY = self.original_api_key
        if hasattr(main, "_WORKER_POLL_TASK"):
            main._WORKER_POLL_TASK = None
        if hasattr(main, "reset_db_singleton"):
            main.reset_db_singleton()

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

    def test_get_db_reuses_singleton_until_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            main.DATABASE_URL = f"sqlite:///{Path(tmp) / 'api.db'}"
            main.reset_db_singleton()

            first = main.get_db()
            second = main.get_db()
            main.reset_db_singleton()
            third = main.get_db()

        self.assertIs(first, second)
        self.assertIsNot(first, third)

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

    def test_runtime_status_reports_safe_runtime_configuration(self):
        main.API_KEY = "test-secret"

        with patch.dict(
            os.environ,
            {
                "AGENT_RUNTIME": "crewai",
                "RESEARCH_MODE": "tavily",
                "OPENAI_API_KEY": "test-openai-key",
                "TAVILY_API_KEY": "test-tavily-key",
                "RENDER_GIT_COMMIT": "abc123",
            },
        ):
            response = asyncio.run(main.runtime_status(x_api_key="test-secret"))

        self.assertEqual(response["agent_runtime"], "crewai")
        self.assertEqual(response["research_mode"], "tavily")
        self.assertTrue(response["openai_api_key_configured"])
        self.assertTrue(response["tavily_api_key_configured"])
        self.assertEqual(response["render_git_commit"], "abc123")
        self.assertNotIn("test-openai-key", str(response))

    def test_report_csv_endpoint_returns_whitelisted_view_as_csv(self):
        from account_intel.db import Database
        from account_intel.worker import Worker

        with tempfile.TemporaryDirectory() as tmp:
            main.DATABASE_URL = f"sqlite:///{Path(tmp) / 'api.db'}"
            main.API_KEY = "test-secret"
            db = Database(main.DATABASE_URL)
            db.initialize()
            db.create_run(
                triggered_by="unit-test",
                icp_profile="healthcare_insurance_ops",
                companies=[{"name": "Northstar Health", "domain": "northstar.example"}],
            )
            Worker(db=db, offline=True).process_next()

            response = asyncio.run(main.get_report_csv("lead_runs_view", x_api_key="test-secret"))

        body = response.body.decode("utf-8")
        self.assertEqual(response.media_type, "text/csv")
        self.assertIn("run_id,icp_profile,status", body)
        self.assertIn("healthcare_insurance_ops", body)

    def test_report_csv_endpoint_rejects_non_whitelisted_view(self):
        main.API_KEY = "test-secret"

        with self.assertRaises(main.HTTPException) as caught:
            asyncio.run(main.get_report_csv("runs", x_api_key="test-secret"))

        self.assertEqual(caught.exception.status_code, 404)

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

    def test_worker_poller_startup_is_disabled_by_default(self):
        calls = []

        def fake_create_task(coro):
            calls.append(coro)
            coro.close()
            return object()

        with patch.dict(os.environ, {"WORKER_POLL_SECONDS": "0"}):
            with patch("main.asyncio.create_task", fake_create_task):
                asyncio.run(main.start_worker_poller())

        self.assertEqual(calls, [])

    def test_worker_poller_startup_schedules_background_task_when_enabled(self):
        calls = []

        class FakeTask:
            def done(self):
                return False

        def fake_create_task(coro):
            calls.append(coro)
            coro.close()
            return FakeTask()

        with patch.dict(os.environ, {"WORKER_POLL_SECONDS": "5"}):
            with patch("main.asyncio.create_task", fake_create_task):
                asyncio.run(main.start_worker_poller())

        self.assertEqual(len(calls), 1)
        self.assertIsNotNone(main._WORKER_POLL_TASK)

    def test_worker_poller_once_runs_worker_in_thread(self):
        calls = []

        class FakeWorker:
            def __init__(self, db, icp_path):
                self.db = db
                self.icp_path = icp_path

            def process_next(self):
                calls.append("worker-called")
                return None

        async def fake_to_thread(func):
            calls.append("to-thread-called")
            return func()

        with patch("main.Worker", FakeWorker):
            with patch("main.to_thread", fake_to_thread):
                result = asyncio.run(main.worker_poll_once())

        self.assertIsNone(result)
        self.assertEqual(calls, ["to-thread-called", "worker-called"])

    def test_crm_sync_approved_endpoint_requires_api_key_and_returns_sync_result(self):
        calls = []

        class FakeWorker:
            def __init__(self, db, icp_path):
                self.db = db
                self.icp_path = icp_path

            def sync_approved_drafts(self):
                calls.append("sync-called")
                return {"synced": ["draft_1"], "failed": ["draft_2"]}

        main.API_KEY = "test-secret"

        with self.assertRaises(main.HTTPException) as caught:
            asyncio.run(main.sync_approved_crm_drafts())

        with patch("main.Worker", FakeWorker):
            response = asyncio.run(main.sync_approved_crm_drafts(x_api_key="test-secret"))

        self.assertEqual(caught.exception.status_code, 401)
        self.assertEqual(response, {"synced": ["draft_1"], "failed": ["draft_2"]})
        self.assertEqual(calls, ["sync-called"])

    def test_retry_failed_run_requeues_and_logs_event(self):
        from account_intel.db import Database

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
            db.update_run_status(run_id, "failed")

            response = asyncio.run(main.retry_run(run_id, x_api_key="test-secret"))
            run = db.get_run(run_id)
            events = db.list_events(run_id)

        self.assertEqual(response, {"run_id": run_id, "status": "queued"})
        self.assertEqual(run["status"], "queued")
        self.assertTrue(any(event["event_type"] == "run_requeued" for event in events))

    def test_retry_run_rejects_non_failed_or_exhausted_runs(self):
        from account_intel.db import Database

        with tempfile.TemporaryDirectory() as tmp:
            main.DATABASE_URL = f"sqlite:///{Path(tmp) / 'api.db'}"
            main.API_KEY = "test-secret"
            db = Database(main.DATABASE_URL)
            db.initialize()
            queued_run_id = db.create_run(
                triggered_by="unit-test",
                icp_profile="healthcare_insurance_ops",
                companies=[{"name": "Northstar Health", "domain": "northstar.example"}],
            )
            exhausted_run_id = db.create_run(
                triggered_by="unit-test",
                icp_profile="healthcare_insurance_ops",
                companies=[{"name": "PayerOps Cloud", "domain": "payerops.example"}],
            )
            db.update_run_status(exhausted_run_id, "failed")
            db.increment_retry(exhausted_run_id)
            db.increment_retry(exhausted_run_id)
            db.increment_retry(exhausted_run_id)

            with self.assertRaises(main.HTTPException) as queued_error:
                asyncio.run(main.retry_run(queued_run_id, x_api_key="test-secret"))
            with self.assertRaises(main.HTTPException) as exhausted_error:
                asyncio.run(main.retry_run(exhausted_run_id, x_api_key="test-secret"))

        self.assertEqual(queued_error.exception.status_code, 409)
        self.assertEqual(exhausted_error.exception.status_code, 409)

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
