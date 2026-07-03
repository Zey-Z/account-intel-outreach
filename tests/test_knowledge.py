import tempfile
import unittest
from pathlib import Path


class KnowledgeTests(unittest.TestCase):
    def test_load_knowledge_snippets_returns_empty_string_when_directory_missing(self):
        from account_intel.knowledge import load_knowledge_snippets

        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing"

            snippets = load_knowledge_snippets(missing)

        self.assertEqual(snippets, "")

    def test_load_knowledge_snippets_concatenates_approved_writer_guidance_with_cap(self):
        from account_intel.knowledge import load_knowledge_snippets

        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "approved_messaging.md").write_text("A" * 700, encoding="utf-8")
            (directory / "product_positioning.md").write_text("B" * 700, encoding="utf-8")
            (directory / "objection_handling.md").write_text("C" * 700, encoding="utf-8")
            (directory / "industry_pain_points.md").write_text("SHOULD NOT LOAD", encoding="utf-8")

            snippets = load_knowledge_snippets(directory)

        self.assertLessEqual(len(snippets), 1500)
        self.assertIn("A", snippets)
        self.assertIn("B", snippets)
        self.assertIn("C", snippets)
        self.assertNotIn("SHOULD NOT LOAD", snippets)


if __name__ == "__main__":
    unittest.main()
