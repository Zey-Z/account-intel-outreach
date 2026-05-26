from __future__ import annotations

import json
import hmac
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from account_intel.db import Database
from account_intel.env import load_local_env
from account_intel.reporting import build_run_report
from account_intel.worker import Worker


load_local_env(ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/account_intel.db")
ICP_PATH = Path(os.getenv("ICP_PROFILES_PATH", "icp_profiles.yaml"))
API_KEY = os.getenv("ACCOUNT_INTEL_API_KEY", "")


def get_db() -> Database:
    db = Database(DATABASE_URL)
    db.initialize()
    return db


try:
    from fastapi import FastAPI, Header, HTTPException, Request
    from fastapi.responses import JSONResponse

    app = FastAPI(title="AI Account Intelligence & Outreach Ops System")

    def require_api_key(x_api_key: str | None) -> None:
        if not API_KEY:
            return
        if not isinstance(x_api_key, str) or not hmac.compare_digest(x_api_key, API_KEY):
            raise HTTPException(status_code=401, detail="Invalid or missing API key.")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/runs", status_code=202)
    async def create_run(payload: dict[str, Any], x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
        require_api_key(x_api_key)
        companies = payload.get("companies")
        if not companies and payload.get("company_name"):
            companies = [{"name": payload["company_name"], "domain": payload.get("domain")}]
        if not companies:
            raise HTTPException(status_code=400, detail="Provide companies or company_name.")
        db = get_db()
        run_id = db.create_run(
            triggered_by=payload.get("triggered_by", "api"),
            icp_profile=payload.get("icp_profile", "healthcare_insurance_ops"),
            companies=companies,
        )
        return {"run_id": run_id, "status": "queued"}

    @app.get("/runs/latest")
    async def get_latest_run(x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
        require_api_key(x_api_key)
        db = get_db()
        run_id = db.latest_run_id()
        if not run_id:
            raise HTTPException(status_code=404, detail="No runs found.")
        return build_run_report(db, run_id)

    @app.get("/runs/{run_id}")
    async def get_run(run_id: str, x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
        require_api_key(x_api_key)
        db = get_db()
        return {"run": db.get_run(run_id), "events": db.list_events(run_id)}

    @app.post("/worker/process-next")
    async def process_next(x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
        require_api_key(x_api_key)
        db = get_db()
        worker = Worker(db=db, icp_path=ICP_PATH)
        run_id = worker.process_next()
        return {"processed_run_id": run_id}

    @app.post("/slack/send-latest-review")
    async def send_latest_slack_review(x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
        from account_intel.integrations.slack import SlackWebhookClient, build_review_message_from_report

        require_api_key(x_api_key)
        webhook_url = os.getenv("SLACK_WEBHOOK_URL", "").strip()
        if not webhook_url:
            raise HTTPException(status_code=400, detail="SLACK_WEBHOOK_URL is not configured.")
        db = get_db()
        run_id = db.latest_run_id()
        if not run_id:
            raise HTTPException(status_code=404, detail="No runs found.")
        report = build_run_report(db, run_id)
        if not report["drafts"]:
            raise HTTPException(status_code=400, detail="Latest run has no draft to review.")
        message = build_review_message_from_report(report)
        response = SlackWebhookClient(webhook_url=webhook_url).post_message(message)
        if not response.get("ok"):
            raise HTTPException(status_code=502, detail=f"Slack webhook failed: {response.get('response')}")
        return {"sent": True, "run_id": run_id}

    @app.post("/slack/interactions")
    async def slack_interactions(
        request: Request,
        x_slack_request_timestamp: str | None = Header(default=None),
        x_slack_signature: str | None = Header(default=None),
    ) -> JSONResponse:
        from account_intel.integrations.slack import (
            SlackWebApiClient,
            SlackWebhookClient,
            build_review_decision_update,
            verify_slack_signature,
        )

        body = await request.body()
        secret = os.getenv("SLACK_SIGNING_SECRET", "")
        if secret and not verify_slack_signature(secret, x_slack_request_timestamp or "", body, x_slack_signature or ""):
            raise HTTPException(status_code=401, detail="Invalid Slack signature.")
        form = await request.form()
        payload = json.loads(str(form.get("payload", "{}")))
        action = payload.get("actions", [{}])[0]
        value = json.loads(action.get("value", "{}"))
        user = payload.get("user", {}).get("username") or payload.get("user", {}).get("id", "slack-user")
        db = get_db()
        worker = Worker(db=db, icp_path=ICP_PATH)
        worker.apply_review_decision(
            draft_id=value["draft_id"],
            decision=value["decision"],
            reviewed_by=user,
            revision_note=value.get("revision_note"),
        )
        update_message = build_review_decision_update(payload, value["decision"], user)
        run_id = db.get_run_id_for_draft(value["draft_id"])
        update_result = _update_slack_review_message(
            payload=payload,
            update_message=update_message,
            web_api_client_class=SlackWebApiClient,
            webhook_client_class=SlackWebhookClient,
        )
        db.log_event(run_id, "slack_review_message_update", update_result)
        return JSONResponse(
            {
                "response_type": "ephemeral",
                "replace_original": False,
                "text": f"Decision recorded: {value['decision']}",
            }
        )

except ModuleNotFoundError:
    app = None


def _update_slack_review_message(
    payload: dict[str, Any],
    update_message: dict[str, Any],
    web_api_client_class: Any,
    webhook_client_class: Any,
) -> dict[str, Any]:
    channel_id = _slack_channel_id(payload)
    message_ts = _slack_message_ts(payload)
    bot_token = os.getenv("SLACK_BOT_TOKEN", "").strip()
    response_url = str(payload.get("response_url") or "").strip()
    result = {
        "method": "none",
        "ok": False,
        "has_bot_token": bool(bot_token),
        "has_message_target": bool(channel_id and message_ts),
        "has_response_url": bool(response_url),
    }
    chat_update_error = None
    if bot_token and channel_id and message_ts:
        try:
            response = web_api_client_class(bot_token=bot_token).update_message(channel_id, message_ts, update_message)
            result.update({"method": "chat.update", "ok": bool(response.get("ok"))})
            if result["ok"]:
                return result
            chat_update_error = str(response.get("response"))
        except Exception as exc:
            chat_update_error = str(exc)
    if response_url:
        try:
            response = webhook_client_class(webhook_url=response_url).post_message(update_message)
            result.update({"method": "response_url", "ok": bool(response.get("ok"))})
            if chat_update_error:
                result["chat_update_error"] = chat_update_error
            if not result["ok"]:
                result["response_url_error"] = str(response.get("response"))
            return result
        except Exception as exc:
            result.update({"method": "response_url", "ok": False, "response_url_error": str(exc)})
            if chat_update_error:
                result["chat_update_error"] = chat_update_error
            return result
    if chat_update_error:
        result["chat_update_error"] = chat_update_error
    return result


def _slack_channel_id(payload: dict[str, Any]) -> str | None:
    channel = payload.get("channel") or {}
    container = payload.get("container") or {}
    return channel.get("id") or container.get("channel_id")


def _slack_message_ts(payload: dict[str, Any]) -> str | None:
    message = payload.get("message") or {}
    container = payload.get("container") or {}
    return message.get("ts") or container.get("message_ts")
