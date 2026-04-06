"""Postgres campaign-state schema for auto-marketer.

The marketing service owns its own ``campaigns`` and ``email_drafts``
tables. info-broker has a separate schema; the two services do NOT share
tables. Run :func:`setup` once at startup to create them if missing.

All SQL is parameterized with ``%s``. The ``test_no_sql_string_formatting``
lint will fail otherwise — do not be tempted by f-strings.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg2
import psycopg2.extras

DB_NAME = os.getenv("POSTGRES_DB", "auto_marketer")
DB_USER = os.getenv("POSTGRES_USER", "user")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5433")


def get_connection():
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
    )


@contextmanager
def _conn() -> Iterator[Any]:
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


_CREATE_CAMPAIGNS = """
CREATE TABLE IF NOT EXISTS campaigns (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    tone VARCHAR NOT NULL DEFAULT 'professional',
    goal TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR DEFAULT 'draft'
)
"""

_CREATE_DRAFTS = """
CREATE TABLE IF NOT EXISTS email_drafts (
    id SERIAL PRIMARY KEY,
    campaign_id INT REFERENCES campaigns(id) ON DELETE CASCADE,
    profile_id VARCHAR NOT NULL,
    recipient_email VARCHAR,
    recipient_name VARCHAR,
    subject TEXT,
    body TEXT,
    status VARCHAR DEFAULT 'draft',
    provider_message_id VARCHAR,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    sent_at TIMESTAMP
)
"""

_CREATE_IDX_CAMPAIGN = (
    "CREATE INDEX IF NOT EXISTS email_drafts_campaign_idx ON email_drafts(campaign_id)"
)
_CREATE_IDX_STATUS = (
    "CREATE INDEX IF NOT EXISTS email_drafts_status_idx ON email_drafts(status)"
)


def setup() -> None:
    """Create the campaign tables if they do not already exist."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(_CREATE_CAMPAIGNS)
        cur.execute(_CREATE_DRAFTS)
        cur.execute(_CREATE_IDX_CAMPAIGN)
        cur.execute(_CREATE_IDX_STATUS)


# --------------------------------------------------------------- campaigns
def create_campaign(name: str, tone: str, goal: str) -> int:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO campaigns (name, tone, goal) VALUES (%s, %s, %s) RETURNING id",
            (name, tone, goal),
        )
        return int(cur.fetchone()[0])


def get_campaign(campaign_id: int) -> dict | None:
    with _conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT id, name, tone, goal, status, created_at FROM campaigns WHERE id = %s",
            (campaign_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        cur.execute(
            "SELECT COUNT(*) AS c FROM email_drafts WHERE campaign_id = %s",
            (campaign_id,),
        )
        row["draft_count"] = int(cur.fetchone()["c"])
        return dict(row)


def list_campaigns() -> list[dict]:
    with _conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT c.id, c.name, c.tone, c.goal, c.status, c.created_at, "
            "COUNT(d.id) AS draft_count "
            "FROM campaigns c LEFT JOIN email_drafts d ON d.campaign_id = c.id "
            "GROUP BY c.id ORDER BY c.created_at DESC"
        )
        return [dict(r) for r in cur.fetchall()]


def update_campaign_status(campaign_id: int, status: str) -> None:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE campaigns SET status = %s WHERE id = %s",
            (status, campaign_id),
        )


# ----------------------------------------------------------------- drafts
def save_draft(
    campaign_id: int,
    profile_id: str,
    recipient_email: str | None,
    recipient_name: str | None,
    subject: str | None,
    body: str | None,
) -> int:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO email_drafts "
            "(campaign_id, profile_id, recipient_email, recipient_name, subject, body) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (campaign_id, profile_id, recipient_email, recipient_name, subject, body),
        )
        return int(cur.fetchone()[0])


def list_drafts(campaign_id: int, status: str | None = None) -> list[dict]:
    with _conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if status is None:
            cur.execute(
                "SELECT * FROM email_drafts WHERE campaign_id = %s ORDER BY id",
                (campaign_id,),
            )
        else:
            cur.execute(
                "SELECT * FROM email_drafts WHERE campaign_id = %s AND status = %s ORDER BY id",
                (campaign_id, status),
            )
        return [dict(r) for r in cur.fetchall()]


def get_draft(draft_id: int) -> dict | None:
    with _conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM email_drafts WHERE id = %s", (draft_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def update_draft(draft_id: int, *, subject: str | None = None, body: str | None = None) -> None:
    if subject is None and body is None:
        return
    with _conn() as conn:
        cur = conn.cursor()
        if subject is not None and body is not None:
            cur.execute(
                "UPDATE email_drafts SET subject = %s, body = %s WHERE id = %s",
                (subject, body, draft_id),
            )
        elif subject is not None:
            cur.execute(
                "UPDATE email_drafts SET subject = %s WHERE id = %s",
                (subject, draft_id),
            )
        else:
            cur.execute(
                "UPDATE email_drafts SET body = %s WHERE id = %s",
                (body, draft_id),
            )


def delete_draft(draft_id: int) -> None:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM email_drafts WHERE id = %s", (draft_id,))


def mark_sent(draft_id: int, provider_message_id: str) -> None:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE email_drafts SET status = %s, provider_message_id = %s, sent_at = NOW() "
            "WHERE id = %s",
            ("sent", provider_message_id, draft_id),
        )


def mark_failed(draft_id: int, error_message: str) -> None:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE email_drafts SET status = %s, error_message = %s WHERE id = %s",
            ("failed", error_message, draft_id),
        )
