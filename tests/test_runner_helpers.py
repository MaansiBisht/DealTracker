"""Pure-function helpers in the runner — no I/O, no Selenium."""

import pytest

from src.scrapers.amazon import _classify_amazon_stock
from src.server.runner import _human_price, _parse_price, _summary_for


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("₹156.00", 156.0),
        ("₹44,899.00", 44899.0),
        ("Rs. 1,299", 1299.0),
        (699, 699.0),
        (7499.0, 7499.0),
        ("", None),
        (None, None),
        ("just text", None),
    ],
)
def test_parse_price(raw, expected):
    assert _parse_price(raw) == expected


def test_human_price_passthrough_for_currency_string():
    assert _human_price("₹156.00") == "₹156.00"


def test_human_price_formats_bare_number():
    assert _human_price("699") == "₹699.00"


def test_human_price_handles_missing():
    assert _human_price(None) == "no price found"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("In stock.", "in stock"),
        ("In Stock", "in stock"),
        ("Currently unavailable.", "out of stock"),
        ("We don't know when or if this item will be back in stock.", "out of stock"),
        ("Only 3 left in stock.", "in stock"),
        ("Usually dispatches within 5 days", "in stock"),
        ("", "unknown"),
        ("Mystery copy", "unknown"),
    ],
)
def test_classify_amazon_stock(text, expected):
    assert _classify_amazon_stock(text) == expected


class _FakeJob:
    def __init__(self, status: str):
        self.status = status


def test_summary_for_alerted_job():
    assert _summary_for(_FakeJob("alerted")) == "tick done · job=ALERTED"


def test_summary_for_idle_job():
    assert _summary_for(_FakeJob("idle")) == "tick done · job=idle"


def test_summary_for_error_job():
    assert _summary_for(_FakeJob("error")) == "tick done · job=ERROR (will retry)"
