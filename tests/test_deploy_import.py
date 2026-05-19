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


if __name__ == "__main__":
    unittest.main()
