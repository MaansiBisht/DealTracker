import json
import logging
import time
from bs4 import BeautifulSoup


log = logging.getLogger(__name__)


def scrape_myntra(driver, url):
    driver.get(url)
    time.sleep(10)
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    # Find all JSON-LD scripts
    scripts = soup.find_all("script", type="application/ld+json")
    product_data = None

    # Find the "Product" schema
    for script in scripts:
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                for item in data:
                    if item.get("@type") == "Product":
                        product_data = item
                        break
            elif data.get("@type") == "Product":
                product_data = data
                break
        except Exception:
            continue

    if not product_data:
        log.warning("no Product JSON-LD schema found at %s", url)
        return None

    # Extract details
    name = product_data.get("name")
    price = None
    stock_status = None

    offers = product_data.get("offers", {})
    if isinstance(offers, list):
        offer = offers[0]
    else:
        offer = offers

    price = offer.get("price")
    availability = offer.get("availability", "")

    if "InStock" in availability:
        stock_status = "in stock"
    elif "OutOfStock" in availability:
        stock_status = "out of stock"
    else:
        stock_status = "unknown"

    return {
        "title": name,
        "price": price,
        "stock_status": stock_status
    }
