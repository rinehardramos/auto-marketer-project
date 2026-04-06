"""End-to-end FastAPI tests with broker + DB stubbed."""
from __future__ import annotations

import os
from typing import Any

import pytest
from fastapi.testclient import TestClient


# ----- in-memory db stub --------------------------------------------------
class _FakeDB:
    def __init__(self):
        self.campaigns: dict[int, dict] = {}
        self.drafts: dict[int, dict] = {}
        self._next_c = 1
        self._next_d = 1

    def setup(self):
        pass

    def create_campaign(self, name, tone, goal):
        cid = self._next_c
        self._next_c += 1
        self.campaigns[cid] = {
            "id": cid, "name": name, "tone": tone, "goal": goal,
            "status": "draft", "created_at": None,
        }
        return cid

    def get_campaign(self, cid):
        c = self.campaigns.get(cid)
        if not c:
            return None
        c = dict(c)
        c["draft_count"] = sum(1 for d in self.drafts.values() if d["campaign_id"] == cid)
        return c

    def list_campaigns(self):
        out = []
        for c in self.campaigns.values():
            row = dict(c)
            row["draft_count"] = sum(1 for d in self.drafts.values() if d["campaign_id"] == c["id"])
            out.append(row)
        return out

    def update_campaign_status(self, cid, status):
        if cid in self.campaigns:
            self.campaigns[cid]["status"] = status

    def save_draft(self, campaign_id, profile_id, recipient_email, recipient_name, subject, body):
        did = self._next_d
        self._next_d += 1
        self.drafts[did] = {
            "id": did, "campaign_id": campaign_id, "profile_id": profile_id,
            "recipient_email": recipient_email, "recipient_name": recipient_name,
            "subject": subject, "body": body, "status": "draft",
            "provider_message_id": None, "error_message": None,
            "created_at": None, "sent_at": None,
        }
        return did

    def list_drafts(self, campaign_id, status=None):
        out = [d for d in self.drafts.values() if d["campaign_id"] == campaign_id]
        if status:
            out = [d for d in out if d["status"] == status]
        return out

    def get_draft(self, did):
        d = self.drafts.get(did)
        return dict(d) if d else None

    def update_draft(self, did, *, subject=None, body=None):
        d = self.drafts.get(did)
        if not d:
            return
        if subject is not None:
            d["subject"] = subject
        if body is not None:
            d["body"] = body

    def delete_draft(self, did):
        self.drafts.pop(did, None)

    def mark_sent(self, did, mid):
        d = self.drafts.get(did)
        if d:
            d["status"] = "sent"
            d["provider_message_id"] = mid

    def mark_failed(self, did, msg):
        d = self.drafts.get(did)
        if d:
            d["status"] = "failed"
            d["error_message"] = msg


class _FakeBroker:
    def list_profiles(self, status=None, limit=100, offset=0):
        return [
            {"id": "p1", "first_name": "Jane", "last_name": "Doe", "email": "jane@acme.com",
             "company": "Acme", "research_summary": "growing fast"},
            {"id": "p2", "first_name": "John", "last_name": "Roe", "email": "john@beta.io",
             "company": "Beta", "research_summary": "hiring"},
        ]

    def get_profile(self, pid):
        return {"id": pid, "first_name": "X", "last_name": "Y", "email": "x@y.com"}

    def search(self, q, top_k=20):
        return []


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AUTO_MARKETER_API_KEY", "secret")
    monkeypatch.setenv("AUTO_MARKETER_SKIP_DB_SETUP", "1")

    fake_db = _FakeDB()
    fake_broker = _FakeBroker()

    # Patch db module across every importer.
    from auto_marketer import db as real_db, sender as sender_mod
    from app.routers import campaigns as camp_router, drafts as draft_router
    from app import deps

    for target in (real_db, sender_mod, camp_router, draft_router):
        for name in (
            "setup", "create_campaign", "get_campaign", "list_campaigns",
            "update_campaign_status", "save_draft", "list_drafts", "get_draft",
            "update_draft", "delete_draft", "mark_sent", "mark_failed",
        ):
            if hasattr(target, "db"):
                pass
        # Replace the `db` attribute on modules that imported it.
    import auto_marketer.exporter as exp_mod
    monkeypatch.setattr(camp_router, "db", fake_db)
    monkeypatch.setattr(draft_router, "db", fake_db)
    monkeypatch.setattr(sender_mod, "db", fake_db)
    monkeypatch.setattr(exp_mod, "db", fake_db)

    deps.set_broker_client(fake_broker)

    # Stub email_generator to avoid LLM calls.
    from auto_marketer import email_generator
    def fake_batch(profiles, **kw):
        return [
            {
                "profile": p, "ok": True,
                "subject": f"Hi {p['first_name']}",
                "body": "personalized body",
                "recipient_email": p.get("email"),
                "recipient_name": f"{p['first_name']} {p['last_name']}",
                "error": None,
            }
            for p in profiles
        ]
    monkeypatch.setattr(camp_router, "generate_batch", fake_batch)

    from app.main import app
    return TestClient(app)


# -------------------------------------------------------------------- tests
def test_healthz_no_auth(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_campaigns_requires_api_key(client):
    r = client.get("/campaigns")
    assert r.status_code == 401


def test_full_flow(client):
    H = {"X-API-Key": "secret"}

    r = client.post("/campaigns", headers=H, json={"name": "Q1 push", "tone": "warm", "goal": "book demos"})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]

    r = client.post(f"/campaigns/{cid}/generate", headers=H, json={"limit": 10})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["generated"] == 2
    assert body["failed"] == 0
    assert len(body["drafts"]) == 2

    r = client.get(f"/campaigns/{cid}/drafts", headers=H)
    assert r.status_code == 200
    drafts = r.json()
    assert len(drafts) == 2

    did = drafts[0]["id"]
    r = client.patch(f"/drafts/{did}", headers=H, json={"subject": "Edited subj"})
    assert r.status_code == 200
    assert r.json()["subject"] == "Edited subj"

    r = client.post(f"/campaigns/{cid}/send", headers=H, json={"provider": "dry-run", "rate_limit_per_min": 600})
    assert r.status_code == 200, r.text
    counts = r.json()
    assert counts["sent"] == 2
    assert counts["failed"] == 0

    r = client.get(f"/campaigns/{cid}/export", headers=H, params={"format": "csv"})
    assert r.status_code == 200
    assert "recipient_email" in r.text

    r = client.get(f"/campaigns/{cid}/export", headers=H, params={"format": "json"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_unknown_campaign_404(client):
    H = {"X-API-Key": "secret"}
    r = client.get("/campaigns/9999", headers=H)
    assert r.status_code == 404
