from __future__ import annotations

import os
from pathlib import Path

from account_intel.db import Database
from account_intel.worker import Worker


def main() -> None:
    db = Database(os.getenv("DATABASE_URL", "sqlite:///data/account_intel.db"))
    db.initialize()
    worker = Worker(db=db, icp_path=Path(os.getenv("ICP_PROFILES_PATH", "icp_profiles.yaml")))
    run_id = worker.process_next()
    print(f"processed_run_id={run_id}")


if __name__ == "__main__":
    main()
