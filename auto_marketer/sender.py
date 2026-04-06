"""Pluggable email senders for bulk campaigns.

The default sender is :class:`DryRunSender` so an accidental
``send_campaign`` call will never put real mail on the wire.
"""
from __future__ import annotations

import logging
import os
import smtplib
import time
import uuid
from email.message import EmailMessage
from typing import Protocol

from auto_marketer import db

log = logging.getLogger(__name__)


class EmailSender(Protocol):
    def send(self, to_email: str, to_name: str, subject: str, body: str) -> str:
        """Send one email and return the provider's message id."""


# --------------------------------------------------------------- providers
class DryRunSender:
    """Logs the email it would have sent and returns a fake message id."""

    def send(self, to_email: str, to_name: str, subject: str, body: str) -> str:
        log.info(
            "[dry-run] would send to=%s name=%s subject=%r body_len=%d",
            to_email,
            to_name,
            subject,
            len(body or ""),
        )
        return f"dryrun-{uuid.uuid4().hex[:12]}"


class NoopSender:
    """Sends nothing, returns a deterministic id. For tests."""

    def send(self, to_email: str, to_name: str, subject: str, body: str) -> str:
        return "noop-message-id"


class SMTPSender:
    """Real SMTP sender. Reads SMTP_* env vars at construction time."""

    def __init__(self) -> None:
        self.host = os.getenv("SMTP_HOST", "")
        self.port = int(os.getenv("SMTP_PORT", "587"))
        self.user = os.getenv("SMTP_USER", "")
        self.password = os.getenv("SMTP_PASSWORD", "")
        self.from_addr = os.getenv("SMTP_FROM", self.user)
        self.use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes")
        if not self.host or not self.from_addr:
            raise RuntimeError("SMTPSender requires SMTP_HOST and SMTP_FROM")

    def send(self, to_email: str, to_name: str, subject: str, body: str) -> str:
        if not to_email:
            raise ValueError("recipient email is empty")
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.from_addr
        msg["To"] = f"{to_name} <{to_email}>" if to_name else to_email
        msg.set_content(body)

        with smtplib.SMTP(self.host, self.port, timeout=30) as smtp:
            smtp.ehlo()
            if self.use_tls:
                smtp.starttls()
                smtp.ehlo()
            if self.user and self.password:
                smtp.login(self.user, self.password)
            smtp.send_message(msg)
        # smtplib doesn't return a server-side id; synthesize a stable one.
        return f"smtp-{uuid.uuid4().hex[:12]}"


# ----------------------------------------------------------------- factory
def build_sender(kind: str = "dry-run") -> EmailSender:
    kind = (kind or "dry-run").lower()
    if kind == "dry-run":
        return DryRunSender()
    if kind == "noop":
        return NoopSender()
    if kind == "smtp":
        return SMTPSender()
    raise ValueError(f"Unknown sender kind: {kind!r}")


# ------------------------------------------------------------ orchestrator
def send_campaign(
    campaign_id: int,
    sender: EmailSender,
    *,
    rate_limit_per_min: int = 30,
    dry_run: bool = True,
) -> dict[str, int]:
    """Send all unsent drafts in a campaign.

    Drafts in status ``draft`` or ``queued`` are eligible. Each send is
    rate-limited; per-row failures are recorded against the draft and the
    loop continues.
    """
    if dry_run and not isinstance(sender, DryRunSender):
        sender = DryRunSender()

    drafts = [
        d for d in db.list_drafts(campaign_id) if d["status"] in ("draft", "queued")
    ]
    sent = failed = skipped = 0
    delay = 60.0 / rate_limit_per_min if rate_limit_per_min > 0 else 0.0

    db.update_campaign_status(campaign_id, "sending")

    for i, draft in enumerate(drafts):
        if not draft.get("recipient_email"):
            db.mark_failed(draft["id"], "missing recipient_email")
            failed += 1
            skipped += 1
            continue
        try:
            msg_id = sender.send(
                draft["recipient_email"],
                draft.get("recipient_name") or "",
                draft.get("subject") or "",
                draft.get("body") or "",
            )
            db.mark_sent(draft["id"], msg_id)
            sent += 1
        except Exception as exc:  # noqa: BLE001 — recorded per-row
            log.warning("send failed for draft %s: %s", draft["id"], exc)
            db.mark_failed(draft["id"], str(exc))
            failed += 1

        if i < len(drafts) - 1 and delay > 0:
            time.sleep(delay)

    db.update_campaign_status(campaign_id, "sent" if failed == 0 else "failed")
    return {"sent": sent, "failed": failed, "skipped": skipped}
