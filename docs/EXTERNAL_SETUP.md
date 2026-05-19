# External Setup Checklist

## Zapier

1. Create a Zapier Table with columns: `company_name`, `domain`, `icp_profile`.
2. Create a Zap from "new table record".
3. Add Webhooks by Zapier POST action.
4. POST to `https://<render-url>/runs`.
5. Body example:

```json
{
  "triggered_by": "zapier",
  "company_name": "{{company_name}}",
  "domain": "{{domain}}",
  "icp_profile": "{{icp_profile}}"
}
```

## Slack

1. Create a Slack app.
2. Enable interactivity.
3. Set Request URL to `https://<render-url>/slack/interactions`.
4. Copy signing secret into `SLACK_SIGNING_SECRET`.
5. Use `build_review_message` from `account_intel.integrations.slack` to format messages.

## HubSpot

1. Create a private app.
2. Enable CRM object write permissions for notes and companies.
3. Put token in `HUBSPOT_PRIVATE_APP_TOKEN`.
4. Sync only approved drafts.

## Power BI

Connect Power BI Desktop to the PostgreSQL database or export SQLite data to CSV
for the first demo. Use:

- `lead_runs_view`
- `outreach_performance_view`
