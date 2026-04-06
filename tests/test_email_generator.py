from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from auto_marketer import email_generator


def _mock_client(content: str) -> MagicMock:
    client = MagicMock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )
    return client


def test_generate_email_parses_json():
    client = _mock_client('{"subject": "Hi Acme", "body": "Hello there."}')
    out = email_generator.generate_email(
        {"first_name": "Jane", "last_name": "Doe", "company": "Acme", "research_summary": "growth"},
        client=client,
    )
    assert out == {"subject": "Hi Acme", "body": "Hello there."}


def test_generate_email_strips_code_fences():
    client = _mock_client('```json\n{"subject": "S", "body": "B"}\n```')
    out = email_generator.generate_email({"first_name": "J", "last_name": "D"}, client=client)
    assert out["subject"] == "S" and out["body"] == "B"


def test_generate_email_raises_on_garbage():
    client = _mock_client("not json at all")
    with pytest.raises(ValueError):
        email_generator.generate_email({"first_name": "J", "last_name": "D"}, client=client)


def test_generate_batch_parallel_collects_failures():
    profiles = [
        {"id": "a", "first_name": "A", "last_name": "X"},
        {"id": "b", "first_name": "B", "last_name": "Y"},
        {"id": "c", "first_name": "C", "last_name": "Z"},
    ]
    calls = {"n": 0}

    def fake_generate(prof, **kw):
        calls["n"] += 1
        if prof["id"] == "b":
            raise RuntimeError("boom")
        return {"subject": f"S-{prof['id']}", "body": "B"}

    orig = email_generator.generate_email
    email_generator.generate_email = fake_generate  # type: ignore
    try:
        results = email_generator.generate_batch(profiles, workers=3)
    finally:
        email_generator.generate_email = orig  # type: ignore

    by_id = {r["profile"]["id"]: r for r in results}
    assert by_id["a"]["ok"] is True
    assert by_id["b"]["ok"] is False and "boom" in by_id["b"]["error"]
    assert by_id["c"]["ok"] is True
    assert calls["n"] == 3
