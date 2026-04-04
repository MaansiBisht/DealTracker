import json
import re
import time
from bs4 import BeautifulSoup


def scrape_flipkart(driver, url):
    driver.get(url)
    time.sleep(10)
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    sold_out_div = soup.find('div', class_='Z8JjpR')
    stock_status = "unknown"
    if sold_out_div and "Sold Out" in sold_out_div.get_text(strip=True):
        stock_status = "out of stock"
    else:
        found_sold_out_script = False
        scripts = soup.find_all("script")
        for script in scripts:
            if script.string and '"type":"AnnouncementValue"' in script.string:
                if '"title":"Sold Out"' in script.string:
                    stock_status = "out of stock"
                    found_sold_out_script = True
                    break
        if not found_sold_out_script:
            stock_status = "in stock"

    price = None
    scripts = soup.find_all("script")
    for script in scripts:
        if script.string:
            matches = re.search(r'"finalPrice":\s*({.*?})', script.string)
            if matches:
                try:
                    final_price = json.loads(matches.group(1))
                    if "decimalValue" in final_price:
                        price = final_price["decimalValue"]
                        break 
                except json.JSONDecodeError:
                    continue

    return {
        "stock_status": stock_status,
        "price": price
    }
