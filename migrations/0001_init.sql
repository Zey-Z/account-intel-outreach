-- dialect: sqlite
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

-- dialect: postgres
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    triggered_by TEXT NOT NULL,
    icp_profile TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
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
    retrieved_at TIMESTAMPTZ NOT NULL,
    grounding_passed BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS analysis_outputs (
    analysis_id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(company_id),
    icp_profile TEXT NOT NULL,
    fit_score INTEGER NOT NULL,
    pain_point_match TEXT NOT NULL,
    buying_trigger TEXT NOT NULL,
    risk_flags JSONB NOT NULL,
    recommended_angle TEXT NOT NULL,
    confidence NUMERIC NOT NULL
);

CREATE TABLE IF NOT EXISTS outreach_drafts (
    draft_id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(company_id),
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    confidence NUMERIC NOT NULL,
    review_flag TEXT NOT NULL,
    evidence_refs JSONB NOT NULL,
    status TEXT NOT NULL,
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
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
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE OR REPLACE VIEW lead_runs_view AS
SELECT
    r.run_id,
    r.icp_profile,
    r.status,
    r.company_count,
    r.retry_count,
    AVG(a.fit_score) AS average_fit_score,
    SUM(CASE WHEN rf.grounding_passed THEN 1 ELSE 0 END)::NUMERIC /
        NULLIF(COUNT(rf.finding_id), 0) AS grounding_rate
FROM runs r
LEFT JOIN companies c ON c.run_id = r.run_id
LEFT JOIN analysis_outputs a ON a.company_id = c.company_id
LEFT JOIN research_findings rf ON rf.company_id = c.company_id
GROUP BY r.run_id;

CREATE OR REPLACE VIEW outreach_performance_view AS
SELECT
    status,
    review_flag,
    COUNT(*) AS draft_count,
    AVG(confidence) AS average_confidence
FROM outreach_drafts
GROUP BY status, review_flag;

CREATE OR REPLACE VIEW agent_quality_view AS
SELECT
    r.run_id,
    r.icp_profile,
    COUNT(DISTINCT c.company_id) AS company_count,
    COUNT(DISTINCT rf.finding_id) AS finding_count,
    SUM(CASE WHEN rf.grounding_passed THEN 1 ELSE 0 END) AS grounded_finding_count,
    SUM(CASE WHEN rf.grounding_passed THEN 1 ELSE 0 END)::NUMERIC /
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

CREATE OR REPLACE VIEW cost_latency_view AS
SELECT
    r.run_id,
    r.icp_profile,
    COUNT(e.event_id) AS event_count,
    SUM(COALESCE((e.payload->>'token_estimate')::NUMERIC, 0)) AS token_estimate,
    AVG(NULLIF(e.payload->>'latency_ms', '')::NUMERIC) AS average_latency_ms,
    SUM(CASE WHEN e.event_type = 'worker_failed' THEN 1 ELSE 0 END) AS failure_event_count
FROM runs r
LEFT JOIN run_events e ON e.run_id = r.run_id
GROUP BY r.run_id;
