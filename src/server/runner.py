"""One-shot scrape execution.

Called by APScheduler at each tick. Opens a fresh Selenium driver (per
tick — Selenium isn't safe to share across long-lived sessions), runs
the appropriate scraper, persists results, and emits Event rows that
the SSE bus (step 5) will fan out to the terminal pane.
"""

from __future__ import annotations

import json
import logging
import os
import re
import traceback
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from .db import SessionLocal
from .events import bus
from .models import Event, Job

# Reuse existing scraper machinery.
from ..scrapers import route_scraper
from ..utils.driver import create_driver
from ..utils.email import send_email
from . import telegram as tg


log = logging.getLogger("dealtracker.runner")

# Fallback recipient when delivery to the user-entered address fails.
# Override via env; set to empty string to disable the fallback entirely.
FALLBACK_EMAIL = os.getenv("FALLBACK_EMAIL", "bishtmaansi004@gmail.com").strip()


# ---------- public entry point -------------------------------------------------

def run_tick(job_id: str) -> None:
    """Execute one scrape tick for the given job. Safe to call from any thread."""
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job is None or not job.active:
            return

        _emit(db, job, "tick_start", f"tick start · {job.platform}")
        job.status = "running"
        db.commit()

        result: dict[str, Any] | None = None
        scrape_error: str | None = None
        try:
            result = _do_scrape(job)
        except Exception as e:
            scrape_error = f"{type(e).__name__}: {e}"
            log.exception("scrape failed for job %s", job.id)

        if result is not None:
            _process_result(db, job, result)
        else:
            job.status = "error"
            _emit(db, job, "error", scrape_error or "unknown scrape failure")

        job.last_checked_at = _now()
        if job.status == "running":
            job.status = "idle"
        db.commit()

        _emit(db, job, "tick_done", _summary_for(job))
        db.commit()


# ---------- scraping -----------------------------------------------------------

def _do_scrape(job: Job) -> dict[str, Any]:
    """Single scrape pass — works for both products and hotels.

    Hotel URLs already carry checkin/checkout in the query string, so
    we scrape that one date pair, not 30 days.
    """
    driver = create_driver()
    try:
        result = route_scraper(driver, job.url)
        if result is None:
            raise RuntimeError("scraper returned no result")
        return result
    finally:
        try:
            driver.quit()
        except Exception:
            pass


# ---------- result handling ----------------------------------------------------

def _process_result(db: Session, job: Job, result: dict[str, Any]) -> None:
    """Single-shot result handler. Works for both products and hotels —
    they share the same {price, stock_status, title?} contract."""
    stock_status = (result.get("stock_status") or "unknown").lower()
    raw_price = result.get("price")
    job.last_status = stock_status
    job.last_price = str(raw_price) if raw_price is not None else None
    _emit(
        db, job, "tick_result",
        f"price={job.last_price or '—'} stock={stock_status}",
    )

    if job.alert_type == "stock":
        # Products only — "in stock" wording.
        if "in stock" in stock_status:
            _alert(db, job, f"in stock · {_human_price(job.last_price)}")
        return

    # price (products) and price_drop (hotels) share the same comparison.
    price_num = _parse_price(raw_price)
    if price_num is None or job.threshold is None:
        return
    if price_num <= job.threshold:
        label = "price drop" if job.kind == "hotel" else "price"
        _alert(
            db, job,
            f"{label} ₹{price_num:,.2f} ≤ threshold ₹{job.threshold:,.2f}",
        )


def _alert(db: Session, job: Job, reason: str) -> None:
    """Mark the job alerted, then fan out to each configured channel.

    Both email and webhook can fire on the same alert — each is
    independent, each emits its own success/failure event so the
    operator log shows exactly what got through.
    """
    job.status = "alerted"
    job.alerted_at = _now()
    job.active = False

    delivered_anywhere = False

    if job.email:
        delivered_anywhere |= _deliver_email(db, job, reason)
    if job.webhook_url:
        delivered_anywhere |= _deliver_webhook(db, job, reason)
    if job.telegram_chat_id:
        delivered_anywhere |= _deliver_telegram(db, job, reason)

    if not delivered_anywhere:
        # Alert state is correct (condition was met) even if every
        # channel rejected; surface that loudly.
        _emit(db, job, "alert", f"ALERT (all channels failed) — {reason}")


