"""One-shot scrape execution.

Called by APScheduler at each tick. Opens a fresh Selenium driver (per
tick — Selenium isn't safe to share across long-lived sessions), runs
the appropriate scraper, persists results, and emits Event rows that
the SSE bus (step 5) will fan out to the terminal pane.
"""

from __future__ import annotations

import logging
import os
import re
import traceback
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from .db import SessionLocal
from .events import bus
from .models import Event, Job

# Reuse existing scraper machinery.
from ..scrapers import (
    SCRAPERS,
    is_hotel_platform,
    route_scraper,
    scan_hotel_prices_monthly,
)
from ..utils.driver import create_driver
from ..utils.email import send_email


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
    driver = create_driver()
    try:
        if is_hotel_platform(job.url):
            scraper = SCRAPERS.get(job.platform)
            if scraper is None:
                raise RuntimeError(f"no scraper registered for hotel platform {job.platform}")
            results = scan_hotel_prices_monthly(driver, job.url, job.platform, scraper, days=30)
            return {"kind": "hotel", "results": results or []}

        product = route_scraper(driver, job.url)
        if product is None:
            raise RuntimeError("scraper returned no result")
        return {"kind": "product", **product}
    finally:
        try:
            driver.quit()
        except Exception:
            pass


# ---------- result handling ----------------------------------------------------

def _process_result(db: Session, job: Job, result: dict[str, Any]) -> None:
    if result["kind"] == "product":
        _process_product(db, job, result)
    elif result["kind"] == "hotel":
        _process_hotel(db, job, result)


def _process_product(db: Session, job: Job, result: dict[str, Any]) -> None:
    stock_status = (result.get("stock_status") or "unknown").lower()
    raw_price = result.get("price")
    job.last_status = stock_status
    job.last_price = str(raw_price) if raw_price is not None else None
    _emit(
        db, job, "tick_result",
        f"price={job.last_price or '—'} stock={stock_status}",
    )

    if job.alert_type == "stock":
        if stock_status == "in stock":
            _alert(db, job, f"in stock · {_human_price(job.last_price)}")
    elif job.alert_type == "price":
        price_num = _parse_price(raw_price)
        if price_num is None or job.threshold is None:
            return
        if price_num <= job.threshold:
            _alert(
                db, job,
                f"price ₹{price_num:,.2f} ≤ threshold ₹{job.threshold:,.2f}",
            )


def _process_hotel(db: Session, job: Job, result: dict[str, Any]) -> None:
    rows: list[dict[str, Any]] = result.get("results", [])
    priced = [r for r in rows if r.get("price") is not None]
    if not priced:
        job.last_status = "no rooms found"
        _emit(db, job, "tick_result", f"scanned {len(rows)} dates · no rooms")
        return

    best = min(priced, key=lambda r: r["price"])
    best_price = float(best["price"])
    best_date = best.get("date", "?")

    job.last_price = f"{best_price:.0f}"
    job.last_status = f"best ₹{best_price:,.0f} on {best_date}"

    _emit(
        db, job, "tick_result",
        f"scanned {len(rows)} dates · best=₹{best_price:,.0f} on {best_date}",
    )

    if job.threshold is None:
        return

    matches = [r for r in priced if float(r["price"]) <= job.threshold]
    if matches:
        msg = (
            f"{len(matches)} dates ≤ ₹{job.threshold:,.0f}, "
            f"lowest ₹{best_price:,.0f} on {best_date}"
        )
        _alert(db, job, msg)


def _alert(db: Session, job: Job, reason: str) -> None:
    job.status = "alerted"
    job.alerted_at = _now()
    job.active = False

    body = (
        f"DealTracker alert\n\n"
        f"Reason: {reason}\n"
        f"Platform: {job.platform}\n"
        f"URL: {job.url}\n"
    )
    subject = f"DealTracker · {job.platform} alert"

    # Primary delivery: address entered on the watch.
    try:
        send_email(subject=subject, body=body, recipient_email=job.email)
        _emit(db, job, "alert", f"ALERT EMAIL SENT to {job.email} — {reason}")
        return
    except Exception as primary_err:
        _emit(
            db, job, "error",
            f"primary delivery to {job.email} failed: {type(primary_err).__name__}: {primary_err}",
        )
        log.warning(
            "primary email failed for job %s: %s",
            job.id, traceback.format_exc(),
        )

    # Fallback delivery: if configured and different from primary.
    if FALLBACK_EMAIL and FALLBACK_EMAIL.lower() != (job.email or "").lower():
        fallback_body = (
            body
            + f"\n[fallback delivery — primary recipient {job.email} did not accept the message]\n"
        )
        try:
            send_email(subject=subject, body=fallback_body, recipient_email=FALLBACK_EMAIL)
            _emit(
                db, job, "alert",
                f"ALERT EMAIL SENT to fallback {FALLBACK_EMAIL} — {reason}",
            )
            return
        except Exception as fb_err:
            _emit(
                db, job, "error",
                f"fallback delivery to {FALLBACK_EMAIL} failed: {type(fb_err).__name__}: {fb_err}",
            )
            log.warning(
                "fallback email failed for job %s: %s",
                job.id, traceback.format_exc(),
            )

    # Alert state is correct (condition was met) even if no email got through.
    _emit(db, job, "alert", f"ALERT (all email delivery failed) — {reason}")


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


_PRICE_RE = re.compile(r"[^\d.]")


def _parse_price(raw: object) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        cleaned = _PRICE_RE.sub("", raw.replace(",", ""))
        if not cleaned:
            return None
        try:
            return float(cleaned)
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
