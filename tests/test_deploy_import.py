import os
import subprocess
import sys
import unittest
from pathlib import Path


class DeployImportTests(unittest.TestCase):
    def test_main_imports_without_pythonpath_for_render(self):
        project_root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)

        result = subprocess.run(
            [sys.executable, "-c", "import main; print(main.app.title)"],
            cwd=project_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("AI Account Intelligence", result.stdout)

    def test_scripts_import_without_pythonpath(self):
        project_root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        scripts = [
            "scripts.create_sample_run",
            "scripts.init_db",
            "scripts.run_worker",
            "scripts.send_latest_slack_review",
            "scripts.show_latest_run",
        ]

        for script in scripts:
            with self.subTest(script=script):
                result = subprocess.run(
                    [sys.executable, "-c", f"import {script}; print('ok')"],
                    cwd=project_root,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=20,
                )

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("ok", result.stdout)

    def test_docker_artifacts_define_optional_uvicorn_runtime(self):
        project_root = Path(__file__).resolve().parents[1]

        dockerfile = (project_root / "Dockerfile").read_text(encoding="utf-8")
        dockerignore = (project_root / ".dockerignore").read_text(encoding="utf-8")

        self.assertIn("FROM python:3.12-slim", dockerfile)
        self.assertIn("pip install --no-cache-dir -r requirements.txt", dockerfile)
        self.assertIn('["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]', dockerfile)
        self.assertIn(".env", dockerignore)
        self.assertIn("data/", dockerignore)
        self.assertIn(".git", dockerignore)

    def test_production_readiness_doc_covers_real_tradeoffs(self):
        project_root = Path(__file__).resolve().parents[1]

        document = (project_root / "docs" / "PRODUCTION_READINESS.md").read_text(encoding="utf-8")

        required_terms = [
            "test-gated deploy",
            "schema_migrations",
            "X-Request-Id",
            "Redis",
            "Render free tier",
            "SQLite locally",
            "no WAF/CDN",
        ]
        for term in required_terms:
            with self.subTest(term=term):
                self.assertIn(term, document)


if __name__ == "__main__":
    unittest.main()
