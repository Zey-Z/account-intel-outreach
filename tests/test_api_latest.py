import asyncio
import tempfile
import unittest
from pathlib import Path

import main


class ApiLatestRunTests(unittest.TestCase):
    def setUp(self):
        self.original_database_url = main.DATABASE_URL
        self.original_api_key = main.API_KEY

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


if __name__ == "__main__":
    unittest.main()
