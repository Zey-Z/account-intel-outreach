-- Each metric is aggregated at its natural grain before the results are joined.
-- This prevents companies with more findings from receiving extra weight.

-- dialect: sqlite
DROP VIEW IF EXISTS lead_runs_view;
CREATE VIEW lead_runs_view AS
WITH analysis_metrics AS (
    SELECT c.run_id, AVG(a.fit_score) AS average_fit_score
    FROM companies c
    JOIN analysis_outputs a ON a.company_id = c.company_id
    GROUP BY c.run_id
),
finding_metrics AS (
    SELECT
        c.run_id,
        SUM(CASE WHEN rf.grounding_passed = 1 THEN 1 ELSE 0 END) * 1.0 /
            NULLIF(COUNT(rf.finding_id), 0) AS grounding_rate
    FROM companies c
    JOIN research_findings rf ON rf.company_id = c.company_id
    GROUP BY c.run_id
)
SELECT
    r.run_id,
    r.icp_profile,
    r.status,
    r.company_count,
    r.retry_count,
    a.average_fit_score,
    f.grounding_rate
FROM runs r
LEFT JOIN analysis_metrics a ON a.run_id = r.run_id
LEFT JOIN finding_metrics f ON f.run_id = r.run_id;

DROP VIEW IF EXISTS agent_quality_view;
CREATE VIEW agent_quality_view AS
WITH company_metrics AS (
    SELECT run_id, COUNT(company_id) AS company_count
    FROM companies
    GROUP BY run_id
),
finding_metrics AS (
    SELECT
        c.run_id,
        COUNT(rf.finding_id) AS finding_count,
        SUM(CASE WHEN rf.grounding_passed = 1 THEN 1 ELSE 0 END) AS grounded_finding_count,
        SUM(CASE WHEN rf.grounding_passed = 1 THEN 1 ELSE 0 END) * 1.0 /
            NULLIF(COUNT(rf.finding_id), 0) AS grounding_rate
    FROM companies c
    JOIN research_findings rf ON rf.company_id = c.company_id
    GROUP BY c.run_id
),
analysis_metrics AS (
    SELECT c.run_id, AVG(a.confidence) AS average_analysis_confidence
    FROM companies c
    JOIN analysis_outputs a ON a.company_id = c.company_id
    GROUP BY c.run_id
),
draft_metrics AS (
    SELECT
        c.run_id,
        AVG(d.confidence) AS average_draft_confidence,
        SUM(CASE WHEN d.review_flag = 'ready_for_review' THEN 1 ELSE 0 END) AS ready_for_review_count,
        SUM(CASE WHEN d.review_flag = 'needs_human_review' THEN 1 ELSE 0 END) AS needs_human_review_count
    FROM companies c
    JOIN outreach_drafts d ON d.company_id = c.company_id
    GROUP BY c.run_id
)
SELECT
    r.run_id,
    r.icp_profile,
    COALESCE(c.company_count, 0) AS company_count,
    COALESCE(f.finding_count, 0) AS finding_count,
    COALESCE(f.grounded_finding_count, 0) AS grounded_finding_count,
    f.grounding_rate,
    a.average_analysis_confidence,
    d.average_draft_confidence,
    COALESCE(d.ready_for_review_count, 0) AS ready_for_review_count,
    COALESCE(d.needs_human_review_count, 0) AS needs_human_review_count
FROM runs r
LEFT JOIN company_metrics c ON c.run_id = r.run_id
LEFT JOIN finding_metrics f ON f.run_id = r.run_id
LEFT JOIN analysis_metrics a ON a.run_id = r.run_id
LEFT JOIN draft_metrics d ON d.run_id = r.run_id;

-- dialect: postgres
DROP VIEW IF EXISTS lead_runs_view;
CREATE VIEW lead_runs_view AS
WITH analysis_metrics AS (
    SELECT c.run_id, AVG(a.fit_score) AS average_fit_score
    FROM companies c
    JOIN analysis_outputs a ON a.company_id = c.company_id
    GROUP BY c.run_id
),
finding_metrics AS (
    SELECT
        c.run_id,
        SUM(CASE WHEN rf.grounding_passed THEN 1 ELSE 0 END)::NUMERIC /
            NULLIF(COUNT(rf.finding_id), 0) AS grounding_rate
    FROM companies c
    JOIN research_findings rf ON rf.company_id = c.company_id
    GROUP BY c.run_id
)
SELECT
    r.run_id,
    r.icp_profile,
    r.status,
    r.company_count,
    r.retry_count,
    a.average_fit_score,
    f.grounding_rate
FROM runs r
LEFT JOIN analysis_metrics a ON a.run_id = r.run_id
LEFT JOIN finding_metrics f ON f.run_id = r.run_id;

DROP VIEW IF EXISTS agent_quality_view;
CREATE VIEW agent_quality_view AS
WITH company_metrics AS (
    SELECT run_id, COUNT(company_id) AS company_count
    FROM companies
    GROUP BY run_id
),
finding_metrics AS (
    SELECT
        c.run_id,
        COUNT(rf.finding_id) AS finding_count,
        SUM(CASE WHEN rf.grounding_passed THEN 1 ELSE 0 END) AS grounded_finding_count,
        SUM(CASE WHEN rf.grounding_passed THEN 1 ELSE 0 END)::NUMERIC /
            NULLIF(COUNT(rf.finding_id), 0) AS grounding_rate
    FROM companies c
    JOIN research_findings rf ON rf.company_id = c.company_id
    GROUP BY c.run_id
),
analysis_metrics AS (
    SELECT c.run_id, AVG(a.confidence) AS average_analysis_confidence
    FROM companies c
    JOIN analysis_outputs a ON a.company_id = c.company_id
    GROUP BY c.run_id
),
draft_metrics AS (
    SELECT
        c.run_id,
        AVG(d.confidence) AS average_draft_confidence,
        SUM(CASE WHEN d.review_flag = 'ready_for_review' THEN 1 ELSE 0 END) AS ready_for_review_count,
        SUM(CASE WHEN d.review_flag = 'needs_human_review' THEN 1 ELSE 0 END) AS needs_human_review_count
    FROM companies c
    JOIN outreach_drafts d ON d.company_id = c.company_id
    GROUP BY c.run_id
)
SELECT
    r.run_id,
    r.icp_profile,
    COALESCE(c.company_count, 0) AS company_count,
    COALESCE(f.finding_count, 0) AS finding_count,
    COALESCE(f.grounded_finding_count, 0) AS grounded_finding_count,
    f.grounding_rate,
    a.average_analysis_confidence,
    d.average_draft_confidence,
    COALESCE(d.ready_for_review_count, 0) AS ready_for_review_count,
    COALESCE(d.needs_human_review_count, 0) AS needs_human_review_count
FROM runs r
LEFT JOIN company_metrics c ON c.run_id = r.run_id
LEFT JOIN finding_metrics f ON f.run_id = r.run_id
LEFT JOIN analysis_metrics a ON a.run_id = r.run_id
LEFT JOIN draft_metrics d ON d.run_id = r.run_id;
