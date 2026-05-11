"""Cross-platform audit of the Telegram alert delivery path.

The HTML-mode fix lives in `_deliver_telegram` (src/server/runner.py).
This file asserts that every supported platform's URL flows through
the alert renderer without producing payloads Telegram would reject —
no stray Markdown specials in user-controlled fields, balanced HTML
tags, and the right parse_mode on the wire.

No SMTP / Selenium / Telegram API is touched: `tg.send_message` is
monkeypatched to capture the dict that would have been sent.
"""

from __future__ import annotations

import re

import pytest

from src.scrapers import HOTEL_PLATFORMS, SCRAPERS
from src.server import runner
from src.server.db import SessionLocal
from src.server.models import Job


# A realistic-shape URL per platform — these are the patterns we've seen
# in the wild that historically tripped Telegram's Markdown parser
# (underscores in slugs, & in query strings, %-encoded checkin dates,
# parens in hotel names, etc.). The exact URL doesn't need to resolve.
PLATFORM_URLS: dict[str, str] = {
    "amazon":     "https://www.amazon.in/Apple-iPhone-17-Pro-Silver/dp/B0CXXX_TEST/ref=sr_1_1?keywords=iphone&qid=1",
    "flipkart":   "https://www.flipkart.com/apple-iphone-17-pro-silver_256-gb/p/itm106f475c264c7?pid=MOBHFN6YPFSDYRTY&marketplace=FLIPKART&lid=LSTMOB",
    "myntra":     "https://www.myntra.com/dresses/h_m/h-and-m-women-floral_dress/12345/buy?p=1&rf=Color%3ARed",
    "amul":       "https://shop.amul.com/en/product/amul_taaza_milk-cookies_(small_pack)",
    "amazfit":    "https://www.amazfit.com/products/amazfit_balance-2-gps?variant=Active_Black",
    "booking":    "https://www.booking.com/hotel/in/the_grand-hotel.html?checkin=2026-06-01&checkout=2026-06-02&group_adults=2&no_rooms=1",
    "makemytrip": "https://www.makemytrip.com/hotels/foo_hotel-details-mumbai.html?ci=06%2F01%2F2026&co=06%2F02%2F2026&r=1e2a",
    "goibibo":    "https://www.goibibo.com/hotels/foo_hotel-mumbai?vcid=200012&locusId=CTMUM&checkin=20260601&checkout=20260602",
    "agoda":      "https://www.agoda.com/the_grand-hotel/hotel/mumbai-in.html?los=1&checkIn=2026-06-01&adults=2",
}


@pytest.fixture()
def captured_telegram(monkeypatch):
    """Replace tg.send_message with a collector — captures payload + parse_mode."""
    calls: list[dict] = []

    def _fake_send(chat_id: str, text: str, parse_mode=None) -> None:
        calls.append({"chat_id": chat_id, "text": text, "parse_mode": parse_mode})

    monkeypatch.setattr("src.server.runner.tg.send_message", _fake_send)
    monkeypatch.setattr("src.server.runner.tg.is_configured", lambda: True)
    return calls


def _make_job(platform: str, url: str) -> Job:
    """Persist a minimal Job for the platform under test."""
    kind = "hotel" if platform in HOTEL_PLATFORMS else "product"
    with SessionLocal() as db:
        job = Job(
            kind=kind,
            url=url,
            email="audit@example.com",
            telegram_chat_id="123456789",
            alert_type="price_drop" if kind == "hotel" else "stock",
            threshold=1000.0 if kind == "hotel" else None,
            platform=platform,
            status="pending",
            active=True,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job


# ---------------------------------------------------------------------------
# Per-platform audit — parametrized over every registered scraper
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("platform", sorted(SCRAPERS.keys()))
def test_alert_renders_cleanly_for_platform(platform, captured_telegram):
    """Every platform's URL must produce a valid HTML-mode payload."""
    url = PLATFORM_URLS[platform]
    job = _make_job(platform, url)
    reason = "in stock · ₹1,19,900.00"

    with SessionLocal() as db:
        live_job = db.get(Job, job.id)
        ok = runner._deliver_telegram(db, live_job, reason)
        db.commit()

    assert ok is True, f"telegram delivery returned False for {platform}"
    assert len(captured_telegram) == 1, f"expected exactly one send for {platform}"
    payload = captured_telegram[0]

    # The wire-format contract Telegram will accept reliably.
    assert payload["parse_mode"] == "HTML", f"{platform}: wrong parse_mode"
    assert payload["chat_id"] == "123456789"

    text = payload["text"]
    assert "<b>DealTracker</b>" in text, f"{platform}: lost the bold header"
    assert "in stock" in text, f"{platform}: reason missing from body"

    # No bare ampersands — they MUST be html-escaped to &amp; (Telegram
    # rejects raw & in HTML mode). Same for any tags that aren't <b>.
    _assert_html_safe(text, platform)

    # The URL must appear, escape-canonicalised. Reverse html.escape and
    # check it equals the original.
    import html as _html
    decoded = _html.unescape(text)
    assert url in decoded, f"{platform}: URL not present in payload"


def _assert_html_safe(text: str, platform: str) -> None:
    """Reject any HTML control char that isn't part of a balanced <b> tag."""
    stripped = re.sub(r"<b>|</b>", "", text)
    assert "<" not in stripped, f"{platform}: stray '<' in body"
    assert ">" not in stripped, f"{platform}: stray '>' in body"
    # An unescaped '&' is anything not followed by an entity name + ';'.
    bare_amp = re.findall(r"&(?!(?:amp|lt|gt|quot|#\d+);)", stripped)
    assert not bare_amp, f"{platform}: unescaped '&' in body — Telegram will reject"


# ---------------------------------------------------------------------------
# Non-Telegram channels: smoke-check the alert dispatcher routes correctly
# when a job has no Telegram configured (no chat_id).
# ---------------------------------------------------------------------------


def test_alert_skips_telegram_when_chat_id_missing(captured_telegram):
    """Job without telegram_chat_id must not touch tg.send_message at all."""
    with SessionLocal() as db:
        job = Job(
            kind="product",
            url="https://www.amazon.in/dp/B0test",
            email="audit@example.com",
            telegram_chat_id=None,
            alert_type="stock",
            platform="amazon",
            status="pending",
            active=True,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        runner._alert(db, job, "in stock · ₹999.00")
        db.commit()

    assert captured_telegram == [], "telegram should not be called when chat_id is None"
