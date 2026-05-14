"""One-shot scrape execution.

Called by APScheduler at each tick. Opens a fresh Selenium driver (per
tick — Selenium isn't safe to share across long-lived sessions), runs
the appropriate scraper, persists results, and emits Event rows that
the SSE bus (step 5) will fan out to the terminal pane.
"""

from __future__ import annotations

import html
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
from ..scrapers.booking import scrape_booking
from ..utils.booking_url import expand_nights, with_dates
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
            if _is_range_job(job):
                result = _do_range_scrape(db, job)
            else:
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
    """Single scrape pass for product and single-date hotel watches."""
    # Booking.com and Agoda require dates in the URL to show room prices.
    # Without them the page shows no rates; the scraper always returns price=None.
    _DATE_PARAMS = {"checkin=", "checkIn=", "check_in="}
    if job.platform in ("booking", "agoda") and not any(p in job.url for p in _DATE_PARAMS):
        raise RuntimeError(
            f"{job.platform} watch has no dates — stop this watch and re-submit "
            "with a check-in / check-out date range"
        )
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


def _is_range_job(job: Job) -> bool:
    return bool(job.date_start and job.date_end and job.platform == "booking")


def _do_range_scrape(db: Session, job: Job) -> dict[str, Any]:
    """Scrape every night in [date_start, date_end), pick the cheapest.

    Shares one Chromium across all nights — opening a fresh driver per
    night would blow up the per-tick budget. Emits a `tick_result` event
    per night so the live terminal pane shows incremental progress
    during the (potentially long) tick.
    """
    nights = expand_nights(job.date_start, job.date_end)
    if not nights:
        raise RuntimeError("date range produced zero nights")

    per_night: list[dict[str, Any]] = []
    title: str | None = None

    driver = create_driver()
    try:
        for checkin, checkout in nights:
            night_url = with_dates(job.url, checkin, checkout)
            try:
                result = scrape_booking(driver, night_url) or {}
            except Exception as e:
                _emit(
                    db, job, "error",
                    f"night {checkin.isoformat()} scrape failed: {type(e).__name__}: {e}",
                )
                per_night.append({"checkin": checkin, "price": None, "status": "error"})
                continue

            if not title and result.get("title"):
                title = result["title"]

            price_num = _parse_price(result.get("price"))
            status = (result.get("stock_status") or "unknown").lower()
            per_night.append({"checkin": checkin, "price": price_num, "status": status})

            _emit(
                db, job, "tick_result",
                f"night {checkin.isoformat()}: "
                f"price={_human_price(str(price_num)) if price_num is not None else '—'} "
                f"stock={status}",
            )
            db.commit()
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    priced = [n for n in per_night if n["price"] is not None]
    cheapest = min(priced, key=lambda n: n["price"]) if priced else None

    return {
        "is_range": True,
        "title": title,
        "nights": per_night,
        "cheapest_date": cheapest["checkin"] if cheapest else None,
        "cheapest_price": cheapest["price"] if cheapest else None,
        "type": "hotel",
    }


# ---------- result handling ----------------------------------------------------

def _process_result(db: Session, job: Job, result: dict[str, Any]) -> None:
    """Single-shot result handler. Works for both products and hotels —
    they share the same {price, stock_status, title?} contract."""
    # Range scrapes have their own shape; aggregated cheapest-night logic.
    if result.get("is_range"):
        _process_range_result(db, job, result)
        return

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


def _process_range_result(db: Session, job: Job, result: dict[str, Any]) -> None:
    """Handle the aggregated output of a night-range scrape.

    Persists the cheapest night onto the Job. If the cheapest beats the
    threshold, fires a single consolidated alert (format A) naming the
    cheapest night and listing any other below-threshold nights.
    """
    cheapest_date = result.get("cheapest_date")
    cheapest_price: float | None = result.get("cheapest_price")
    nights = result.get("nights") or []

    # Persist summary on the job for the watch list.
    if cheapest_date is not None and cheapest_price is not None:
        job.cheapest_night_date = cheapest_date
        job.cheapest_night_price = float(cheapest_price)
        job.last_status = "available"
        job.last_price = f"{cheapest_price:.0f}"
    else:
        job.last_status = "no-prices"
        job.last_price = None

    priced_count = sum(1 for n in nights if n.get("price") is not None)
    _emit(
        db, job, "tick_result",
        f"range {job.date_start.isoformat()}→{job.date_end.isoformat()} · "
        f"priced {priced_count}/{len(nights)} · "
        f"cheapest={'₹{:,.0f} on {}'.format(cheapest_price, cheapest_date.isoformat()) if cheapest_price else '—'}",
    )

    # No alert if nothing priced or no threshold.
    if cheapest_price is None or job.threshold is None:
        return
    if cheapest_price > job.threshold:
        return

    _alert(db, job, _format_range_alert(job, result))


def _format_range_alert(job: Job, result: dict[str, Any]) -> str:
    """Build the multi-line reason string for a night-range alert.

    Format A: name the cheapest night, mention any other nights that
    also beat the threshold. Plain text — the channel-specific helpers
    (_deliver_telegram, _deliver_email) escape/wrap as needed.
    """
    title = result.get("title") or "Hotel"
    cheapest_date = result.get("cheapest_date")
    cheapest_price: float = result["cheapest_price"]
    threshold = job.threshold or 0.0

    other_below: list[str] = []
    for n in result.get("nights") or []:
        p = n.get("price")
        d = n.get("checkin")
        if p is None or d is None or d == cheapest_date:
            continue
        if p <= threshold:
            other_below.append(d.strftime("%a %d %b"))

    lines = [
        f"{title}",
        f"Best night: {cheapest_date.strftime('%a %d %b')} — ₹{cheapest_price:,.0f}",
        f"(your threshold ₹{threshold:,.0f})",
    ]
    if other_below:
        lines.append("")
        lines.append(
            f"{len(other_below)} other night{'s' if len(other_below) != 1 else ''} "
            f"also below threshold: {', '.join(other_below)}"
        )
    return "\n".join(lines)


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

    # HTML parse_mode handles URLs cleanly — legacy Markdown choked on the
    # underscores Flipkart loves to put in product slugs.
    text = (
        f"🔔 <b>DealTracker</b> — {html.escape(job.platform)}\n"
        f"{html.escape(reason)}\n"
        f"{html.escape(job.url)}"
    )
    try:
        tg.send_message(job.telegram_chat_id, text, parse_mode="HTML")
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
        # user_id rides with every event so the SSE route can filter by
        # session identity. Null on legacy jobs that haven't been claimed.
        "user_id": job.user_id,
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
