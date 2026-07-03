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
2. Enable Incoming Webhooks and add the webhook to the review channel.
3. Copy the webhook URL into `SLACK_WEBHOOK_URL`.
4. In OAuth & Permissions, make sure the bot has `chat:write`.
5. Install or reinstall the app to the workspace.
6. Copy the Bot User OAuth Token into `SLACK_BOT_TOKEN`.
7. Enable interactivity.
8. Set Request URL to `https://<render-url>/slack/interactions`.
9. Copy signing secret into `SLACK_SIGNING_SECRET`.
10. Send a review message from the same Render environment that will handle button clicks:

```text
POST https://<render-url>/slack/send-latest-review
Header: X-API-Key: <ACCOUNT_INTEL_API_KEY>
```

## HubSpot

1. Create a private app.
2. Enable CRM object write permissions for notes and companies.
3. Put token in `HUBSPOT_PRIVATE_APP_TOKEN`.
4. Sync only approved drafts. When a Slack reviewer clicks Approve, the service attempts to create a HubSpot note with the approved draft and source links.
5. If HubSpot was not configured during approval, run the catch-up endpoint later:

```text
POST https://<render-url>/crm/sync-approved
Header: X-API-Key: <ACCOUNT_INTEL_API_KEY>
```

## Power BI

Connect Power BI Desktop to the PostgreSQL database or export SQLite data to CSV
for the first demo. Use:

- `lead_runs_view`
- `outreach_performance_view`
