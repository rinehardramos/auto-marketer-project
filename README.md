# auto-marketer

Personalized cold email generation and bulk sending. Pure marketing layer
of a two-service stack — pair it with the sibling
[`info-broker`](https://github.com/rinehardramos/info-broker) service which
supplies prospect profiles over REST.

```
+------------+   REST    +---------------+   SMTP   +-----------+
| info-broker| --------> | auto-marketer | -------> | recipient |
| (research) |  /profiles| (generate +   |          |           |
+------------+           |  send)        |          +-----------+
                         +---------------+
```

auto-marketer does NOT scrape, ingest, or grade anything — that all lives
in info-broker now. It only:

1. Pulls candidate profiles from info-broker
2. Drafts personalized emails with an LLM (LM Studio / OpenAI-compatible)
3. Stores drafts for human review/edit
4. Bulk-sends with rate limiting (DryRunSender by default)
5. Exports campaign results as CSV / XLSX / JSON

## Quickstart

```bash
cp .env.example .env
# fill in INFO_BROKER_BASE_URL, INFO_BROKER_API_KEY, AUTO_MARKETER_API_KEY,
# LM_STUDIO_BASE_URL and (when ready to actually send) SMTP_*

uv sync --extra dev
docker compose up -d postgres
uv run uvicorn app.main:app --reload --port 8001
```

## API examples

```bash
# Create a campaign
curl -X POST http://localhost:8001/campaigns \
  -H "X-API-Key: $AUTO_MARKETER_API_KEY" -H "Content-Type: application/json" \
  -d '{"name":"Q2 SMB push","tone":"warm","goal":"book a 15-min discovery call"}'

# Generate drafts (pulls profiles from info-broker)
curl -X POST http://localhost:8001/campaigns/1/generate \
  -H "X-API-Key: $AUTO_MARKETER_API_KEY" -H "Content-Type: application/json" \
  -d '{"limit": 50, "workers": 4}'

# Review / edit a draft
curl -X PATCH http://localhost:8001/drafts/12 \
  -H "X-API-Key: $AUTO_MARKETER_API_KEY" -H "Content-Type: application/json" \
  -d '{"subject":"New subject","body":"Edited body"}'

# Dry-run send
curl -X POST http://localhost:8001/campaigns/1/send \
  -H "X-API-Key: $AUTO_MARKETER_API_KEY" -H "Content-Type: application/json" \
  -d '{"provider":"dry-run","rate_limit_per_min":30}'

# Real send (only after dry-run looks right)
curl -X POST http://localhost:8001/campaigns/1/send \
  -H "X-API-Key: $AUTO_MARKETER_API_KEY" -H "Content-Type: application/json" \
  -d '{"provider":"smtp","rate_limit_per_min":30}'

# Export
curl -OJ -H "X-API-Key: $AUTO_MARKETER_API_KEY" \
  "http://localhost:8001/campaigns/1/export?format=csv"
```

## CLI

```bash
auto-marketer campaign create --name "Q2 push" --tone warm --goal "book demos"
auto-marketer generate --campaign-id 1 --limit 50
auto-marketer send --campaign-id 1 --provider dry-run --rate-limit 30
auto-marketer export --campaign-id 1 --format csv --output q2.csv
```

## Docs

- [docs/architecture.md](docs/architecture.md) — two-service split
- [docs/campaigns.md](docs/campaigns.md) — campaign lifecycle
- [docs/sending.md](docs/sending.md) — sender providers, rate limiting
- [SECURITY.md](SECURITY.md) — threat model
