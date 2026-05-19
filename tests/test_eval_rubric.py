import importlib.util
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


def load_run_eval_module():
    path = Path(__file__).resolve().parents[1] / "eval" / "run_eval.py"
    spec = importlib.util.spec_from_file_location("run_eval", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    unittest.main()
