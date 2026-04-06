"""Pydantic v2 schemas for the Auto Marketer API."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CampaignCreate(BaseModel):
    name: str
    tone: str = "professional"
    goal: str


class CampaignOut(BaseModel):
    id: int
    name: str
    tone: str
    goal: str
    status: str
    created_at: datetime | None = None
    draft_count: int = 0


class GenerateRequest(BaseModel):
    profile_ids: list[str] | None = None
    status_filter: str = "completed"
    limit: int = Field(default=50, ge=1, le=500)
    workers: int = Field(default=3, ge=1, le=16)


class DraftOut(BaseModel):
    id: int
    campaign_id: int
    profile_id: str
    recipient_email: str | None = None
    recipient_name: str | None = None
    subject: str | None = None
    body: str | None = None
    status: str
    sent_at: datetime | None = None


class GenerateResponse(BaseModel):
    generated: int
    failed: int
    drafts: list[DraftOut]


class DraftUpdate(BaseModel):
    subject: str | None = None
    body: str | None = None


class SendRequest(BaseModel):
    provider: Literal["dry-run", "smtp", "noop"] = "dry-run"
    rate_limit_per_min: int = Field(default=30, ge=1, le=600)


class SendResponse(BaseModel):
    sent: int
    failed: int
    skipped: int
