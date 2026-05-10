import json
import re
import time
from bs4 import BeautifulSoup


def _extract_price_from_jsonld(soup):
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("@type") == "Product":
                offers = item.get("offers")
                if isinstance(offers, list) and offers:
                    offers = offers[0]
                if isinstance(offers, dict):
                    p = offers.get("price") or offers.get("lowPrice")
                    if p:
                        return str(p)
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


def scrape_flipkart(driver, url):
    driver.get(url)
    time.sleep(10)
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    body_text_lower = soup.get_text(' ', strip=True).lower()
    stock_status = "out of stock" if (
        'sold out' in body_text_lower or 'currently unavailable' in body_text_lower
    ) else "in stock"

    price = _extract_price_from_jsonld(soup) or _extract_price_from_dom(soup)

    if not price:
        # Legacy fallback: regex on inline scripts.
        for script in soup.find_all("script"):
            if not script.string:
                continue
            m = re.search(r'"finalPrice"\s*:\s*({[^}]{0,300}})', script.string)
            if m:
                try:
                    final_price = json.loads(m.group(1))
                    if "decimalValue" in final_price:
                        price = str(final_price["decimalValue"])
                        break
                except json.JSONDecodeError:
                    continue

    if not price:
        # No price extracted -> page likely didn't render; don't claim stock.
        stock_status = "unknown"

    return {
        "stock_status": stock_status,
        "price": price,
    }
