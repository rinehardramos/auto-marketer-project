# Architecture

auto-marketer is one half of a two-service stack:

| Service       | Responsibility                                          |
|---------------|---------------------------------------------------------|
| info-broker   | Ingest LinkedIn data, run OSINT research, grade fit, vector search |
| auto-marketer | Generate personalized emails, manage drafts, bulk-send, export |

The two communicate over REST. auto-marketer is a strict consumer — it
never writes back to info-broker.

## Why split?

The original monolith mixed information-gathering (high latency,
flaky upstream APIs, scraping risk) with email-sending (predictable,
transactional, requires its own auth and rate-limit story). Splitting
lets each side scale and deploy independently and isolates failure
domains: if info-broker is down, in-flight campaigns can still be
reviewed and sent.

## Data flow

1. info-broker scrapes/researches a profile and marks it
   `research_status = 'completed'`.
2. auto-marketer's `POST /campaigns/{id}/generate` calls
   `InfoBrokerClient.list_profiles(status='completed')` and asks the LLM
   for a `{subject, body}` per profile.
3. Drafts are stored in auto-marketer's own Postgres tables
   (`campaigns`, `email_drafts`).
4. A human reviews/edits drafts via `PATCH /drafts/{id}`.
5. `POST /campaigns/{id}/send` ships them through the chosen sender
   (`dry-run` by default).

## Storage

auto-marketer owns two tables only: `campaigns` and `email_drafts`. It
does NOT touch info-broker's `linkedin_profiles` table even when sharing
the same Postgres instance — data only moves through the REST contract.

## Auth

Every endpoint except `/healthz` requires the `X-API-Key` header set to
`AUTO_MARKETER_API_KEY`. The InfoBrokerClient sends `X-API-Key` set to
`INFO_BROKER_API_KEY` on every outbound request.
