"""URL normalizer: short-link resolution + pass-through for canonical URLs."""

from __future__ import annotations

import urllib.error
from unittest.mock import patch

import pytest

from src.utils.url_normalizer import normalize_url, resolve_short_url


class _FakeResponse:
    """Minimal stand-in for urllib's response context manager — just .geturl()."""

    def __init__(self, final_url: str) -> None:
        self._final_url = final_url

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def geturl(self) -> str:
        return self._final_url


@pytest.mark.parametrize(
    "url",
    [
        "https://www.amazon.in/dp/B08BPQ9CZ1",
        "https://www.flipkart.com/foo/p/itm123",
        "https://www.booking.com/hotel/x.html",
        "https://example.com/whatever",
        "not a url",
        "",
    ],
)
def test_normalize_passes_through_non_short_urls(url):
    """Canonical and unknown URLs are returned unchanged with no network call."""
    with patch("src.utils.url_normalizer.urllib.request.urlopen") as mock_open:
        out = normalize_url(url)
    assert out == url.strip()
    mock_open.assert_not_called()


@pytest.mark.parametrize(
    "short, canonical",
    [
        ("https://amzn.in/d/abc123", "https://www.amazon.in/dp/B08BPQ9CZ1?tag=foo"),
        ("https://amzn.to/3xYzAbc", "https://www.amazon.com/dp/B0XYZ"),
        ("https://a.co/d/abcXYZ", "https://www.amazon.com/dp/B0ABC"),
        ("https://fkrt.it/abc-xyz", "https://www.flipkart.com/foo/p/itm123"),
    ],
)
def test_resolves_known_short_hosts_to_final_url(short, canonical):
    with patch("src.utils.url_normalizer.urllib.request.urlopen") as mock_open:
        mock_open.return_value = _FakeResponse(canonical)
        out = normalize_url(short)
    assert out == canonical
    mock_open.assert_called_once()


def test_returns_original_when_redirect_resolves_to_same_url():
    """If the upstream returns the same URL we sent (no redirect), pass it through."""
    short = "https://amzn.in/d/abc123"
    with patch("src.utils.url_normalizer.urllib.request.urlopen") as mock_open:
        mock_open.return_value = _FakeResponse(short)
        out = resolve_short_url(short)
    assert out == short


def test_falls_back_to_original_on_network_error():
    """A blocked / timed-out resolution must not crash — return the original URL."""
    short = "https://amzn.in/d/abc123"
    with patch("src.utils.url_normalizer.urllib.request.urlopen") as mock_open:
        mock_open.side_effect = urllib.error.URLError("connection refused")
        out = resolve_short_url(short)
    assert out == short


def test_falls_back_to_original_on_unexpected_exception():
    """Defensive: a non-urllib error inside urlopen also returns the original."""
    short = "https://fkrt.it/abc-xyz"
    with patch("src.utils.url_normalizer.urllib.request.urlopen") as mock_open:
        mock_open.side_effect = RuntimeError("unexpected")
        out = resolve_short_url(short)
    assert out == short


def test_strips_whitespace_in_normalize():
    assert normalize_url("  https://example.com/x  ") == "https://example.com/x"


def test_idempotent():
    """Calling normalize_url twice produces the same result (no double-resolution)."""
    canonical = "https://www.amazon.in/dp/B08BPQ9CZ1"
    once = normalize_url(canonical)
    twice = normalize_url(once)
    assert once == twice == canonical
