"""Normalise share/short URLs to their canonical product form.

Retailer apps' "Share" buttons typically produce short links like
`https://amzn.in/d/abc123` or `https://fkrt.it/xyz`. The substring host
matcher in `src/scrapers/__init__.py` doesn't recognise these, so the
API would reject them with "unsupported platform".

This module exposes one function — `normalize_url(url)` — that follows
HTTP redirects on a small allow-list of known short hostnames and
returns the canonical URL. Anything not on the short-host list is
returned unchanged. Network errors are swallowed and the original URL
is returned (Selenium will follow the redirect at scrape time anyway —
this is only about getting the URL past the platform-detection gate
and storing something the user can recognise in the watch list).

Stdlib only (urllib) — no new runtime deps.
"""

from __future__ import annotations

import logging
import urllib.error
import urllib.request
from urllib.parse import urlparse


log = logging.getLogger("dealtracker.url_normalizer")


# Hostnames whose links are short/share redirects to canonical product pages.
# Keep this list narrow — anything on it gets a real network call.
SHORT_HOSTS: frozenset[str] = frozenset({
    "amzn.in",
    "amzn.eu",
    "amzn.to",
    "a.co",
    "fkrt.it",
    "dl.flipkart.com",
})

# Mimic a real browser; some shorteners return a 4xx to bare urllib UA.
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def _hostname(url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return ""
    return host[4:] if host.startswith("www.") else host


def _is_short(url: str) -> bool:
    return _hostname(url) in SHORT_HOSTS


def resolve_short_url(url: str, *, timeout: float = 5.0) -> str:
    """Follow redirects from a known short URL to its canonical form.

    Returns the final URL when the redirect chain resolves cleanly.
    On any failure (network error, non-2xx, blocked by anti-bot)
    returns the original URL — callers fall back to handing it to
    Selenium, which does its own redirect handling.
    """
    if not _is_short(url):
        return url

    req = urllib.request.Request(
        url,
        method="GET",
        headers={"User-Agent": _UA, "Accept": "*/*"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            final = resp.geturl()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        log.info("resolve_short_url failed for %s: %s", url, e)
        return url
    except Exception as e:
        # Defensive: never let resolution crash a create-job call.
        log.warning("resolve_short_url unexpected error for %s: %s", url, e)
        return url

    if not final or final == url:
        return url
    return final


def normalize_url(url: str) -> str:
    """Public entry point. Strips whitespace, resolves known short links.

    Idempotent: calling it twice produces the same result.
    """
    url = url.strip()
    return resolve_short_url(url)
