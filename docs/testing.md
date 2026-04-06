# Testing

The project uses `pytest` with `pytest-mock` for unit and integration testing.

## Running tests

The recommended way to run tests is via `uv`:

```bash
# Run all tests
uv run pytest

# Run with coverage (if configured)
uv run pytest --cov=app --cov=auto_marketer

# Run specific tests
uv run pytest tests/test_api.py
```

## Test Structure

| File | What it tests |
|---|---|
| `tests/test_api.py` | FastAPI endpoints (using `TestClient`). |
| `tests/test_db.py` | PostgreSQL interactions, parameterized SQL enforcement. |
| `tests/test_email_generator.py` | LLM prompt formatting, JSON parsing of LLM output. |
| `tests/test_info_broker_client.py` | REST interactions with the sibling `info-broker` service (mocked). |
| `tests/test_sender.py` | SMTP and DryRun email sending logic. |
| `test_no_sql_string_formatting.py` | AST-based lint that forbids f-strings or `.format()` in SQL `execute()` calls. |
| `test_security.py` | Security controls: SSRF protection, CSV injection guards, NUL-byte scrubbing. |

## Mocking

- **LLM Calls:** Mocked using `unittest.mock` to avoid external API dependencies and costs.
- **info-broker:** The `InfoBrokerClient` is mocked in most tests to ensure the marketing layer can be tested in isolation.
- **SMTP:** The `Sender` class is tested with a `NoopSender` or `DryRunSender` to prevent accidental outreach during development.
