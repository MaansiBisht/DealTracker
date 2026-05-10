"""HTTP routes for the DealTracker ops console."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import require_user
from .db import get_session
from .models import Event, Job
from .schemas import EventOut, HealthOut, JobCreate, JobOut

# Reuse existing platform routing logic from the scrapers package.
from src.scrapers import HOTEL_PLATFORMS, get_platform_from_url


VERSION = "0.0.1"

router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(status="ok", version=VERSION)


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
        alert_type=payload.alert_type,
        threshold=payload.threshold,
        platform=platform,
        status="pending",
        active=True,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
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
    return job


@router.get("/events/recent", response_model=list[EventOut])
def recent_events(
    limit: int = Query(default=100, ge=1, le=500),
    job_id: str | None = Query(default=None),
    _user: str = Depends(require_user),
    db: Session = Depends(get_session),
) -> list[Event]:
    stmt = select(Event).order_by(Event.id.desc()).limit(limit)
    if job_id:
        stmt = stmt.where(Event.job_id == job_id)
    rows = list(db.scalars(stmt).all())
    rows.reverse()
    return rows
