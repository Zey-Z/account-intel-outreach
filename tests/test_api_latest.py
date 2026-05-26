import asyncio
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


if __name__ == "__main__":
    unittest.main()
