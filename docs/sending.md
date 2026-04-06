# Sending

## Providers

- `dry-run` (**default**) — `DryRunSender`. Logs the email it would
  have sent and returns a synthetic message id. Use this until you are
  100% certain about the draft list.
- `smtp` — `SMTPSender`. Uses stdlib `smtplib` + `EmailMessage`. Reads
  `SMTP_HOST`, `SMTP_PORT` (default 587), `SMTP_USER`, `SMTP_PASSWORD`,
  `SMTP_FROM`, `SMTP_USE_TLS` (default true) from the environment.
  STARTTLS is on by default.
- `noop` — for tests only. Returns `noop-message-id` and does nothing.

## Rate limiting

`send_campaign(rate_limit_per_min=N)` sleeps `60/N` seconds between
sends. The default is 30/minute. Use a much lower number on a fresh
domain to keep your sender reputation alive.

## Failure handling

Per-draft exceptions are caught, the draft is moved to status `failed`
with the error stored in `error_message`, and the loop continues. The
campaign as a whole is marked `sent` if and only if every draft
succeeds; otherwise it ends in `failed` and you can re-run after
fixing the offending rows (drafts in status `failed` are not picked up
on retry — only `draft` and `queued` are). Reset failed drafts by
PATCHing them or by re-generating the campaign.

## Configuring SMTP

Minimum required env:

```
SMTP_HOST=smtp.example.com
SMTP_FROM=outreach@example.com
SMTP_USER=outreach@example.com
SMTP_PASSWORD=hunter2
SMTP_USE_TLS=true
```

Production tip: terminate authentication at a transactional provider
(SES, Postmark, SendGrid) rather than a raw mail server, and rotate
the SMTP password from a secret store rather than committing it to
`.env`.
