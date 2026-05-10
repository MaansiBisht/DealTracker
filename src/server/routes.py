"""HTTP routes for the DealTracker ops console."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import require_user
from .db import get_session
from .events import bus
from .models import Event, Job
from .schemas import EventOut, HealthOut, JobCreate, JobOut
from .scheduler import schedule_job, unschedule_job
from . import telegram as tg

# Reuse existing platform routing logic from the scrapers package.
from ..scrapers import HOTEL_PLATFORMS, SCRAPERS, get_platform_from_url


VERSION = "0.0.1"

router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(status="ok", version=VERSION)


@router.get("/platforms")
def list_platforms() -> dict[str, list[str]]:
    """Platforms the scrapers currently support, grouped by job kind."""
    products = sorted(p for p in SCRAPERS if p not in HOTEL_PLATFORMS)
    hotels = sorted(p for p in SCRAPERS if p in HOTEL_PLATFORMS)
    return {"product": products, "hotel": hotels}


@router.get("/jobs", response_model=list[JobOut])
def list_jobs(
    kind: str | None = Query(default=None, pattern="^(product|hotel)$"),
    include_inactive: bool = Query(default=False),
    _user: str = Depends(require_user),
    db: Session = Depends(get_session),
) -> list[Job]:
    stmt = select(Job).order_by(Job.created_at.desc())
    if kind:
        stmt = stmt.where(Job.kind == kind)
    if not include_inactive:
        stmt = stmt.where(Job.active.is_(True))
    return list(db.scalars(stmt).all())


@router.post("/jobs", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreate,
    _user: str = Depends(require_user),
    db: Session = Depends(get_session),
) -> Job:
    platform = get_platform_from_url(payload.url)
    if platform == "unknown":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="unsupported platform — URL must be from a recognised site",
        )

    kind = "hotel" if platform in HOTEL_PLATFORMS else "product"

    if kind == "hotel" and payload.alert_type != "price_drop":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="hotel watches must use alert_type=price_drop",
        )
    if kind == "product" and payload.alert_type not in ("stock", "price"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="product watches must use alert_type=stock or price",
        )
    if payload.alert_type in ("price", "price_drop") and payload.threshold is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="price alerts require a threshold",
        )

    job = Job(
        kind=kind,
        url=payload.url,
        email=payload.email,
        webhook_url=payload.webhook_url,
        telegram_chat_id=payload.telegram_chat_id,
        alert_type=payload.alert_type,
        threshold=payload.threshold,
        platform=platform,
        status="pending",
        active=True,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    schedule_job(job.id, job.kind)
    return job


@router.post("/jobs/{job_id}/stop", response_model=JobOut)
def stop_job(
    job_id: str,
    _user: str = Depends(require_user),
    db: Session = Depends(get_session),
) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")

    job.active = False
    job.status = "stopped"
    db.add(Event(
        job_id=job.id,
        kind="job_stop",
        message="stopped by user",
        ts=datetime.now(timezone.utc),
    ))
    db.commit()
    db.refresh(job)

    unschedule_job(job.id)
    return job


# ---- Telegram --------------------------------------------------------------

@router.get("/telegram/status")
def telegram_status(_user: str = Depends(require_user)) -> dict:
    configured = tg.is_configured()
    return {
        "configured": configured,
        "bot_username": tg.bot_username() if configured else None,
    }


@router.post("/telegram/start-pairing")
def telegram_start_pairing(_user: str = Depends(require_user)) -> dict:
    if not tg.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="telegram bot not configured",
        )
    return tg.start_pairing()


@router.get("/telegram/pairing/{token}")
def telegram_pairing_status(
    token: str,
    _user: str = Depends(require_user),
) -> dict:
    return tg.pairing_status(token)


# ---- Events -----------------------------------------------------------------

@router.get("/events/recent", response_model=list[EventOut])
def recent_events(
    limit: int = Query(default=100, ge=1, le=500),
    job_id: str | None = Query(default=None),
    kind: str | None = Query(default=None, pattern="^(product|hotel)$"),
    _user: str = Depends(require_user),
    db: Session = Depends(get_session),
) -> list[dict]:
    # JOIN with jobs so each event carries job_kind + platform — SSE
    # consumers filter on kind without a second round-trip.
    stmt = (
        select(Event, Job.kind, Job.platform)
        .join(Job, Event.job_id == Job.id)
        .order_by(Event.id.desc())
        .limit(limit)
    )
    if job_id:
        stmt = stmt.where(Event.job_id == job_id)
    if kind:
        stmt = stmt.where(Job.kind == kind)

    rows: list[dict] = []
    for e, job_kind, platform in db.execute(stmt).all():
        rows.append({
            "id": e.id,
            "ts": e.ts,
            "job_id": e.job_id,
            "job_kind": job_kind,
            "platform": platform,
            "kind": e.kind,
            "message": e.message,
        })
    rows.reverse()  # oldest -> newest, ready for terminal append
    return rows


@router.get("/events/stream")
async def stream_events(_user: str = Depends(require_user)) -> StreamingResponse:
    """Server-Sent Events stream of every tick event, live as they fire."""

    async def event_source():
        async with bus.subscribe() as queue:
            # Tell the client we're listening (also forces the headers to flush).
            yield ": connected\n\n"
            try:
                while True:
                    try:
                        payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                    except asyncio.TimeoutError:
                        # Heartbeat — keeps proxies/CDNs from idling the connection out.
                        yield ": heartbeat\n\n"
                        continue
                    yield f"event: tick\ndata: {json.dumps(payload, default=str)}\n\n"
            except asyncio.CancelledError:
                # Client disconnected — clean up by exiting the context.
                raise

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable nginx buffering for SSE
        },
    )
