from __future__ import annotations

from unittest.mock import patch

import pytest

from auto_marketer import sender as sender_mod
from auto_marketer.sender import DryRunSender, NoopSender, build_sender


def test_dry_run_sender_returns_id():
    s = DryRunSender()
    out = s.send("a@b.com", "A B", "subj", "body")
    assert out.startswith("dryrun-")


def test_noop_sender():
    assert NoopSender().send("a@b.com", "A B", "s", "b") == "noop-message-id"


def test_build_sender_unknown_raises():
    with pytest.raises(ValueError):
        build_sender("carrier-pigeon")


def test_smtp_sender_requires_env(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_FROM", raising=False)
    with pytest.raises(RuntimeError):
        build_sender("smtp")


def test_smtp_sender_constructs_with_env(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_FROM", "from@test")
    s = build_sender("smtp")
    assert s.host == "smtp.test"
    assert s.from_addr == "from@test"


def test_send_campaign_rate_limits_and_records(monkeypatch):
    drafts = [
        {"id": 1, "status": "draft", "recipient_email": "a@x.com", "recipient_name": "A", "subject": "s", "body": "b"},
        {"id": 2, "status": "draft", "recipient_email": "b@x.com", "recipient_name": "B", "subject": "s", "body": "b"},
        {"id": 3, "status": "draft", "recipient_email": "", "recipient_name": "", "subject": "s", "body": "b"},
    ]
    sleep_calls: list[float] = []
    sent_ids: list[int] = []
    failed: list[tuple[int, str]] = []

    monkeypatch.setattr(sender_mod, "db", type("D", (), {
        "list_drafts": staticmethod(lambda cid: drafts),
        "mark_sent": staticmethod(lambda did, mid: sent_ids.append(did)),
        "mark_failed": staticmethod(lambda did, msg: failed.append((did, msg))),
        "update_campaign_status": staticmethod(lambda *a, **k: None),
    }))
    monkeypatch.setattr(sender_mod.time, "sleep", lambda d: sleep_calls.append(d))

    counts = sender_mod.send_campaign(1, DryRunSender(), rate_limit_per_min=60, dry_run=True)

    assert counts["sent"] == 2
    assert counts["failed"] == 1  # missing email
    assert sent_ids == [1, 2]
    assert failed[0][0] == 3
    # Two iterations between three drafts → at most 2 sleeps.
    assert len(sleep_calls) <= 2


def test_send_campaign_records_send_exceptions(monkeypatch):
    drafts = [
        {"id": 5, "status": "draft", "recipient_email": "a@x.com", "recipient_name": "A", "subject": "s", "body": "b"},
    ]
    failed: list[tuple[int, str]] = []
    monkeypatch.setattr(sender_mod, "db", type("D", (), {
        "list_drafts": staticmethod(lambda cid: drafts),
        "mark_sent": staticmethod(lambda did, mid: None),
        "mark_failed": staticmethod(lambda did, msg: failed.append((did, msg))),
        "update_campaign_status": staticmethod(lambda *a, **k: None),
    }))
    monkeypatch.setattr(sender_mod.time, "sleep", lambda d: None)

    class Boom(DryRunSender):
        def send(self, *a, **k):
            raise RuntimeError("smtp down")

    # dry_run=False so our subclass actually runs
    counts = sender_mod.send_campaign(1, Boom(), rate_limit_per_min=60, dry_run=False)
    assert counts["failed"] == 1
    assert failed and "smtp down" in failed[0][1]
