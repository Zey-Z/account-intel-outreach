from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from account_intel.db import Database
from account_intel.env import load_local_env
from account_intel.integrations.slack import SlackWebhookClient, build_review_message_from_report
from account_intel.reporting import build_run_report


def main() -> None:
    load_local_env()
    webhook_url = os.getenv("SLACK_WEBHOOK_URL", "").strip()
    if not webhook_url:
        raise SystemExit("SLACK_WEBHOOK_URL is missing. Add it to your local .env first.")

    db = Database(os.getenv("DATABASE_URL", "sqlite:///data/account_intel.db"))
    db.initialize()
    run_id = sys.argv[1] if len(sys.argv) > 1 else db.latest_run_id()
    if not run_id:
        raise SystemExit("No run found. Create and process a run first.")

    report = build_run_report(db, run_id)
    if not report["drafts"]:
        raise SystemExit(f"Run {run_id} has no outreach draft to review.")

    message = build_review_message_from_report(report)
    response = SlackWebhookClient(webhook_url=webhook_url).post_message(message)
    if not response.get("ok"):
        raise SystemExit(f"Slack webhook returned an unexpected response: {response.get('response')}")
    print(f"sent_slack_review_for_run={run_id}")


if __name__ == "__main__":
    main()
