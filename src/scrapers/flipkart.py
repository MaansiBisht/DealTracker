import json
import logging
import re
import time
from bs4 import BeautifulSoup

log = logging.getLogger("dealtracker.scrapers.flipkart")

_OOS_SCHEMA_TOKENS = {"outofstock", "soldout", "discontinued"}
_IN_STOCK_SCHEMA_TOKENS = {"instock", "limitedavailability", "onlineonly", "preorder", "presale"}

# Flipkart's buy-box swaps the primary action button when the URL-pinned
# variant is unavailable. These cues only appear in the action area —
# cross-sell carousels render their own 'Add to cart' buttons, so an OOS
# cue anywhere on the page is a reliable signal.
_BUYBOX_OUT_OF_STOCK_CUES = ("sold out", "out of stock", "notify me", "coming soon")
_BUYBOX_IN_STOCK_CUES = ("add to cart", "buy now", "go to cart")


def _classify_availability(value):
    """Map a schema.org availability URL/string to a canonical state.

    Accepts both bare tokens ('OutOfStock') and full URLs
    ('https://schema.org/OutOfStock'). Returns None on unknown input
    so the caller can fall back to the next signal.
    """
    if not value:
        return None
    token = re.sub(r"[^a-z]", "", str(value).rsplit("/", 1)[-1].lower())
    if token in _OOS_SCHEMA_TOKENS:
        return "out of stock"
    if token in _IN_STOCK_SCHEMA_TOKENS:
        return "in stock"
    return None


def _walk_jsonld(soup):
    """Return (price, raw_availability) from the first Product JSON-LD block."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict) or item.get("@type") != "Product":
                continue
            offers = item.get("offers")
            if isinstance(offers, list) and offers:
                offers = offers[0]
            if not isinstance(offers, dict):
                continue
            price = offers.get("price") or offers.get("lowPrice")
            availability = offers.get("availability")
            return (str(price) if price else None, availability)
    return (None, None)


def _classify_buybox_cta(soup):
    """Inspect primary action buttons; return canonical state or None.

    Rule: if any button copy contains an OOS cue ('sold out', 'notify me',
    etc.), trust it — cross-sell cards never carry those phrases. If only
    in-stock cues are present, the variant is buyable.
    """
    button_texts = []
    for btn in soup.find_all("button"):
        text = btn.get_text(" ", strip=True).lower()
        if text:
            button_texts.append(text)
    for anchor in soup.select('a[role="button"]'):
        text = anchor.get_text(" ", strip=True).lower()
        if text:
            button_texts.append(text)

    if not button_texts:
        return None

    joined = " | ".join(button_texts)
    has_oos = any(cue in joined for cue in _BUYBOX_OUT_OF_STOCK_CUES)
    has_buy = any(cue in joined for cue in _BUYBOX_IN_STOCK_CUES)

    if has_oos:
        return "out of stock"
    if has_buy:
        return "in stock"
    return None


def _extract_price_from_dom(soup):
    """Smallest plausible ₹X,XXX node — current Flipkart lists selling price first."""
    candidates = []
    for el in soup.find_all(['div', 'span']):
        txt = el.get_text(strip=True)
        m = re.fullmatch(r'₹\s*([\d,]+)', txt)
        if m:
            try:
                candidates.append(int(m.group(1).replace(',', '')))
            except ValueError:
                continue
        if len(candidates) >= 30:
            break
    candidates = [c for c in candidates if c >= 10]
    return str(min(candidates)) if candidates else None


def _extract_price_from_inline_script(soup):
    """Legacy fallback: regex on inline scripts for finalPrice.decimalValue."""
    for script in soup.find_all("script"):
        if not script.string:
            continue
        m = re.search(r'"finalPrice"\s*:\s*({[^}]{0,300}})', script.string)
        if not m:
            continue
        try:
            final_price = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if "decimalValue" in final_price:
            return str(final_price["decimalValue"])
    return None


def classify_stock(soup):
    """Decide stock for the URL-pinned variant using layered signals.

    1. JSON-LD offers.availability (authoritative when present).
    2. Buy-box CTA inspection (fallback for missing JSON-LD).
    3. Page-text scan (last resort).

    When none of the signals fire AND no JSON-LD Product block exists on
    the page at all, we return "unknown" rather than defaulting to
    "in stock". Flipkart occasionally serves a reCAPTCHA interstitial
    (or a partially-hydrated page) — neither is a product page, and
    silently labelling it "in stock" produced false re-alerts on
    out-of-stock variants.
    """
    _, raw_availability = _walk_jsonld(soup)
    status = _classify_availability(raw_availability)
    if status:
        return status

    status = _classify_buybox_cta(soup)
    if status:
        return status

    body_text_lower = soup.get_text(' ', strip=True).lower()
    if 'sold out' in body_text_lower or 'currently unavailable' in body_text_lower:
        return "out of stock"

    # Refuse to claim "in stock" if the page didn't render a Product
    # JSON-LD block. Every real Flipkart PDP carries one; an absence
    # almost always means recaptcha / partial render.
    if not soup.find("script", type="application/ld+json"):
        return "unknown"
    return "in stock"


def _looks_like_recaptcha(soup) -> bool:
    """Quick fingerprint check for Flipkart's anti-bot interstitial."""
    title = soup.find("title")
    if title and "recaptcha" in title.get_text(strip=True).lower():
        return True
    return False


def scrape_flipkart(driver, url):
    driver.get(url)
    # Give Flipkart's JS extra hydration time. Most renders settle in
    # well under this, but the iPhone-class hot-products page is slow
    # enough that a 10s wait left JSON-LD missing on ~20% of ticks.
    time.sleep(15)
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    if _looks_like_recaptcha(soup):
        log.warning("flipkart served a recaptcha interstitial for %s — returning unknown", url)
        return {"stock_status": "unknown", "price": None}

    price, _ = _walk_jsonld(soup)
    if not price:
        price = _extract_price_from_dom(soup)
    if not price:
        price = _extract_price_from_inline_script(soup)

    stock_status = classify_stock(soup)
    if not price:
        # Page likely didn't render — don't trust the stock signal either.
        stock_status = "unknown"

    return {
        "stock_status": stock_status,
        "price": price,
    }
