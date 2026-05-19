import asyncio
import tempfile
import unittest
from pathlib import Path

import main


class ApiLatestRunTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
