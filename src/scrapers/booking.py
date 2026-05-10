import json
import re
import time
from bs4 import BeautifulSoup


def scrape_booking(driver, url):
    """
    Scrape hotel price from Booking.com
    URL should be a direct hotel page with dates selected
    Example: https://www.booking.com/hotel/in/taj-mahal-palace.html?checkin=2024-05-01&checkout=2024-05-02
    """
    driver.get(url)
    time.sleep(8)
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    hotel_name = None
    price = None
    availability = "unknown"

    # Try to get hotel name
    name_elem = soup.find('h2', {'class': re.compile(r'pp-header__title|d2fee87262')})
    if not name_elem:
        name_elem = soup.find('h2', {'data-testid': 'title'})
    if name_elem:
        hotel_name = name_elem.get_text(strip=True)

    # Try JSON-LD schema first
    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        try:
            data = json.loads(script.string)
            if isinstance(data, dict):
                if data.get("@type") == "Hotel":
                    if not hotel_name:
                        hotel_name = data.get("name")
                    offers = data.get("priceRange") or data.get("offers")
                    if offers:
                        if isinstance(offers, dict):
                            price = offers.get("price")
        except Exception:
            continue

    # Fallback: parse price from HTML
    if not price:
        # Booking.com price selectors (they change frequently)
        price_selectors = [
            {'data-testid': 'price-and-discounted-price'},
            {'class': re.compile(r'prco-valign-middle-helper|bui-price-display__value')},
            {'class': 'prco-inline-block-maker-helper'},
        ]
        
        for selector in price_selectors:
            price_elem = soup.find('span', selector)
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                # Extract numeric price
                price_clean = re.sub(r'[^\d.]', '', price_text.replace(',', ''))
                if price_clean:
                    price = price_clean
                    break

    # If we extracted a price the hotel is bookable on this date.
    # Otherwise look for an unambiguous "no rooms" container — body-wide
    # text search picks up "sold out" from sidebars/recommendations and
    # falsely flags an available hotel.
    if price:
        availability = "available"
    else:
        no_rooms = soup.find(
            ['div', 'span'],
            string=re.compile(r'^\s*(sold out|no rooms available|unavailable)\s*$', re.IGNORECASE),
        )
        availability = "sold out" if no_rooms else "unknown"

    # Try to get rating
    rating = None
    rating_elem = soup.find('div', {'data-testid': 'review-score-component'})
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
