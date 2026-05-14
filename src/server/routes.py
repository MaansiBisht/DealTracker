"""HTTP routes for the DealTracker ops console."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import current_user, optional_current_user
from .db import get_session
from .events import bus
from . import magic_link
from .models import Event, Job, User
from .schemas import (
    AuthMeResponse,
    EventOut,
    HealthOut,
    JobCreate,
    JobOut,
    MagicLinkRequest,
    UserOut,
)
from .scheduler import schedule_job, unschedule_job
from .sessions import login_user, logout_user
from . import telegram as tg

# Reuse existing platform routing logic from the scrapers package.
from ..scrapers import HOTEL_PLATFORMS, SCRAPERS, get_platform_from_url
from ..utils.url_normalizer import normalize_url
from ..utils.booking_url import strip_dates as strip_booking_dates

# Email sender — re-used from the alerts pipeline without modification.
from ..utils.email import send_email


VERSION = "0.0.1"

log = logging.getLogger("dealtracker.auth.routes")

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
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
) -> list[Job]:
    stmt = select(Job).order_by(Job.created_at.desc())
    if kind:
        stmt = stmt.where(Job.kind == kind)
    if not include_inactive:
        stmt = stmt.where(Job.active.is_(True))
    if not user.is_admin:
        stmt = stmt.where(Job.user_id == user.id)
    return list(db.scalars(stmt).all())


@router.post("/jobs", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
) -> Job:
    # Resolve share/short links (amzn.in/d/…, fkrt.it/…, a.co/d/…) up front
    # so the user sees a recognisable URL in the watch list AND so the
    # platform-detection gate accepts them. Falls back to the original URL
    # on any network failure; Selenium follows redirects at scrape time too.
    canonical_url = normalize_url(payload.url)
    platform = get_platform_from_url(canonical_url)
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

    # Night-range watches: only valid for hotels, only on Booking (Phase 1).
    # Strip any checkin/checkout query params the user pasted — the runner
    # injects them per-night.
    if payload.date_start and payload.date_end:
        if kind != "hotel":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="date range is only supported for hotel watches",
            )
        if platform != "booking":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="date range is only supported for Booking.com today",
            )
        canonical_url = strip_booking_dates(canonical_url)

    job = Job(
        kind=kind,
        url=canonical_url,
        user_id=user.id,
        email=payload.email,
        webhook_url=payload.webhook_url,
        telegram_chat_id=payload.telegram_chat_id,
        alert_type=payload.alert_type,
        threshold=payload.threshold,
        platform=platform,
        status="pending",
        active=True,
        date_start=payload.date_start,
        date_end=payload.date_end,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    schedule_job(job.id, job.kind)
    return job


@router.post("/jobs/{job_id}/stop", response_model=JobOut)
def stop_job(
    job_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")

    # Admin can stop anything; everyone else only their own watches.
    if not user.is_admin and job.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="not authorised to stop this job",
        )

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
def telegram_status(_user: User = Depends(current_user)) -> dict:
    configured = tg.is_configured()
    return {
        "configured": configured,
        "bot_username": tg.bot_username() if configured else None,
    }


@router.post("/telegram/start-pairing")
def telegram_start_pairing(user: User = Depends(current_user)) -> dict:
    if not tg.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="telegram bot not configured",
        )
    return tg.start_pairing(user_id=user.id)


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request) -> dict:
    """Inbound endpoint Telegram POSTs each update to.

    Auth: Telegram echoes our pre-shared secret in the
    `X-Telegram-Bot-Api-Secret-Token` header. Missing or wrong header
    returns 404 so scanners on the path see no signal the endpoint
    exists. Constant-time compare on the secret.
    """
    expected = tg.webhook_secret()
    if not expected:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    presented = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    import hmac as _hmac
    if not _hmac.compare_digest(presented, expected):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    try:
        payload = await request.json()
    except Exception:
        return {"ok": True}  # malformed body — ack and move on

    try:
        tg.handle_update(payload)
    except Exception as e:
        # Never raise back to Telegram; that would trigger retries we don't want.
        log.warning("telegram webhook handler raised: %s", e)
    return {"ok": True}


@router.get("/telegram/pairing/{token}")
def telegram_pairing_status(
    token: str,
    _user: User = Depends(current_user),
) -> dict:
    return tg.pairing_status(token)


@router.get("/telegram/connection")
def telegram_connection(user: User = Depends(current_user)) -> dict:
    """Read the user's persistent Telegram pairing (set after a /start)."""
    return {
        "paired": user.telegram_chat_id is not None,
        "chat_id": user.telegram_chat_id,
        "display_name": user.telegram_display_name,
    }


