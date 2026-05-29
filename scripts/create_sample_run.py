from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from account_intel.db import Database
from account_intel.env import load_local_env


def main() -> None:
    load_local_env()
    db = Database(os.getenv("DATABASE_URL", "sqlite:///data/account_intel.db"))
    db.initialize()
    run_id = db.create_run(
        triggered_by="sample",
        icp_profile="healthcare_insurance_ops",
        companies=[
            {"name": "Northstar Health", "domain": "northstar.example"},
            {"name": "PayerOps Cloud", "domain": "payerops.example"},
        ],
    )
    print(f"run_id={run_id}")


if __name__ == "__main__":
    main()
