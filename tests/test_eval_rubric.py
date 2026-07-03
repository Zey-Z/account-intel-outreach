import importlib.util
import tempfile
import unittest
from pathlib import Path


class EvalRubricTests(unittest.TestCase):
    def test_rubric_checker_reports_score_route_and_term_failures(self):
        run_eval = load_run_eval_module()

        result = run_eval.evaluate_company_rubric(
            company_name="Northstar Health",
            expected={
                "min_fit_score": 80,
                "must_route_to": "sent_to_review",
                "required_terms": ["claims", "payer", "operations"],
            },
            actual={
                "fit_score": 72,
                "status": "archived",
                "text": "claims workflow automation",
            },
        )

        self.assertFalse(result["passed"])
        self.assertEqual(result["company"], "Northstar Health")
        self.assertIn("fit_score 72 < expected 80", result["failures"])
        self.assertIn("status archived != expected sent_to_review", result["failures"])
        self.assertIn("missing required terms: payer, operations", result["failures"])

    def test_load_company_actuals_includes_per_company_grounding_rate(self):
        from account_intel.db import Database
        from account_intel.worker import Worker

        run_eval = load_run_eval_module()

        with tempfile.TemporaryDirectory() as tmp:
            db = Database(f"sqlite:///{Path(tmp) / 'eval.db'}")
            db.initialize()
            run_id = db.create_run(
                triggered_by="unit-test",
                icp_profile="healthcare_insurance_ops",
                companies=[{"name": "Northstar Health", "domain": "northstar.example"}],
            )
            Worker(db=db, icp_path=Path("icp_profiles.yaml"), offline=True).process_next()

            actuals = run_eval.load_company_actuals(db, run_id)

        self.assertEqual(actuals["Northstar Health"]["grounding_rate"], 1.0)


def load_run_eval_module():
    path = Path(__file__).resolve().parents[1] / "eval" / "run_eval.py"
    spec = importlib.util.spec_from_file_location("run_eval", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    unittest.main()
