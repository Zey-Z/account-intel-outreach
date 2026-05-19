from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from account_intel.db import Database
from account_intel.worker import Worker


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/account_intel.db")
ICP_PATH = Path(os.getenv("ICP_PROFILES_PATH", "icp_profiles.yaml"))


def get_db() -> Database:
    db = Database(DATABASE_URL)
    db.initialize()
    return db


try:
    from fastapi import FastAPI, Header, HTTPException, Request
    from fastapi.responses import JSONResponse

    app = FastAPI(title="AI Account Intelligence & Outreach Ops System")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/runs", status_code=202)
    async def create_run(payload: dict[str, Any]) -> dict[str, Any]:
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

    @app.get("/runs/{run_id}")
    async def get_run(run_id: str) -> dict[str, Any]:
        db = get_db()
        return {"run": db.get_run(run_id), "events": db.list_events(run_id)}

    @app.post("/worker/process-next")
    async def process_next() -> dict[str, Any]:
        db = get_db()
        worker = Worker(db=db, icp_path=ICP_PATH)
        run_id = worker.process_next()
        return {"processed_run_id": run_id}

    @app.post("/slack/interactions")
    async def slack_interactions(
        request: Request,
        x_slack_request_timestamp: str | None = Header(default=None),
        x_slack_signature: str | None = Header(default=None),
    ) -> JSONResponse:
        from account_intel.integrations.slack import verify_slack_signature

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
        return JSONResponse({"text": f"Decision recorded: {value['decision']}"})

except ModuleNotFoundError:
    app = None
