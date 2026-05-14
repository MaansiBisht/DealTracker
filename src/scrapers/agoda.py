import json
import re
import time
from bs4 import BeautifulSoup


def scrape_agoda(driver, url):
    """
    Scrape hotel price from Agoda
    URL should be a direct hotel page with dates
    Example: https://www.agoda.com/hotel-name/hotel/city.html?checkIn=2024-05-01&checkOut=2024-05-02
    """
    driver.get(url)
    time.sleep(10)
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    hotel_name = None
    price = None
    availability = "unknown"

    # Get hotel name
    name_elem = soup.find('h1', {'data-selenium': 'hotel-header-name'})
    if not name_elem:
        name_elem = soup.find('h1', {'class': re.compile(r'HeaderTitle|hotel-name')})
    if not name_elem:
        name_elem = soup.find('h1')
    if name_elem:
        hotel_name = name_elem.get_text(strip=True)

    # Try JSON-LD schema first
    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        try:
            data = json.loads(script.string)
            if isinstance(data, dict):
                if data.get("@type") in ["Hotel", "LodgingBusiness"]:
                    if not hotel_name:
                        hotel_name = data.get("name")
                    offers = data.get("offers")
                    if offers:
                        if isinstance(offers, dict):
                            price = offers.get("price")
                        elif isinstance(offers, list) and offers:
                            price = offers[0].get("price")
        except Exception:
            continue

    # Try to find price in embedded JSON data (Agoda uses a lot of inline JSON)
    if not price:
        script_tags = soup.find_all('script')
        for script in script_tags:
            if script.string and 'displayPrice' in script.string:
                try:
                    # Look for price patterns in JavaScript
                    price_match = re.search(r'"displayPrice"\s*:\s*"?(\d+\.?\d*)"?', script.string)
                    if price_match:
                        price = price_match.group(1)
                        break
                    price_match = re.search(r'"price"\s*:\s*"?(\d+\.?\d*)"?', script.string)
                    if price_match:
                        price = price_match.group(1)
                        break
                except Exception:
                    continue

    # Fallback: parse price from HTML
    if not price:
        price_selectors = [
            {'data-selenium': 'display-price'},
            {'data-element-name': 'final-price'},
            {'class': re.compile(r'PropertyCardPrice|price-text|MainPrice')},
        ]
        
        for selector in price_selectors:
            price_elem = soup.find(['span', 'div'], selector)
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price_clean = re.sub(r'[^\d.]', '', price_text.replace(',', ''))
                if price_clean:
                    price = price_clean
                    break

    # Check availability — only look in dedicated containers, not the whole
    # page. Agoda lists individual room types, some marked "Sold Out", which
    # would falsely flag the hotel when other rooms are still bookable.
    no_rooms = soup.find('div', {'data-selenium': 'no-rooms-message'})
    page_soldout = soup.find(
        ['div', 'section'],
        {'data-selenium': re.compile(r'soldout|no-availability', re.IGNORECASE)},
    )
    if no_rooms or page_soldout:
        availability = "sold out"
    elif price:
        availability = "available"

    # Get rating
    rating = None
    rating_elem = soup.find('div', {'data-selenium': 'review-score'})
    if not rating_elem:
        rating_elem = soup.find('span', {'class': re.compile(r'review-score|Rating')})
    if rating_elem:
        rating_text = rating_elem.get_text(strip=True)
        rating_match = re.search(r'(\d+\.?\d*)', rating_text)
        if rating_match:
            rating = rating_match.group(1)

    return {
        "title": hotel_name,
        "price": price,
        "stock_status": availability,
        "rating": rating,
        "type": "hotel"
    }
