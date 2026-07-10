import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Barrier

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class CoreWorkflowTests(unittest.TestCase):
    def test_load_healthcare_icp_profile(self):
        from account_intel.config import load_icp_profiles

        profiles = load_icp_profiles(Path("icp_profiles.yaml"))

        self.assertIn("healthcare_insurance_ops", profiles)
        profile = profiles["healthcare_insurance_ops"]
        self.assertIn("claims", " ".join(profile.pain_points).lower())
        self.assertGreaterEqual(len(profile.buying_signals), 3)

    def test_grounding_rejects_claim_not_present_in_source_text(self):
        from account_intel.grounding import ground_findings
        from account_intel.models import SourceEvidence

        findings = [
            SourceEvidence(
                claim="Acme Health uses AI to automate prior authorization.",
                source_url="https://example.com/acme",
                source_type="company_website",
                retrieved_at="2026-05-18T00:00:00Z",
                grounding_passed=False,
            )
        ]

        grounded = ground_findings(
            findings,
            {"https://example.com/acme": "Acme Health provides claims analytics for payers."},
        )

        self.assertEqual(len(grounded), 0)

    def test_writer_evidence_check_flags_unsupported_draft_fact(self):
        from account_intel.models import OutreachDraft, SourceEvidence
        from account_intel.validation import validate_writer_evidence

        findings = [
            SourceEvidence(
                claim="Northstar Health serves regional payer operations teams.",
                source_url="https://example.com/northstar",
                source_type="company_website",
                retrieved_at="2026-05-18T00:00:00Z",
                grounding_passed=True,
            )
        ]
        draft = OutreachDraft(
            subject="Reducing claim review friction",
            body="I saw Northstar Health recently raised $90M and is expanding into Europe.",
            confidence=0.82,
            review_flag="ready_for_review",
            evidence_refs=[],
        )

        updated = validate_writer_evidence(draft, findings)

        self.assertEqual(updated.review_flag, "needs_human_review")
        self.assertIn("unsupported", updated.validation_notes.lower())

    def test_grounded_fit_account_routes_to_slack_review_even_when_draft_needs_review(self):
        from account_intel.crew import AccountIntelligenceCrew
        from account_intel.models import AnalystRationale, OutreachDraft, ResearchFindings, SourceEvidence

        research = ResearchFindings(
            company_name="Oscar Health",
            domain="hioscar.com",
            findings=[
                SourceEvidence(
                    claim="Oscar Health supports member engagement and healthcare operations workflows.",
                    source_url="https://www.hioscar.com/about",
                    source_type="company_website",
                    retrieved_at="2026-05-26T00:00:00Z",
                    grounding_passed=True,
                ),
                SourceEvidence(
                    claim="+Oscar supports healthcare clients through platform-based services.",
                    source_url="https://www.hioscar.com/plus-oscar",
                    source_type="company_website",
                    retrieved_at="2026-05-26T00:00:00Z",
                    grounding_passed=True,
                ),
                SourceEvidence(
                    claim="Oscar Health hires member care roles for healthcare support teams.",
                    source_url="https://www.hioscar.com/careers/member-care",
                    source_type="job_post",
                    retrieved_at="2026-05-26T00:00:00Z",
                    grounding_passed=True,
                ),
            ],
            grounding_passed=True,
        )
        analysis = AnalystRationale(
            fit_score=65,
            pain_point_match="member support triage",
            buying_trigger="Public operations and member-care signals.",
            risk_flags=[],
            recommended_angle="AI-assisted exception triage with human approval",
            confidence=0.66,
            evidence_refs=[],
        )
        draft = OutreachDraft(
            subject="Idea for Oscar operations workflows",
            body="Human review should check this draft.",
            confidence=0.66,
            review_flag="needs_human_review",
            evidence_refs=[],
        )

        status = AccountIntelligenceCrew._status_for(research, analysis, draft)

        self.assertEqual(status, "sent_to_review")

    def test_database_run_lifecycle_and_event_logging(self):
        from account_intel.db import Database

        with tempfile.TemporaryDirectory() as tmp:
            db = Database(f"sqlite:///{Path(tmp) / 'workflow.db'}")
            db.initialize()

            run_id = db.create_run(
                triggered_by="unit-test",
                icp_profile="healthcare_insurance_ops",
                companies=[{"name": "Northstar Health", "domain": "northstar.example"}],
            )
            db.update_run_status(run_id, "researching")
            db.log_event(run_id, "research_started", {"company_count": 1})

            run = db.get_run(run_id)
            events = db.list_events(run_id)

            self.assertEqual(run["status"], "researching")
        self.assertEqual(events[0]["event_type"], "research_started")
        self.assertEqual(events[0]["payload"]["company_count"], 1)

    def test_database_claims_a_queued_run_only_once_across_workers(self):
        from account_intel.db import Database

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow.db"
            db = Database(f"sqlite:///{db_path}")
            db.initialize()
            run_id = db.create_run(
                triggered_by="concurrency-test",
                icp_profile="healthcare_insurance_ops",
                companies=[{"name": "Northstar Health", "domain": "northstar.example"}],
            )
            barrier = Barrier(2)

            def claim() -> dict | None:
                barrier.wait()
                return Database(f"sqlite:///{db_path}").claim_next_queued_run()

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _index: claim(), range(2)))

            claimed_ids = [result["run_id"] for result in results if result is not None]
            events = db.list_events(run_id)

        self.assertEqual(claimed_ids, [run_id])
        self.assertEqual(sum(result is None for result in results), 1)
        self.assertEqual([event["event_type"] for event in events], ["run_claimed"])

    def test_database_migrations_are_idempotent(self):
        from account_intel.db import Database

        with tempfile.TemporaryDirectory() as tmp:
            db = Database(f"sqlite:///{Path(tmp) / 'workflow.db'}")

            db.initialize()
            db.initialize()

            with db.connect() as conn:
                rows = conn.execute("SELECT id FROM schema_migrations ORDER BY id").fetchall()

        self.assertEqual(
            [row["id"] for row in rows],
            ["0001_init.sql", "0002_query_indexes.sql", "0003_fix_bi_view_fanout.sql"],
        )

    def test_database_migrations_apply_incrementally_in_filename_order(self):
        from account_intel.db import Database

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            migrations_dir = root / "migrations"
            migrations_dir.mkdir()
            (migrations_dir / "0001_create_probe.sql").write_text(
                """
                -- dialect: sqlite
                CREATE TABLE migration_probe (
                    id TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """,
                encoding="utf-8",
            )
            (migrations_dir / "0002_insert_probe.sql").write_text(
                """
                -- dialect: sqlite
                INSERT INTO migration_probe(id, value) VALUES ('order', 'second migration saw first table');
                """,
                encoding="utf-8",
            )
            db = Database(f"sqlite:///{root / 'workflow.db'}", migrations_dir=migrations_dir)

            db.initialize()

            with db.connect() as conn:
                value = conn.execute("SELECT value FROM migration_probe WHERE id = ?", ("order",)).fetchone()["value"]
                migration_rows = conn.execute("SELECT id FROM schema_migrations ORDER BY id").fetchall()

        self.assertEqual(value, "second migration saw first table")
        self.assertEqual(
            [row["id"] for row in migration_rows],
            ["0001_create_probe.sql", "0002_insert_probe.sql"],
        )

    def test_database_accepts_postgres_url_for_neon_deployment(self):
        from account_intel.db import Database

        db = Database("postgresql://user:pass@example.neon.tech/neondb?sslmode=require")

        self.assertEqual(db.backend, "postgres")

    def test_postgres_research_finding_uses_boolean_grounding_value(self):
        from account_intel.db import Database

        class FakePostgresDatabase(Database):
            def __init__(self):
                self.backend = "postgres"
                self.executed_parameters = []

            @contextmanager
            def connect(self):
                yield self

            def execute(self, _sql, parameters=()):
                self.executed_parameters.append(parameters)

        db = FakePostgresDatabase()
        db.save_research_findings(
            "company_1",
            [
                {
                    "claim": "Oscar Health supports payer operations workflows.",
                    "source_url": "https://example.com/oscar",
                    "source_type": "company_website",
                    "retrieved_at": "2026-05-19T00:00:00Z",
                    "grounding_passed": True,
                }
            ],
        )

        grounding_value = db.executed_parameters[0][-1]
        self.assertIs(grounding_value, True)

    def test_jsonb_fields_already_decoded_are_preserved(self):
        from account_intel.db import Database

        draft = Database._decode_draft({"evidence_refs": ["finding_1", "finding_2"]})

        self.assertEqual(draft["evidence_refs"], ["finding_1", "finding_2"])


if __name__ == "__main__":
    unittest.main()
