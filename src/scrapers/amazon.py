import time
from bs4 import BeautifulSoup


def _classify_amazon_stock(text: str) -> str:
    """Map Amazon's free-form availability text to our canonical states."""
    t = (text or "").lower()
    if not t:
        return "unknown"
    if "unavailable" in t or "out of stock" in t or "we don't know when" in t:
        return "out of stock"
    if "in stock" in t or ("only" in t and "left" in t) or "usually dispatches" in t:
        return "in stock"
    return "unknown"


def scrape_amazon(driver, url):
    driver.get(url)
    time.sleep(10)
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    # ---- Stock ----
    stock_status = "unknown"
    stock_div = soup.find('div', id='availability')
    if stock_div:
        msg_span = (
            stock_div.find('span', class_='a-color-success')
            or stock_div.find('span', class_='a-color-state')
            or stock_div.find('span', class_='a-color-attainable')
            or stock_div.find('span', class_='a-color-price')
        )
        text = msg_span.get_text(strip=True) if msg_span else stock_div.get_text(' ', strip=True)
        stock_status = _classify_amazon_stock(text)

    # ---- Price ----
    # Amazon renders many a-price blocks (sale, MRP, per-unit, deals, EMI). Walk
    # them in order and return the first non-empty offscreen value, preferring
    # the apex-pricetopay container when available.
    price_text = None
    price_candidates = soup.select(
        'span.apex-pricetopay-value, span.priceToPay, span.a-price'
    )
    for span in price_candidates:
        offscreen = span.find('span', class_='a-offscreen')
        text = offscreen.get_text(strip=True) if offscreen else ''
        if text and '₹' in text:
            price_text = text
            break

    return {'stock_status': stock_status, 'price': price_text}
