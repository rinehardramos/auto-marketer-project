"""Campaign export helpers (CSV / XLSX / JSON)."""
from __future__ import annotations

import io
import json

import pandas as pd

from auto_marketer import db
from security import escape_dataframe_cells

EXPORT_COLUMNS = [
    "id",
    "campaign_id",
    "profile_id",
    "recipient_email",
    "recipient_name",
    "subject",
    "body",
    "status",
    "provider_message_id",
    "error_message",
    "created_at",
    "sent_at",
]


def _drafts_dataframe(campaign_id: int) -> pd.DataFrame:
    rows = db.list_drafts(campaign_id)
    df = pd.DataFrame(rows, columns=EXPORT_COLUMNS) if rows else pd.DataFrame(columns=EXPORT_COLUMNS)
    return df


def export_campaign(campaign_id: int, fmt: str) -> tuple[bytes, str, str]:
    """Return ``(payload_bytes, content_type, filename)``."""
    fmt = fmt.lower()
    df = _drafts_dataframe(campaign_id)

    if fmt == "csv":
        safe = escape_dataframe_cells(df.copy())
        buf = io.StringIO()
        safe.to_csv(buf, index=False)
        return (
            buf.getvalue().encode("utf-8"),
            "text/csv",
            f"campaign-{campaign_id}.csv",
        )
    if fmt == "xlsx":
        safe = escape_dataframe_cells(df.copy())
        buf = io.BytesIO()
        safe.to_excel(buf, index=False, engine="openpyxl")
        return (
            buf.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            f"campaign-{campaign_id}.xlsx",
        )
    if fmt == "json":
        records = df.to_dict(orient="records")
        return (
            json.dumps(records, indent=2, default=str).encode("utf-8"),
            "application/json",
            f"campaign-{campaign_id}.json",
        )
    raise ValueError(f"Unsupported export format: {fmt!r}")
