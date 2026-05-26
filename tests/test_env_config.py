import os
import tempfile
import unittest
from pathlib import Path


class EnvConfigTests(unittest.TestCase):
    def test_load_local_env_reads_dotenv_file_without_overriding_existing_values(self):
        from account_intel.env import load_local_env

        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "RESEARCH_MODE=tavily\n"
                "TAVILY_API_KEY=test-tavily-key\n"
                "DATABASE_URL=sqlite:///from-env-file.db\n",
                encoding="utf-8",
            )

            original_database_url = os.environ.get("DATABASE_URL")
            try:
                os.environ["DATABASE_URL"] = "sqlite:///already-set.db"
                os.environ.pop("RESEARCH_MODE", None)
                os.environ.pop("TAVILY_API_KEY", None)

                load_local_env(env_path)

                self.assertEqual(os.environ["RESEARCH_MODE"], "tavily")
                self.assertEqual(os.environ["TAVILY_API_KEY"], "test-tavily-key")
                self.assertEqual(os.environ["DATABASE_URL"], "sqlite:///already-set.db")
            finally:
                for key in ("RESEARCH_MODE", "TAVILY_API_KEY", "DATABASE_URL"):
                    os.environ.pop(key, None)
                if original_database_url is not None:
                    os.environ["DATABASE_URL"] = original_database_url


if __name__ == "__main__":
    unittest.main()
