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
    def __init__(self, url: str, migrations_dir: Path | str | None = None):
        self.url = url
        self.migrations_dir = Path(migrations_dir) if migrations_dir is not None else Path(__file__).resolve().parents[2] / "migrations"
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
            self._ensure_migration_table(conn)
            applied = {
                row["id"]
                for row in conn.execute("SELECT id FROM schema_migrations").fetchall()
            }
            for path in sorted(self.migrations_dir.glob("*.sql")):
                migration_id = path.name
                if migration_id in applied:
                    continue
                sql = self._migration_sql_for_backend(path.read_text(encoding="utf-8"))
                if sql.strip():
                    conn.executescript(sql)
                conn.execute(
                    "INSERT INTO schema_migrations(id, applied_at) VALUES (?, ?)",
                    (migration_id, now_iso()),
                )

    def _ensure_migration_table(self, conn: "ConnectionAdapter") -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )

    def _migration_sql_for_backend(self, sql: str) -> str:
        selected_lines: list[str] = []
        common_lines: list[str] = []
        current_dialect: str | None = None
        has_dialect_markers = False
        for line in sql.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("-- dialect:"):
                has_dialect_markers = True
                current_dialect = stripped.split(":", 1)[1].strip().lower()
                continue
            if not has_dialect_markers:
                common_lines.append(line)
            elif current_dialect == self.backend:
                selected_lines.append(line)
        if not has_dialect_markers:
            return "\n".join(common_lines)
        return "\n".join(common_lines + selected_lines)

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

    def requeue_run(self, run_id: str) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE runs SET status = 'queued', finished_at = NULL WHERE run_id = ?", (run_id,))

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

    def get_draft_sync_context(self, draft_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT
                    d.*,
                    c.company_id,
                    c.run_id,
                    c.name AS company_name,
                    c.domain AS company_domain
                FROM outreach_drafts d
                JOIN companies c ON c.company_id = d.company_id
                WHERE d.draft_id = ?
                """,
                (draft_id,),
            ).fetchone()
            if row is None:
                raise KeyError(draft_id)
            return self._decode_draft(dict(row))

    def list_approved_drafts_without_hubspot(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    d.*,
                    c.company_id,
                    c.run_id,
                    c.name AS company_name,
                    c.domain AS company_domain
                FROM outreach_drafts d
                JOIN companies c ON c.company_id = d.company_id
                WHERE d.status = 'approved'
                  AND (d.hubspot_object_id IS NULL OR d.hubspot_object_id = '')
                ORDER BY d.reviewed_at, d.draft_id
                """
            ).fetchall()
            return [self._decode_draft(dict(row)) for row in rows]

    def list_source_urls_for_draft(self, draft_id: str) -> list[str]:
        draft = self.get_draft_sync_context(draft_id)
        evidence_refs = draft.get("evidence_refs") or []
        with self.connect() as conn:
            if evidence_refs:
                placeholders = ", ".join("?" for _ in evidence_refs)
                rows = conn.execute(
                    f"""
                    SELECT DISTINCT source_url
                    FROM research_findings
                    WHERE company_id = ?
                      AND finding_id IN ({placeholders})
                    ORDER BY source_url
                    """,
                    tuple([draft["company_id"], *evidence_refs]),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT DISTINCT source_url
                    FROM research_findings
                    WHERE company_id = ?
                    ORDER BY source_url
                    """,
                    (draft["company_id"],),
                ).fetchall()
            return [str(row["source_url"]) for row in rows]

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
