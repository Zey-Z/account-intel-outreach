CREATE INDEX IF NOT EXISTS idx_runs_queue
    ON runs(status, started_at);

CREATE INDEX IF NOT EXISTS idx_companies_run
    ON companies(run_id);

CREATE INDEX IF NOT EXISTS idx_findings_company
    ON research_findings(company_id);

CREATE INDEX IF NOT EXISTS idx_analysis_company
    ON analysis_outputs(company_id);

CREATE INDEX IF NOT EXISTS idx_drafts_company_status
    ON outreach_drafts(company_id, status);

CREATE INDEX IF NOT EXISTS idx_events_run_created
    ON run_events(run_id, created_at);