def _deliver_email(db: Session, job: Job, reason: str) -> bool:
    """Email channel — primary recipient with a configurable fallback."""
    body = (
        f"DealTracker alert\n\n"
        f"Reason: {reason}\n"
        f"Platform: {job.platform}\n"
        f"URL: {job.url}\n"
    )
    subject = f"DealTracker · {job.platform} alert"

    try:
        send_email(subject=subject, body=body, recipient_email=job.email)
        _emit(db, job, "alert", f"ALERT EMAIL SENT to {job.email} — {reason}")
        return True
    except Exception as primary_err:
        _emit(
            db, job, "error",
            f"email delivery to {job.email} failed: {type(primary_err).__name__}: {primary_err}",
        )
        log.warning("primary email failed for job %s: %s", job.id, traceback.format_exc())

    if FALLBACK_EMAIL and FALLBACK_EMAIL.lower() != (job.email or "").lower():
        fallback_body = body + f"\n[fallback delivery — primary {job.email} did not accept]\n"
        try:
            send_email(subject=subject, body=fallback_body, recipient_email=FALLBACK_EMAIL)
            _emit(db, job, "alert", f"ALERT EMAIL SENT to fallback {FALLBACK_EMAIL} — {reason}")
            return True
        except Exception as fb_err:
            _emit(
                db, job, "error",
                f"fallback email to {FALLBACK_EMAIL} failed: {type(fb_err).__name__}: {fb_err}",
            )
            log.warning("fallback email failed for job %s: %s", job.id, traceback.format_exc())

    return False


def _deliver_webhook(db: Session, job: Job, reason: str) -> bool:
    """Generic outbound webhook — POSTs a JSON payload with timeout=8s.

    Payload is intentionally flat and bridge-friendly (n8n, Zapier,
    IFTTT, custom Telegram bots, etc.) so any of those can pluck the
    fields they need without parsing nested structures.
    """
    payload = {
        "type": "dealtracker.alert",
        "ts": _now().isoformat(),
        "reason": reason,
        "job": {
            "id": job.id,
            "kind": job.kind,
            "platform": job.platform,
            "url": job.url,
            "alert_type": job.alert_type,
            "threshold": job.threshold,
            "last_status": job.last_status,
            "last_price": job.last_price,
        },
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        job.webhook_url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "DealTracker/0.0.1",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            status = resp.status
        if 200 <= status < 300:
            _emit(
                db, job, "alert",
                f"WEBHOOK POSTED ({status}) to {_redact_url(job.webhook_url)} — {reason}",
            )
            return True
        _emit(
            db, job, "error",
            f"webhook to {_redact_url(job.webhook_url)} returned status {status}",
        )
        return False
    except urllib.error.HTTPError as e:
        _emit(
            db, job, "error",
            f"webhook to {_redact_url(job.webhook_url)} HTTP {e.code}: {e.reason}",
        )
    except Exception as e:
        _emit(
            db, job, "error",
            f"webhook to {_redact_url(job.webhook_url)} failed: {type(e).__name__}: {e}",
        )
        log.warning("webhook delivery failed for job %s: %s", job.id, traceback.format_exc())
    return False


def _deliver_telegram(db: Session, job: Job, reason: str) -> bool:
    """Send the alert to the chat ID attached to this watch."""
    if not tg.is_configured():
        _emit(db, job, "error", "telegram channel selected but bot is not configured")
        return False

    text = (
        f"🔔 *DealTracker* — {job.platform}\n"
        f"{reason}\n"
        f"{job.url}"
    )
    try:
        tg.send_message(job.telegram_chat_id, text)
        _emit(db, job, "alert", f"TELEGRAM SENT to chat {job.telegram_chat_id} — {reason}")
        return True
    except Exception as e:
        _emit(db, job, "error", f"telegram delivery failed: {type(e).__name__}: {e}")
        log.warning("telegram failed for job %s: %s", job.id, traceback.format_exc())
        return False


def _redact_url(url: str | None) -> str:
    """Trim webhook URL for log lines — many bridge URLs include secrets in the path."""
    if not url:
        return "?"
    if len(url) > 60:
        return url[:40] + "…" + url[-12:]
    return url


# ---------- helpers ------------------------------------------------------------

def _emit(db: Session, job: Job, kind: str, message: str) -> None:
    e = Event(job_id=job.id, kind=kind, message=message, ts=_now())
    db.add(e)
    db.flush()  # populate e.id without committing yet
    bus.publish({
        "id": e.id,
        "ts": e.ts.isoformat(),
        "job_id": job.id,
        "job_kind": job.kind,
        "platform": job.platform,
        "kind": kind,
        "message": message,
    })


def _now() -> datetime:
    return datetime.now(timezone.utc)


_PRICE_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _parse_price(raw: object) -> float | None:
    """
    Pull a number out of a price string. Handles "₹156.00", "Rs. 1,299",
    "44,899", bare ints/floats, and refuses gracefully on garbage.
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        match = _PRICE_RE.search(raw)
        if not match:
            return None
        try:
            return float(match.group(0).replace(",", ""))
        except ValueError:
            return None
    return None


def _human_price(raw: str | None) -> str:
    if not raw:
        return "no price found"
    if any(sym in raw for sym in ("₹", "$", "€")):
        return raw
    n = _parse_price(raw)
    return f"₹{n:,.2f}" if n is not None else raw


def _summary_for(job: Job) -> str:
    if job.status == "alerted":
        return "tick done · job=ALERTED"
    if job.status == "error":
        return "tick done · job=ERROR (will retry)"
    return f"tick done · job={job.status}"
