from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.deps import get_api_key, get_broker_client
from app.schemas import (
    CampaignCreate,
    CampaignOut,
    GenerateRequest,
    GenerateResponse,
    DraftOut,
    SendRequest,
    SendResponse,
)
from auto_marketer import db, exporter, sender as sender_mod
from auto_marketer.email_generator import generate_batch
from auto_marketer.info_broker_client import InfoBrokerClient

router = APIRouter(prefix="/campaigns", tags=["campaigns"], dependencies=[Depends(get_api_key)])


@router.post("", response_model=CampaignOut, status_code=201)
def create_campaign(payload: CampaignCreate) -> CampaignOut:
    cid = db.create_campaign(payload.name, payload.tone, payload.goal)
    row = db.get_campaign(cid)
    assert row is not None
    return CampaignOut(**row)


@router.get("", response_model=list[CampaignOut])
def list_campaigns() -> list[CampaignOut]:
    return [CampaignOut(**c) for c in db.list_campaigns()]


@router.get("/{campaign_id}", response_model=CampaignOut)
def get_campaign(campaign_id: int) -> CampaignOut:
    row = db.get_campaign(campaign_id)
    if not row:
        raise HTTPException(404, detail="campaign not found")
    return CampaignOut(**row)


@router.post("/{campaign_id}/generate", response_model=GenerateResponse)
def generate_campaign(
    campaign_id: int,
    req: GenerateRequest,
    broker: InfoBrokerClient = Depends(get_broker_client),
) -> GenerateResponse:
    campaign = db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(404, detail="campaign not found")

    if req.profile_ids:
        profiles = [broker.get_profile(pid) for pid in req.profile_ids]
    else:
        profiles = broker.list_profiles(status=req.status_filter, limit=req.limit)

    db.update_campaign_status(campaign_id, "generating")
    results = generate_batch(
        profiles,
        workers=req.workers,
        tone=campaign["tone"],
        goal=campaign["goal"],
    )

    drafts_out: list[DraftOut] = []
    generated = failed = 0
    for r in results:
        prof = r["profile"] or {}
        prof_id = str(prof.get("id") or prof.get("profile_id") or "")
        draft_id = db.save_draft(
            campaign_id=campaign_id,
            profile_id=prof_id,
            recipient_email=r["recipient_email"],
            recipient_name=r["recipient_name"],
            subject=r["subject"],
            body=r["body"],
        )
        if r["ok"]:
            generated += 1
        else:
            failed += 1
            db.mark_failed(draft_id, r["error"] or "unknown error")
        row = db.get_draft(draft_id)
        if row:
            drafts_out.append(DraftOut(**row))

    db.update_campaign_status(campaign_id, "ready")
    return GenerateResponse(generated=generated, failed=failed, drafts=drafts_out)


@router.post("/{campaign_id}/send", response_model=SendResponse)
def send_campaign(campaign_id: int, req: SendRequest) -> SendResponse:
    if not db.get_campaign(campaign_id):
        raise HTTPException(404, detail="campaign not found")
    dry_run = req.provider == "dry-run"
    impl = sender_mod.build_sender(req.provider)
    counts = sender_mod.send_campaign(
        campaign_id,
        impl,
        rate_limit_per_min=req.rate_limit_per_min,
        dry_run=dry_run,
    )
    return SendResponse(**counts)


@router.get("/{campaign_id}/export")
def export_campaign(campaign_id: int, format: str = Query("csv", pattern="^(csv|xlsx|json)$")):
    if not db.get_campaign(campaign_id):
        raise HTTPException(404, detail="campaign not found")
    payload, ctype, filename = exporter.export_campaign(campaign_id, format)
    return Response(
        content=payload,
        media_type=ctype,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
