# Production Readiness

This document explains what has been production-hardened in this portfolio
deployment and what is still intentionally limited.

The short version: this is stronger than a local demo, but it is not an
enterprise production rollout. It has test gates, deploy gates, migrations,
request tracing, rate limiting, and health checks. It still runs on lightweight
demo infrastructure and should be described honestly.

## CI/CD Pipeline

GitHub Actions runs the offline unit test suite on every push and pull request.
The tests use deterministic offline mode, so they do not need OpenAI, Tavily,
Slack, HubSpot, or Neon credentials.

The deploy workflow is a test-gated deploy. It runs the test suite first, and
only then calls the Render Deploy Hook stored in the GitHub secret
`RENDER_DEPLOY_HOOK_URL`.

Plain English: code does not get sent to the demo server just because someone
pushed it. The project first asks, "did the safety checks pass?"

## Database Migrations

The database schema is versioned in `migrations/`. The first migration is
`migrations/0001_init.sql`.

`Database.initialize()` creates a `schema_migrations` table, checks which
migrations have already run, and applies any missing files in filename order.
This lets the same startup path work for local SQLite and cloud Postgres.

Plain English: the database keeps a checklist of structure updates, so future
schema changes can be replayed in order instead of being guessed manually.

## Atomic Worker Claiming

Before processing starts, a worker atomically changes one run from `queued` to
`researching`. Postgres uses a row lock that skips work already claimed by
another worker; local SQLite takes a short write lock. The claim and its
`run_claimed` audit event are stored in the same database transaction.

Plain English: two workers may reach for the same folder, but only one can sign
it out. This prevents duplicate research and duplicate drafts.

## Approved-Only CRM Filing

After Slack approval, the HubSpot client searches for a company by its public
domain, creates the company only when needed, and files the approved note on
that company record. The note keeps its source URLs, and temporary HubSpot
errors receive bounded retries before the failure is logged for catch-up sync.

Plain English: the approved note is placed in the correct customer folder, not
left loose in the filing cabinet.

## Structured Logging And Request Tracing

The FastAPI service emits one structured JSON log line per request. Each log
includes:

- request method
- request path
- status code
- latency in milliseconds
- request ID

The response also includes `X-Request-Id`.

Plain English: every API call gets a claim ticket. If something goes wrong, the
request ID helps connect the user-visible response to the server log.

## Rate Limiting

`POST /runs` and `POST /worker/process-next` use an in-memory sliding-window rate
limiter. The default is 30 requests per minute, configurable with
`RATE_LIMIT_PER_MINUTE`.

This is appropriate for a single-instance demo/portfolio deployment. It is not a
full multi-instance production limiter. If the service ran multiple app
instances, a real deployment would need shared state such as Redis so every
instance sees the same counters.

Plain English: this is a front-desk rule for one desk. If the company opens many
front desks, the desks need a shared notebook.

## Health Checks

`GET /health` stays public and fast for Render's health check path.

`GET /health/deep` is protected by `X-API-Key`. It runs a small database query,
measures database latency, reports the database dialect, and returns a degraded
503 response if the query fails.

Plain English: `/health` checks whether the door opens. `/health/deep` checks
whether the filing cabinet inside is reachable.

## Containerization

The repository includes an optional Docker path. The live Render config still
uses Render's Python runtime. The Dockerfile exists to show that the service can
also be packaged as a standard container. The image runs as an unprivileged
`appuser` and includes a container health check against `/health`.

The image was built from a clean Python 3.12 base and started locally on
2026-07-09; its containerized `/health` endpoint returned HTTP 200.

Plain English: Render is the current stage. Docker is the shipping box that
makes the app easier to move to another stage later. The app does not get the
master key to the box, and the box checks that the app is still awake.

## Known Limitations

- Render free tier can cold start and has no autoscaling guarantee.
- SQLite locally is useful for development, but cloud demo runs should use
  Postgres.
- The rate limiter is in memory, so it is single-instance only.
- There is no WAF/CDN layer in front of the API.
- Worker claiming prevents duplicate pickup, but the in-process poller is still
  a lightweight demo/internal runner rather than a supervised durable queue.
- Secrets and dashboard settings still require owner-managed setup.
- The project uses public company data only. It does not process PHI or patient
  data.
- The system drafts outreach for human review. It does not auto-send emails.
- This project should not be described as HIPAA compliant, clinically validated,
  or enterprise production rolled out.
