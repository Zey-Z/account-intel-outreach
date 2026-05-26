from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any
from urllib import request


class SlackWebhookClient:
    def __init__(self, webhook_url: str, post_json: Any | None = None):
        if not webhook_url:
            raise ValueError("Slack webhook URL is required.")
        self.webhook_url = webhook_url
        self.post_json = post_json or _post_json

    def post_message(self, message: dict[str, Any], timeout_seconds: int = 10) -> dict[str, Any]:
        return self.post_json(self.webhook_url, message, timeout_seconds)


def build_review_message_from_report(report: dict[str, Any]) -> dict[str, Any]:
    """Build a Slack Block Kit review message from one run report."""
    draft = report["drafts"][0]
    analysis = _analysis_for_company(report, draft["company_name"])
    findings = _findings_for_draft(report, draft)
    source_lines = "\n".join(_format_finding_line(finding) for finding in findings[:5])
    if not source_lines:
        source_lines = "No source evidence available."
    risk_flags = analysis.get("risk_flags") or []
    risk_text = "\n".join(f"- {flag}" for flag in risk_flags) if risk_flags else "No risk flags."

    return {
        "text": f"Review outreach draft for {draft['company_name']}",
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": f"Review: {draft['company_name']}"}},
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Fit score:*\n{analysis['fit_score']}"},
                    {"type": "mrkdwn", "text": f"*Confidence:*\n{analysis['confidence']:.2f}"},
                    {"type": "mrkdwn", "text": f"*Status:*\n{draft['status']}"},
                    {"type": "mrkdwn", "text": f"*Review flag:*\n{draft['review_flag']}"},
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Pain point match:*\n{analysis['pain_point_match']}\n\n"
                        f"*Buying trigger:*\n{analysis['buying_trigger']}\n\n"
                        f"*Recommended angle:*\n{analysis['recommended_angle']}"
                    ),
                },
            },
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Source evidence:*\n{source_lines}"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Risk flags:*\n{risk_text}"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Subject:*\n{draft['subject']}"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Draft:*\n{draft.get('body', '')}"}},
            _review_actions_block(draft["draft_id"]),
        ],
    }


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


def build_review_decision_update(payload: dict[str, Any], decision: str, reviewed_by: str) -> dict[str, Any]:
    """Build the replacement message Slack should show after a review button click."""
    message = payload.get("message", {})
    original_blocks = message.get("blocks") or []
    blocks = [block for block in original_blocks if block.get("type") != "actions"]
    decision_text = (
        f"*Decision recorded:* `{decision}`\n"
        f"*Reviewer:* `{reviewed_by}`\n"
        "The review buttons were removed because this draft already has a decision."
    )
    blocks.extend(
        [
            {"type": "divider"},
            {"type": "section", "text": {"type": "mrkdwn", "text": decision_text}},
        ]
    )
    return {
        "replace_original": True,
        "text": f"Decision recorded: {decision}",
        "blocks": blocks,
    }


def _analysis_for_company(report: dict[str, Any], company_name: str) -> dict[str, Any]:
    for analysis in report.get("analysis", []):
        if analysis.get("company_name") == company_name:
            return analysis
    raise ValueError(f"No analysis found for company: {company_name}")


def _findings_for_draft(report: dict[str, Any], draft: dict[str, Any]) -> list[dict[str, Any]]:
    refs = set(draft.get("evidence_refs") or [])
    company_name = draft["company_name"]
    findings = [
        finding
        for finding in report.get("findings", [])
        if finding.get("company_name") == company_name and (not refs or finding.get("finding_id") in refs)
    ]
    if findings:
        return findings
    return [finding for finding in report.get("findings", []) if finding.get("company_name") == company_name]


def _format_finding_line(finding: dict[str, Any]) -> str:
    claim = _truncate(str(finding.get("claim", "")), 150)
    url = str(finding.get("source_url", ""))
    source_type = str(finding.get("source_type", "source"))
    return f"- {claim} (<{url}|{source_type}>)"


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _review_actions_block(draft_id: str) -> dict[str, Any]:
    return {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Approve"},
                "style": "primary",
                "value": json.dumps({"draft_id": draft_id, "decision": "approved"}),
                "action_id": "approve_draft",
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Reject"},
                "style": "danger",
                "value": json.dumps({"draft_id": draft_id, "decision": "rejected"}),
                "action_id": "reject_draft",
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Request changes"},
                "value": json.dumps({"draft_id": draft_id, "decision": "needs_revision"}),
                "action_id": "request_changes",
            },
        ],
    }


def _post_json(url: str, payload: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=timeout_seconds) as response:
        response_body = response.read().decode("utf-8")
    return {"ok": response_body.strip().lower() == "ok", "response": response_body}


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
