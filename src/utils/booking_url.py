"""Booking.com URL helpers — strip dates, inject dates, expand a range.

Night-range hotel watches store a *date-less* hotel URL in the DB. On
every tick the runner injects checkin/checkout for each night in the
configured range and scrapes them one at a time.

Pure functions, no network, no DB. Booking-specific for now — Phase 3
will add per-platform variants for MMT / Agoda / Goibibo when their
URL formats are needed.
"""

from __future__ import annotations

from datetime import date, timedelta
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl


# Query-param names Booking uses for the stay window. We strip these on
# save and re-inject them per night. Capitalised variants are folded.
_DATE_PARAMS: frozenset[str] = frozenset({"checkin", "checkout"})

# Hard cap on nights per watch. Matches the product decision: keep the
# per-tick scrape budget bounded so a single watch can't starve others.
MAX_NIGHTS: int = 14


def strip_dates(url: str) -> str:
    """Remove checkin / checkout query params from a Booking URL.

    Everything else (scheme, host, path, other query params, fragment)
    is preserved verbatim. Returns the URL unchanged if it doesn't
    parse — caller decides what to do with that.
    """
    try:
        parts = urlparse(url)
    except Exception:
        return url
    if not parts.query:
        return url

    kept = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if k.lower() not in _DATE_PARAMS]
    new_query = urlencode(kept)
    return urlunparse(parts._replace(query=new_query))


def with_dates(url: str, checkin: date, checkout: date) -> str:
    """Return a copy of `url` with checkin/checkout injected as query params.

    Any pre-existing checkin/checkout are dropped first so we never end
    up with two values for the same key. Date format is ISO `YYYY-MM-DD`
    which Booking accepts directly.
    """
    base = strip_dates(url)
    parts = urlparse(base)
    existing = parse_qsl(parts.query, keep_blank_values=True)
    existing.append(("checkin", checkin.isoformat()))
    existing.append(("checkout", checkout.isoformat()))
    return urlunparse(parts._replace(query=urlencode(existing)))


def expand_nights(start: date, end: date, *, cap: int = MAX_NIGHTS) -> list[tuple[date, date]]:
    """Yield consecutive (checkin, checkout) pairs covering [start, end).

    A "night" is a single-day stay: (day, day + 1). Returns pairs for
    every checkin from `start` up to but not including `end`. Capped at
    `cap` nights to keep per-tick scrape work bounded.

    Returns an empty list when `end <= start`.
    """
    if end <= start:
        return []
    nights: list[tuple[date, date]] = []
    cursor = start
    while cursor < end and len(nights) < cap:
        nights.append((cursor, cursor + timedelta(days=1)))
        cursor += timedelta(days=1)
    return nights
