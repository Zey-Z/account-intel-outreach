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
SLACK_BOT_TOKEN=
SLACK_SIGNING_SECRET=
HUBSPOT_PRIVATE_APP_TOKEN=
```

6. Deploy.

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
