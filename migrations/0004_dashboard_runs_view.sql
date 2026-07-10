CREATE VIEW dashboard_runs_view AS
SELECT
    r.run_id,
    r.triggered_by,
    r.started_at,
    r.finished_at,
    l.icp_profile,
    l.status,
    l.company_count,
    l.retry_count,
    l.average_fit_score,
    l.grounding_rate,
    q.finding_count,
    q.grounded_finding_count,
    q.average_analysis_confidence,
    q.average_draft_confidence,
    q.ready_for_review_count,
    q.needs_human_review_count,
    c.event_count,
    c.token_estimate,
    c.average_latency_ms,
    c.failure_event_count
FROM lead_runs_view l
JOIN runs r ON r.run_id = l.run_id
LEFT JOIN agent_quality_view q ON q.run_id = l.run_id
LEFT JOIN cost_latency_view c ON c.run_id = l.run_id;
