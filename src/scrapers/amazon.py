import time
from bs4 import BeautifulSoup


def scrape_amazon(driver, url):
    driver.get(url)
    time.sleep(10)
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    # Extract stock availability
    stock_status = None
    stock_div = soup.find('div', id='availability')
    if stock_div:
        span = stock_div.find('span', class_='a-color-success')
        if span:
            stock_status = span.text.strip()
            if stock_status == "in stock":
                stock_status = "in stock"
            elif  stock_status == "currently unavailable":
                stock_status = "out of stock"
            else:
                stock_status = "unknown"

    # Extract price
    price_text = None
    price_span = soup.find('span', class_='a-price')
    if price_span:
        offscreen_span = price_span.find('span', class_='a-offscreen')
        if offscreen_span:
            price_text = offscreen_span.text.strip()

    return {'stock_status': stock_status, 'price': price_text}
