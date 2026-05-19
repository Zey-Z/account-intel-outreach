from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any


def build_review_message(draft: dict[str, Any], company_name: str, fit_score: int) -> dict[str, Any]:
    return {
        "text": f"Review outreach draft for {company_name}",
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": f"Review: {company_name}"}},
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Fit score:*\n{fit_score}"},
                    {"type": "mrkdwn", "text": f"*Confidence:*\n{draft['confidence']:.2f}"},
                    {"type": "mrkdwn", "text": f"*Status:*\n{draft['status']}"},
                    {"type": "mrkdwn", "text": f"*Review flag:*\n{draft['review_flag']}"},
                ],
            },
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Subject:*\n{draft['subject']}"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Draft:*\n{draft['body']}"}},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Approve"},
                        "style": "primary",
                        "value": json.dumps({"draft_id": draft["draft_id"], "decision": "approved"}),
                        "action_id": "approve_draft",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Reject"},
                        "style": "danger",
                        "value": json.dumps({"draft_id": draft["draft_id"], "decision": "rejected"}),
                        "action_id": "reject_draft",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Request changes"},
                        "value": json.dumps({"draft_id": draft["draft_id"], "decision": "needs_revision"}),
                        "action_id": "request_changes",
                    },
                ],
            },
        ],
    }


def verify_slack_signature(
    signing_secret: str,
    timestamp: str,
    body: bytes,
    signature: str,
    tolerance_seconds: int = 300,
) -> bool:
    if not signing_secret or not timestamp or not signature:
        return False
    try:
        request_ts = int(timestamp)
    except ValueError:
        return False
    if abs(time.time() - request_ts) > tolerance_seconds:
        return False
    base = b"v0:" + timestamp.encode("utf-8") + b":" + body
    expected = "v0=" + hmac.new(signing_secret.encode("utf-8"), base, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
