from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.deps import get_api_key
from app.schemas import DraftOut, DraftUpdate
from auto_marketer import db

router = APIRouter(tags=["drafts"], dependencies=[Depends(get_api_key)])


@router.get("/campaigns/{campaign_id}/drafts", response_model=list[DraftOut])
def list_drafts(campaign_id: int, status: str | None = None) -> list[DraftOut]:
    return [DraftOut(**d) for d in db.list_drafts(campaign_id, status=status)]


@router.get("/drafts/{draft_id}", response_model=DraftOut)
def get_draft(draft_id: int) -> DraftOut:
    row = db.get_draft(draft_id)
    if not row:
        raise HTTPException(404, detail="draft not found")
    return DraftOut(**row)


@router.patch("/drafts/{draft_id}", response_model=DraftOut)
def update_draft(draft_id: int, payload: DraftUpdate) -> DraftOut:
    if db.get_draft(draft_id) is None:
        raise HTTPException(404, detail="draft not found")
    db.update_draft(draft_id, subject=payload.subject, body=payload.body)
    row = db.get_draft(draft_id)
    assert row is not None
    return DraftOut(**row)


@router.delete("/drafts/{draft_id}", status_code=204)
def delete_draft(draft_id: int) -> None:
    if db.get_draft(draft_id) is None:
        raise HTTPException(404, detail="draft not found")
    db.delete_draft(draft_id)
