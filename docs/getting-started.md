# Getting started

This guide takes a fresh checkout to a working marketing pipeline: creating a campaign, generating drafts from `info-broker` profiles, and performing a dry-run send.

## Prerequisites

- Python 3.10 or newer.
- [`uv`](https://github.com/astral-sh/uv) package manager.
- Docker Desktop (or any Docker Engine) for Postgres.
- [LM Studio](https://lmstudio.ai/) (or OpenAI/Anthropic) with a chat model loaded and its OpenAI-compatible server running.
- A running instance of the sibling [`info-broker`](https://github.com/rinehardramos/info-broker) service.

## 1. Clone and install

```sh
git clone <repo-url> auto-marketer-project
cd auto-marketer-project
uv sync --extra dev
```

`--extra dev` pulls in `pytest`, `ruff`, and `pip-audit`.

## 2. Start Postgres

```sh
docker compose up -d postgres
```

`docker-compose.yml` maps Postgres to host port **5433**. The container keeps data in a named volume `postgres_data`.

## 3. Configure LLM Provider

If using LM Studio:
1. Load a chat-capable model (e.g., `mistralai/mistral-nemo-instruct-2407`).
2. Start the local server. Note the base URL (default `http://localhost:1234/v1`).

## 4. Create `.env`

Create a `.env` file in the repo root:

```sh
# --- info-broker ---
INFO_BROKER_BASE_URL=http://localhost:8000
INFO_BROKER_API_KEY=your-broker-key

# --- auto-marketer ---
AUTO_MARKETER_API_KEY=your-api-key

# --- LLM Provider ---
LM_STUDIO_BASE_URL=http://localhost:1234/v1
LM_STUDIO_API_KEY=lm-studio
CHAT_MODEL_NAME=mistralai/mistral-nemo-instruct-2407

# --- Postgres ---
POSTGRES_DB=auto_marketer
POSTGRES_USER=user
POSTGRES_PASSWORD=password
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
```

## 5. Launch the API

```sh
uv run uvicorn app.main:app --reload --port 8001
```

The API will be available at `http://localhost:8001`. Swagger docs are at `/docs`.

## 6. Your first campaign

Using the CLI:

```bash
# 1. Create campaign
auto-marketer campaign create --name "Test Push" --tone "professional" --goal "book a demo"

# 2. Generate drafts (pulls from info-broker)
auto-marketer generate --campaign-id 1 --limit 10

# 3. Dry-run send
auto-marketer send --campaign-id 1 --provider dry-run --rate-limit 10
```

## Next steps

- [architecture.md](architecture.md) for the two-service split.
- [campaigns.md](campaigns.md) for managing outreach.
- [sending.md](sending.md) for SMTP configuration and rate limiting.
