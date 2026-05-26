from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator, Protocol


VALID_STATUSES = {
    "queued",
    "researching",
    "research_completed",
    "analysis_completed",
    "draft_created",
    "validation_failed",
    "sent_to_review",
    "approved",
    "rejected",
    "needs_revision",
    "needs_human_research",
    "synced_to_crm",
    "archived",
    "failed",
}


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def decode_json_value(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value


class Database:
    def __init__(self, url: str):
        self.url = url
        if url.startswith("sqlite:///"):
            self.backend = "sqlite"
            self.path = Path(url.removeprefix("sqlite:///"))
        elif url.startswith(("postgresql://", "postgres://")):
            self.backend = "postgres"
            self.path = None
        else:
            raise ValueError("DATABASE_URL must start with sqlite:/// or postgresql://.")

    @contextmanager
    def connect(self) -> Iterator["ConnectionAdapter"]:
        if self.backend == "sqlite":
            assert self.path is not None
            self.path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.path)
            conn.row_factory = sqlite3.Row
        else:
            try:
                import psycopg2
                from psycopg2.extras import RealDictCursor
            except ModuleNotFoundError as exc:
                raise RuntimeError(
                    "PostgreSQL DATABASE_URL requires psycopg2-binary. Install requirements.txt first."
                ) from exc
            conn = psycopg2.connect(self.url, cursor_factory=RealDictCursor)
        try:
            yield ConnectionAdapter(conn, self.backend)
            conn.commit()
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connect() as conn:
            if self.backend == "postgres":
                schema_path = Path(__file__).resolve().parents[2] / "schema.sql"
                conn.executescript(schema_path.read_text(encoding="utf-8"))
            else:
                conn.executescript(
                    """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    triggered_by TEXT NOT NULL,
                    icp_profile TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    company_count INTEGER NOT NULL DEFAULT 0,
                    retry_count INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS companies (
                    company_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES runs(run_id),
                    name TEXT NOT NULL,
                    domain TEXT,
                    segment TEXT
                );

                CREATE TABLE IF NOT EXISTS research_findings (
                    finding_id TEXT PRIMARY KEY,
                    company_id TEXT NOT NULL REFERENCES companies(company_id),
                    claim TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    retrieved_at TEXT NOT NULL,
                    grounding_passed INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS analysis_outputs (
                    analysis_id TEXT PRIMARY KEY,
                    company_id TEXT NOT NULL REFERENCES companies(company_id),
                    icp_profile TEXT NOT NULL,
                    fit_score INTEGER NOT NULL,
                    pain_point_match TEXT NOT NULL,
                    buying_trigger TEXT NOT NULL,
                    risk_flags TEXT NOT NULL,
                    recommended_angle TEXT NOT NULL,
                    confidence REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS outreach_drafts (
                    draft_id TEXT PRIMARY KEY,
                    company_id TEXT NOT NULL REFERENCES companies(company_id),
                    subject TEXT NOT NULL,
                    body TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    review_flag TEXT NOT NULL,
                    evidence_refs TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reviewed_by TEXT,
                    reviewed_at TEXT,
                    revision_note TEXT,
                    revision_count INTEGER NOT NULL DEFAULT 0,
                    hubspot_object_id TEXT,
                    validation_notes TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS run_events (
                    event_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES runs(run_id),
                    company_id TEXT,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE VIEW IF NOT EXISTS lead_runs_view AS
                SELECT
                    r.run_id,
                    r.icp_profile,
                    r.status,
                    r.company_count,
                    r.retry_count,
                    AVG(a.fit_score) AS average_fit_score,
                    SUM(CASE WHEN rf.grounding_passed = 1 THEN 1 ELSE 0 END) * 1.0 /
                        NULLIF(COUNT(rf.finding_id), 0) AS grounding_rate
                FROM runs r
                LEFT JOIN companies c ON c.run_id = r.run_id
                LEFT JOIN analysis_outputs a ON a.company_id = c.company_id
                LEFT JOIN research_findings rf ON rf.company_id = c.company_id
                GROUP BY r.run_id;

                CREATE VIEW IF NOT EXISTS outreach_performance_view AS
                SELECT
                    status,
                    review_flag,
                    COUNT(*) AS draft_count,
                    AVG(confidence) AS average_confidence
                FROM outreach_drafts
                GROUP BY status, review_flag;

                CREATE VIEW IF NOT EXISTS agent_quality_view AS
                SELECT
                    r.run_id,
                    r.icp_profile,
                    COUNT(DISTINCT c.company_id) AS company_count,
                    COUNT(DISTINCT rf.finding_id) AS finding_count,
                    SUM(CASE WHEN rf.grounding_passed = 1 THEN 1 ELSE 0 END) AS grounded_finding_count,
                    SUM(CASE WHEN rf.grounding_passed = 1 THEN 1 ELSE 0 END) * 1.0 /
                        NULLIF(COUNT(rf.finding_id), 0) AS grounding_rate,
                    AVG(a.confidence) AS average_analysis_confidence,
                    AVG(d.confidence) AS average_draft_confidence,
                    SUM(CASE WHEN d.review_flag = 'ready_for_review' THEN 1 ELSE 0 END) AS ready_for_review_count,
                    SUM(CASE WHEN d.review_flag = 'needs_human_review' THEN 1 ELSE 0 END) AS needs_human_review_count
                FROM runs r
                LEFT JOIN companies c ON c.run_id = r.run_id
                LEFT JOIN research_findings rf ON rf.company_id = c.company_id
                LEFT JOIN analysis_outputs a ON a.company_id = c.company_id
                LEFT JOIN outreach_drafts d ON d.company_id = c.company_id
                GROUP BY r.run_id;

                CREATE VIEW IF NOT EXISTS cost_latency_view AS
                SELECT
                    r.run_id,
                    r.icp_profile,
                    COUNT(e.event_id) AS event_count,
                    SUM(COALESCE(json_extract(e.payload, '$.token_estimate'), 0)) AS token_estimate,
                    AVG(COALESCE(json_extract(e.payload, '$.latency_ms'), NULL)) AS average_latency_ms,
                    SUM(CASE WHEN e.event_type = 'worker_failed' THEN 1 ELSE 0 END) AS failure_event_count
                FROM runs r
                LEFT JOIN run_events e ON e.run_id = r.run_id
                GROUP BY r.run_id;
                """
                )

    def create_run(
        self,
        triggered_by: str,
        icp_profile: str,
        companies: list[dict[str, str | None]],
    ) -> str:
        run_id = str(uuid.uuid4())
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO runs(run_id, triggered_by, icp_profile, status, started_at, company_count)
                VALUES (?, ?, ?, 'queued', ?, ?)
                """,
                (run_id, triggered_by, icp_profile, now_iso(), len(companies)),
            )
            for company in companies:
                conn.execute(
                    """
                    INSERT INTO companies(company_id, run_id, name, domain, segment)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        run_id,
                        company["name"],
                        company.get("domain"),
                        company.get("segment"),
                    ),
                )
        return run_id

    def get_run(self, run_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            return dict(row)

    def latest_run_id(self) -> str | None:
        with self.connect() as conn:
            row = conn.execute("SELECT run_id FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()
            return str(row["run_id"]) if row else None

    def next_queued_run(self) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM runs WHERE status = 'queued' ORDER BY started_at LIMIT 1"
            ).fetchone()
            return dict(row) if row else None

    def update_run_status(self, run_id: str, status: str) -> None:
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid run status: {status}")
        with self.connect() as conn:
            finished_at = now_iso() if status in {"synced_to_crm", "archived", "failed"} else None
            conn.execute(
                "UPDATE runs SET status = ?, finished_at = COALESCE(?, finished_at) WHERE run_id = ?",
                (status, finished_at, run_id),
            )

    def increment_retry(self, run_id: str) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE runs SET retry_count = retry_count + 1 WHERE run_id = ?", (run_id,))

    def list_companies(self, run_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM companies WHERE run_id = ?", (run_id,)).fetchall()
            return [dict(row) for row in rows]

    def save_research_findings(self, company_id: str, findings: list[dict[str, Any]]) -> list[str]:
        ids: list[str] = []
        with self.connect() as conn:
            for finding in findings:
                finding_id = str(uuid.uuid4())
                ids.append(finding_id)
                conn.execute(
                    """
                    INSERT INTO research_findings(
                        finding_id, company_id, claim, source_url, source_type, retrieved_at, grounding_passed
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        finding_id,
                        company_id,
                        finding["claim"],
                        finding["source_url"],
                        finding["source_type"],
                        finding["retrieved_at"],
                        bool(finding["grounding_passed"]) if self.backend == "postgres" else 1 if finding["grounding_passed"] else 0,
                    ),
                )
        return ids

    def save_analysis(self, company_id: str, icp_profile: str, analysis: dict[str, Any]) -> str:
        analysis_id = str(uuid.uuid4())
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO analysis_outputs(
                    analysis_id, company_id, icp_profile, fit_score, pain_point_match,
                    buying_trigger, risk_flags, recommended_angle, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis_id,
                    company_id,
                    icp_profile,
                    analysis["fit_score"],
                    analysis["pain_point_match"],
                    analysis["buying_trigger"],
                    json.dumps(analysis["risk_flags"]),
                    analysis["recommended_angle"],
                    analysis["confidence"],
                ),
            )
        return analysis_id

    def save_outreach_draft(self, company_id: str, draft: dict[str, Any], status: str) -> str:
        draft_id = str(uuid.uuid4())
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO outreach_drafts(
                    draft_id, company_id, subject, body, confidence, review_flag,
                    evidence_refs, status, validation_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft_id,
                    company_id,
                    draft["subject"],
                    draft["body"],
                    draft["confidence"],
                    draft["review_flag"],
                    json.dumps(draft["evidence_refs"]),
                    status,
                    draft.get("validation_notes", ""),
                ),
            )
        return draft_id

    def list_outreach_drafts(self, run_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT d.* FROM outreach_drafts d
                JOIN companies c ON c.company_id = d.company_id
                WHERE c.run_id = ?
                ORDER BY d.draft_id
                """,
                (run_id,),
            ).fetchall()
            return [self._decode_draft(dict(row)) for row in rows]

    def get_outreach_draft(self, draft_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM outreach_drafts WHERE draft_id = ?", (draft_id,)).fetchone()
            if row is None:
                raise KeyError(draft_id)
            return self._decode_draft(dict(row))

    def get_run_id_for_draft(self, draft_id: str) -> str:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT c.run_id
                FROM outreach_drafts d
                JOIN companies c ON c.company_id = d.company_id
                WHERE d.draft_id = ?
                """,
                (draft_id,),
            ).fetchone()
            if row is None:
                raise KeyError(draft_id)
            return str(row["run_id"])

    def update_draft_review(
        self,
        draft_id: str,
        status: str,
        reviewed_by: str,
        revision_note: str | None = None,
        increment_revision: bool = False,
    ) -> None:
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid draft status: {status}")
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE outreach_drafts
                SET status = ?,
                    reviewed_by = ?,
                    reviewed_at = ?,
                    revision_note = COALESCE(?, revision_note),
                    revision_count = revision_count + ?
                WHERE draft_id = ?
                """,
                (
                    status,
                    reviewed_by,
                    now_iso(),
                    revision_note,
                    1 if increment_revision else 0,
                    draft_id,
                ),
            )

    def set_draft_hubspot_id(self, draft_id: str, hubspot_object_id: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE outreach_drafts
                SET hubspot_object_id = ?, status = 'synced_to_crm'
                WHERE draft_id = ?
                """,
                (hubspot_object_id, draft_id),
            )

    def log_event(
        self,
        run_id: str,
        event_type: str,
        payload: dict[str, Any],
        company_id: str | None = None,
    ) -> str:
        event_id = str(uuid.uuid4())
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO run_events(event_id, run_id, company_id, event_type, payload, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (event_id, run_id, company_id, event_type, json.dumps(payload), now_iso()),
            )
        return event_id

    def list_events(self, run_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM run_events WHERE run_id = ? ORDER BY created_at, event_id",
                (run_id,),
            ).fetchall()
            events = [dict(row) for row in rows]
            for event in events:
                event["payload"] = decode_json_value(event["payload"])
            return events

    @staticmethod
    def _decode_draft(draft: dict[str, Any]) -> dict[str, Any]:
        draft["evidence_refs"] = decode_json_value(draft["evidence_refs"])
        return draft


class ExecutableConnection(Protocol):
    def execute(self, sql: str, parameters: tuple[Any, ...] = ()) -> Any:
        ...

    def executescript(self, sql_script: str) -> Any:
        ...


class ConnectionAdapter:
    def __init__(self, conn: ExecutableConnection, backend: str):
        self.conn = conn
        self.backend = backend

    def execute(self, sql: str, parameters: tuple[Any, ...] = ()) -> Any:
        if self.backend == "postgres":
            cursor = self.conn.cursor()
            cursor.execute(sql.replace("?", "%s"), parameters)
            return cursor
        return self.conn.execute(sql, parameters)

    def executescript(self, sql_script: str) -> Any:
        if self.backend == "postgres":
            cursor = self.conn.cursor()
            cursor.execute(sql_script)
            return cursor
        return self.conn.executescript(sql_script)
