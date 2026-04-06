# Operations

This guide covers day-to-day operations for the `auto-marketer` service.

## Campaign management

1. **Initialize:** Create a campaign with a clear goal (e.g., "Schedule a 10-minute demo") and a specific tone.
2. **Drafting:** Run the generation process to create draft emails from `info-broker` profiles. Start with a small limit (e.g., `--limit 10`) to verify quality.
3. **Reviewing:** Use the API or CLI to inspect drafts and make manual edits if necessary.
4. **Sending:** Perform a dry-run send first. Review the results in the `email_drafts` table or CLI export. When satisfied, proceed to a live SMTP send.

## Monitoring & maintenance

- **Logs:** Monitor FastAPI logs for `5xx` errors and slow response times.
- **Database:** Periodically check the `email_drafts` table for failed sends.
- **Health Checks:** The `/health` endpoint provides status on the database connection and service availability.

## Rate limiting

The `sender` module supports a `rate_limit_per_min` parameter. This is critical when using SMTP to avoid domain blacklisting. A safe starting point is 5–10 emails per minute for new domains, gradually increasing as you build reputation.

## Exporting results

Campaign results should be exported regularly to track conversion rates and for import into CRM systems.

```bash
auto-marketer export --campaign-id <id> --format xlsx --output q2_results.xlsx
```