@router.post("/telegram/disconnect")
def telegram_disconnect(
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
) -> dict:
    """Forget the user's persistent pairing; new watches need a fresh Connect."""
    user.telegram_chat_id = None
    user.telegram_display_name = None
    db.add(user)
    db.commit()
    return {"ok": True}


# ---- Events -----------------------------------------------------------------

@router.get("/events/recent", response_model=list[EventOut])
def recent_events(
    limit: int = Query(default=100, ge=1, le=500),
    job_id: str | None = Query(default=None),
    kind: str | None = Query(default=None, pattern="^(product|hotel)$"),
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
) -> list[dict]:
    # JOIN with jobs so each event carries job_kind + platform — SSE
    # consumers filter on kind without a second round-trip. The same JOIN
    # is the natural place to filter by Job.user_id for non-admins.
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
    if not user.is_admin:
        stmt = stmt.where(Job.user_id == user.id)

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
async def stream_events(user: User = Depends(current_user)) -> StreamingResponse:
    """Server-Sent Events stream of every tick event, live as they fire.

    Admin subscribers receive every event; everyone else sees only events
    tied to their own jobs (and never the orphan-NULL-user events that
    might still exist before the admin claim sweep runs).
    """
    is_admin = user.is_admin
    user_id = user.id

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
                    if not is_admin and payload.get("user_id") != user_id:
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


# ---- Auth (magic-link) -----------------------------------------------------


def _build_login_link(token: str) -> str:
    base = os.getenv("APP_BASE_URL", "http://localhost:8000").rstrip("/")
    return f"{base}/api/auth/verify?token={token}"


def _send_magic_link(email: str, token: str) -> None:
    """Reuse the alerts SMTP path for the login link email."""
    link = _build_login_link(token)
    subject = "Your DealTracker login link"
    body = (
        f"Hi,\n\n"
        f"Click the link below to sign in to DealTracker. The link is "
        f"valid for {magic_link.TOKEN_TTL_MINUTES} minutes and can only "
        f"be used once.\n\n"
        f"{link}\n\n"
        f"If you didn't request this, you can safely ignore the message.\n"
    )
    send_email(subject=subject, body=body, recipient_email=email)


@router.post("/auth/request-magic-link")
def request_magic_link(
    payload: MagicLinkRequest,
    request: Request,
    db: Session = Depends(get_session),
) -> dict:
    """Issue a one-time login link and email it to the requester."""
    ip = request.client.host if request.client else None
    try:
        issued = magic_link.issue_token(db, payload.email, ip)
    except magic_link.RateLimitedError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"too many requests ({exc.scope}); try again later",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        )

    try:
        _send_magic_link(payload.email, issued.token)
    except Exception as exc:  # noqa: BLE001 — SMTP failures vary by provider
        log.error("magic-link email send failed for %s: %s", payload.email, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="could not send login email — operator should check SMTP config",
        )

    return {"ok": True}


@router.get("/auth/verify")
def verify_magic_link(
    token: str,
    request: Request,
    db: Session = Depends(get_session),
) -> RedirectResponse:
    """Consume the token, set the session cookie, redirect to the app."""
    base = os.getenv("APP_BASE_URL", "http://localhost:8000").rstrip("/")
    try:
        user = magic_link.consume_token(db, token)
    except magic_link.TokenInvalidError as exc:
        # Land back on the SPA's sign-in screen with a hint in the URL.
        return RedirectResponse(url=f"{base}/?login_error={exc.reason}", status_code=303)

    login_user(request, user.id)
    return RedirectResponse(url=f"{base}/", status_code=303)


@router.get("/auth/me", response_model=AuthMeResponse)
def auth_me(
    user: User | None = Depends(optional_current_user),
) -> AuthMeResponse:
    """Return the current user plus Telegram-bot configuration in one shot."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not authenticated",
        )
    configured = tg.is_configured()
    return AuthMeResponse(
        user=UserOut.model_validate(user),
        telegram_bot_username=tg.bot_username() if configured else None,
        telegram_bot_configured=configured,
    )


@router.post("/auth/logout")
def auth_logout(request: Request) -> dict:
    """Clear the session cookie. Idempotent — works whether signed in or not."""
    logout_user(request)
    return {"ok": True}
