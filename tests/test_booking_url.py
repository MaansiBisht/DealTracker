"""Booking URL helpers — strip / inject dates, expand night ranges."""

from __future__ import annotations

from datetime import date

import pytest

from src.utils.booking_url import MAX_NIGHTS, expand_nights, strip_dates, with_dates


# ---------- strip_dates --------------------------------------------------------

@pytest.mark.parametrize(
    "url, expected",
    [
        # No query string — pass-through
        (
            "https://www.booking.com/hotel/in/foo.html",
            "https://www.booking.com/hotel/in/foo.html",
        ),
        # Only checkin/checkout — strips to empty query
        (
            "https://www.booking.com/hotel/in/foo.html?checkin=2026-06-11&checkout=2026-06-12",
            "https://www.booking.com/hotel/in/foo.html",
        ),
        # Mixed params — keep label, group_adults; drop dates
        (
            "https://www.booking.com/hotel/in/foo.html?checkin=2026-06-11&label=ABC&checkout=2026-06-12&group_adults=2",
            "https://www.booking.com/hotel/in/foo.html?label=ABC&group_adults=2",
        ),
        # Capitalised — Booking treats them as the same key; we should too
        (
            "https://www.booking.com/hotel/in/foo.html?Checkin=2026-06-11&CHECKOUT=2026-06-12&keep=1",
            "https://www.booking.com/hotel/in/foo.html?keep=1",
        ),
    ],
)
def test_strip_dates(url, expected):
    assert strip_dates(url) == expected


def test_strip_dates_is_idempotent():
    once = strip_dates("https://www.booking.com/x?checkin=2026-06-11&checkout=2026-06-12&kept=y")
    twice = strip_dates(once)
    assert once == twice


# ---------- with_dates --------------------------------------------------------

def test_with_dates_appends_to_clean_url():
    out = with_dates("https://www.booking.com/hotel/in/foo.html", date(2026, 6, 11), date(2026, 6, 12))
    assert out == "https://www.booking.com/hotel/in/foo.html?checkin=2026-06-11&checkout=2026-06-12"


def test_with_dates_preserves_other_query_params():
    out = with_dates(
        "https://www.booking.com/hotel/in/foo.html?label=ABC&group_adults=2",
        date(2026, 6, 11),
        date(2026, 6, 12),
    )
    assert "label=ABC" in out
    assert "group_adults=2" in out
    assert "checkin=2026-06-11" in out
    assert "checkout=2026-06-12" in out


def test_with_dates_overwrites_existing_dates():
    """If the URL already has dates, they're replaced not duplicated."""
    out = with_dates(
        "https://www.booking.com/hotel/in/foo.html?checkin=2024-01-01&checkout=2024-01-02",
        date(2026, 6, 11),
        date(2026, 6, 12),
    )
    assert "2024-01-01" not in out
    assert "2024-01-02" not in out
    assert "checkin=2026-06-11" in out
    assert "checkout=2026-06-12" in out
    assert out.count("checkin=") == 1
    assert out.count("checkout=") == 1


# ---------- expand_nights -----------------------------------------------------

def test_expand_nights_three_day_range():
    nights = expand_nights(date(2026, 6, 11), date(2026, 6, 14))
    assert nights == [
        (date(2026, 6, 11), date(2026, 6, 12)),
        (date(2026, 6, 12), date(2026, 6, 13)),
        (date(2026, 6, 13), date(2026, 6, 14)),
    ]


def test_expand_nights_single_night():
    nights = expand_nights(date(2026, 6, 11), date(2026, 6, 12))
    assert nights == [(date(2026, 6, 11), date(2026, 6, 12))]


def test_expand_nights_empty_when_end_not_after_start():
    assert expand_nights(date(2026, 6, 11), date(2026, 6, 11)) == []
    assert expand_nights(date(2026, 6, 12), date(2026, 6, 11)) == []


def test_expand_nights_respects_cap():
    """A 30-day range with cap=14 must return exactly 14 pairs."""
    nights = expand_nights(date(2026, 6, 1), date(2026, 7, 1), cap=14)
    assert len(nights) == 14
    assert nights[0] == (date(2026, 6, 1), date(2026, 6, 2))
    assert nights[-1] == (date(2026, 6, 14), date(2026, 6, 15))


def test_expand_nights_default_cap_matches_constant():
    """Default cap pulled from MAX_NIGHTS so product change = one place."""
    nights = expand_nights(date(2026, 6, 1), date(2026, 7, 1))
    assert len(nights) == MAX_NIGHTS
