from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from account_intel.db import Database
from account_intel.env import load_local_env
from account_intel.reporting import build_run_report


def main() -> None:
    load_local_env()
    db = Database(os.getenv("DATABASE_URL", "sqlite:///data/account_intel.db"))
    db.initialize()
    run_id = sys.argv[1] if len(sys.argv) > 1 else db.latest_run_id()
    if not run_id:
        print("No runs found.")
        return
    print(json.dumps(build_run_report(db, run_id), indent=2))

if __name__ == "__main__":
    main()
