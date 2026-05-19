from __future__ import annotations

import os

from account_intel.db import Database


def main() -> None:
    db = Database(os.getenv("DATABASE_URL", "sqlite:///data/account_intel.db"))
    db.initialize()
    print("Database initialized.")


if __name__ == "__main__":
    main()
