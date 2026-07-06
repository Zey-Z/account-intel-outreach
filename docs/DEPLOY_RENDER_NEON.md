# Deploy To Render + Neon

This stage turns the local FastAPI app into a public HTTPS service that Zapier
can call.

## Why This Stage Exists

Zapier runs in the cloud, so it cannot call:

```text
http://127.0.0.1:8011/runs
```

It needs a public HTTPS URL:

```text
https://your-render-service.onrender.com/runs
```

Render hosts the FastAPI service. Neon hosts the PostgreSQL database.

## Layer Roles

```text
Zapier       business entry layer
Render       public API hosting
FastAPI      receives /runs requests
Worker       processes queued runs
Neon         persistent Postgres database
```

## Neon Setup

1. Create a Neon project.
2. Copy the pooled or direct PostgreSQL connection string.
3. Make sure the URL starts with `postgresql://`.
4. Keep `sslmode=require` in the URL if Neon provides it.

Use this value as Render's `DATABASE_URL`.

## Database Migrations

The database schema is versioned in `migrations/`.

- `Database.initialize()` creates `schema_migrations` if needed.
- Migration files run in filename order.
- Already-applied migrations are skipped.
- `schema.sql` is now only a compatibility note; do not edit it for new schema
  changes.

For future schema changes, add a new file such as:

```text
migrations/0002_add_example_column.sql
```

Each migration should include the SQL needed for the supported database dialects
and should be safe to apply once.

## Render Setup

1. Create a new Render web service from this repo.
2. Use Python runtime.
3. Build command:

```text
pip install -r requirements.txt
```

4. Start command:

```text
uvicorn main:app --host 0.0.0.0 --port $PORT
```

5. Add environment variables:

```text
DATABASE_URL=<Neon PostgreSQL URL>
ICP_PROFILES_PATH=icp_profiles.yaml
TAVILY_API_KEY=
SLACK_WEBHOOK_URL=
SLACK_BOT_TOKEN=
SLACK_SIGNING_SECRET=
HUBSPOT_PRIVATE_APP_TOKEN=
```

6. Deploy.

## Test-Gated Deploy Setup

The repository includes a GitHub Actions deploy workflow. It does not deploy
directly from a developer laptop. It first runs the unit test suite in offline
mode, then calls a Render Deploy Hook only if the tests pass.

One-time owner setup:

1. In Render, open the `account-intel-outreach-api` web service.
2. Open Settings.
3. Find Deploy Hook and create a new deploy hook URL.
4. Copy the full deploy hook URL.
5. In GitHub, open `Zey-Z/account-intel-outreach`.
6. Go to Settings -> Secrets and variables -> Actions.
7. Add a repository secret named `RENDER_DEPLOY_HOOK_URL`.
8. Paste the Render Deploy Hook URL as the value.
9. Optional but recommended: enable a branch protection rule for `main` that
   requires the `CI / Unit tests` check before merging.

If `RENDER_DEPLOY_HOOK_URL` is missing, the deploy workflow fails loudly. That is
intentional: a silent no-op would make the repo look deployed when it is not.

## First Verification

After deploy, open:

```text
https://your-render-service.onrender.com/health
```

Expected response:

```json
{"status":"ok"}
```

Then test:

```powershell
$payload = @{
  company_name = "Oscar Health"
  domain = "hioscar.com"
  icp_profile = "healthcare_insurance_ops"
  triggered_by = "render-smoke-test"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "https://your-render-service.onrender.com/runs" `
  -ContentType "application/json" `
  -Body $payload
```

Expected response:

```json
{"run_id":"...","status":"queued"}
```

## Important Boundary

Render hosting is demo deployment, not production proof. A production system
would need a durable queue, scheduled worker, auth, rate limiting, monitoring,
and stronger secret management.
