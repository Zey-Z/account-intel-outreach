from __future__ import annotations

import os

from account_intel.db import Database


def main() -> None:
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
