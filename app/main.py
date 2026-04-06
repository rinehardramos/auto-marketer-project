from __future__ import annotations

import logging
import os

from fastapi import FastAPI

from app.routers import campaigns, drafts, health
from auto_marketer import db

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

app = FastAPI(
    title="Auto Marketer API",
    version="0.4.0",
    description=(
        "Personalized cold email generation and bulk sending. "
        "Consumes profiles from info-broker."
    ),
)

app.include_router(health.router)
app.include_router(campaigns.router)
app.include_router(drafts.router)


@app.on_event("startup")
def _startup() -> None:
    if os.getenv("AUTO_MARKETER_SKIP_DB_SETUP") == "1":
        return
    try:
        db.setup()
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning("DB setup skipped: %s", exc)
