import logging
import time
from bs4 import BeautifulSoup
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from ..config import PINCODE


log = logging.getLogger(__name__)


def enter_pincode(driver, pincode):
    try:
        log.debug("waiting for pincode overlay…")
        WebDriverWait(driver, 15).until(
            EC.visibility_of_element_located((By.ID, "search"))
        )

        inputs = driver.find_elements(By.ID, "search")
        pincode_input = None
        for inp in inputs:
            if inp.is_displayed() and inp.is_enabled():
                pincode_input = inp
                break

        if not pincode_input:
            log.warning("no interactable pincode input found")
            return False

        driver.execute_script("arguments[0].scrollIntoView(true);", pincode_input)
        time.sleep(0.5)

        pincode_input.clear()
        pincode_input.send_keys(pincode)
        log.debug("pincode '%s' entered", pincode)

        dropdown_item = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located(
                (By.XPATH, f"//p[@class='item-name text-dark mb-0 fw-semibold fs-6' and text()='{pincode}']")
            )
        )
        log.debug("pincode dropdown item: %s", dropdown_item.text)
        dropdown_item.click()
        time.sleep(1)
        return True

    except Exception as e:
        log.warning("could not automate pincode entry: %s", e)
        return False


def _extract_amul_price(soup):
    """Several strategies to read an Amul product price post-pincode."""
    import json
    import re

    # 1. JSON-LD Product schema.
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if isinstance(item, dict) and item.get("@type") == "Product":
                offers = item.get("offers")
                if isinstance(offers, list) and offers:
                    offers = offers[0]
                if isinstance(offers, dict):
                    p = offers.get("price") or offers.get("lowPrice")
                    if p:
                        return str(p)

    # 2. Legacy class.
    for tag in soup.find_all("span", class_=lambda x: x and "price-new" in x):
        txt = tag.get_text(strip=True)
        if "₹" in txt:
            return txt.replace('₹', '').replace(',', '').strip()

    # 3. Any class containing 'price' with a ₹ number.
    for el in soup.find_all(class_=re.compile(r'price', re.I)):
        m = re.search(r'₹\s*([\d,]+(?:\.\d+)?)', el.get_text(strip=True))
        if m:
            return m.group(1).replace(',', '')

    # 4. Smallest ₹X,XXX found in body.
    candidates = []
    for el in soup.find_all(['span', 'div', 'p']):
        m = re.fullmatch(r'₹\s*([\d,]+(?:\.\d+)?)', el.get_text(strip=True))
        if m:
            try:
                candidates.append(float(m.group(1).replace(',', '')))
            except ValueError:
                continue
    candidates = [c for c in candidates if c >= 1]
    if candidates:
        v = min(candidates)
        return f"{v:.2f}".rstrip('0').rstrip('.')
    return None


def scrape_amul(driver, url):
    driver.get(url)
    enter_pincode(driver, PINCODE)
    time.sleep(10)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    body_text = soup.get_text(' ', strip=True)
    body_lower = body_text.lower()

    # Stock status: explicit sold-out signal first, otherwise infer from page state.
    sold_out_div = soup.find('div', class_='alert alert-danger mt-3')
    if sold_out_div and "Sold Out" in sold_out_div.get_text(strip=True):
        stock_status = "out of stock"
    elif 'sold out' in body_lower:
        stock_status = "out of stock"
    else:
        stock_status = "in stock"

    price = _extract_amul_price(soup)

    # If the SPA never rendered product data (no price, no ₹ anywhere), don't
    # falsely claim "in stock" — surface "unknown" so callers can retry.
    if price is None and '₹' not in body_text:
        stock_status = "unknown"

    return {
        "stock_status": stock_status,
        "price": price,
    }
