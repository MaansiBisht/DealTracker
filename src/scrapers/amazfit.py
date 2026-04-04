import json
import re
import time
from bs4 import BeautifulSoup


def scrape_amazfit(driver, url):
    driver.get(url)
    time.sleep(10)
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    # Amazfit uses Shopify - try JSON-LD schema first
    scripts = soup.find_all("script", type="application/ld+json")
    product_data = None

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

    name = None
    price = None
    stock_status = "unknown"

    if product_data:
        name = product_data.get("name")
        offers = product_data.get("offers", {})
        if isinstance(offers, list):
            offer = offers[0] if offers else {}
        else:
            offer = offers

        price = offer.get("price")
        availability = offer.get("availability", "")

        if "InStock" in availability:
            stock_status = "in stock"
        elif "OutOfStock" in availability:
            stock_status = "out of stock"
    else:
        # Fallback: parse HTML directly for Shopify product pages
        price_elem = soup.find('span', class_='price-item--sale') or soup.find('span', class_='price-item')
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            price_clean = re.sub(r'[^\d.]', '', price_text.replace('Rs.', '').replace(',', ''))
            if price_clean:
                price = price_clean

        # Check for sold out button or availability
        add_to_cart = soup.find('button', {'name': 'add'})
        if add_to_cart:
            if add_to_cart.get('disabled'):
                stock_status = "out of stock"
            else:
                stock_status = "in stock"
        
        # Check for sold out text
        sold_out = soup.find(string=re.compile(r'sold\s*out', re.IGNORECASE))
        if sold_out:
            stock_status = "out of stock"

    return {
        "title": name,
        "price": price,
        "stock_status": stock_status
    }
