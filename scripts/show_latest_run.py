from __future__ import annotations

import json
import os
import sys

from account_intel.db import Database
from account_intel.reporting import build_run_report


def main() -> None:
    db = Database(os.getenv("DATABASE_URL", "sqlite:///data/account_intel.db"))
    db.initialize()
    run_id = sys.argv[1] if len(sys.argv) > 1 else latest_run_id(db)
    if not run_id:
        print("No runs found.")
        return
    print(json.dumps(build_run_report(db, run_id), indent=2))


def latest_run_id(db: Database) -> str | None:
    with db.connect() as conn:
        row = conn.execute("SELECT run_id FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()
    return str(row["run_id"]) if row else None


if __name__ == "__main__":
    main()
