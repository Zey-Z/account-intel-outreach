import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class FakeResponse:
    def __init__(self, content: str):
        self.content = content.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self.content


class PowerBIExportTests(unittest.TestCase):
    def test_export_powerbi_snapshot_writes_validated_views_and_manifest(self):
        from account_intel.powerbi_export import REPORT_COLUMNS, export_powerbi_snapshot

        payloads = {}
        for view_name, columns in REPORT_COLUMNS.items():
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=columns)
            writer.writeheader()
            writer.writerow({column: f"{view_name}-{column}" for column in columns})
            payloads[view_name] = buffer.getvalue()

        def fake_opener(request, timeout):
            view_name = request.full_url.rsplit("/", 1)[-1].removesuffix(".csv")
            self.assertEqual(request.headers["X-api-key"], "test-secret")
            self.assertEqual(timeout, 60)
            return FakeResponse(payloads[view_name])

        with tempfile.TemporaryDirectory() as tmp:
            manifest = export_powerbi_snapshot(
                "https://example.test/",
                "test-secret",
                tmp,
                opener=fake_opener,
            )
            manifest_file = json.loads((Path(tmp) / "snapshot_manifest.json").read_text())

            for view_name in REPORT_COLUMNS:
                self.assertTrue((Path(tmp) / f"{view_name}.csv").exists())
                self.assertEqual(manifest["views"][view_name], 1)
            self.assertEqual(manifest_file["source"], "https://example.test")

    def test_export_rejects_an_unexpected_schema(self):
        from account_intel.powerbi_export import fetch_report_csv

        def fake_opener(request, timeout):
            return FakeResponse("wrong,column\n1,2\n")

        with self.assertRaisesRegex(ValueError, "Unexpected columns"):
            fetch_report_csv(
                "https://example.test",
                "test-secret",
                "dashboard_runs_view",
                opener=fake_opener,
            )
