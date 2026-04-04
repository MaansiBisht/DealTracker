import json
import re
import time
from bs4 import BeautifulSoup


def scrape_makemytrip(driver, url):
    """
    Scrape hotel price from MakeMyTrip
    URL should be a direct hotel page with dates
    Example: https://www.makemytrip.com/hotels/hotel-details/?hotelId=...&checkin=...&checkout=...
    """
    driver.get(url)
    time.sleep(10)
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    hotel_name = None
    price = None
    availability = "unknown"

    # Get hotel name
    name_elem = soup.find('h1', {'id': 'hotel-name'})
    if not name_elem:
        name_elem = soup.find('h1', {'class': re.compile(r'hotelName|hotel-name')})
    if not name_elem:
        name_elem = soup.find('p', {'class': re.compile(r'latoBlack')})
    if name_elem:
        hotel_name = name_elem.get_text(strip=True)

    # Try JSON-LD schema
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

    # Fallback: parse price from HTML
    if not price:
        price_selectors = [
            {'id': 'hlistpg_hotel_shown_price'},
            {'class': re.compile(r'actual-price|finalPrice|priceValue')},
            {'class': 'pricePerNight'},
        ]
        
        for selector in price_selectors:
            price_elem = soup.find(['span', 'p', 'div'], selector)
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price_clean = re.sub(r'[^\d.]', '', price_text.replace(',', ''))
                if price_clean:
                    price = price_clean
                    break

    # Also check for price in data attributes
    if not price:
        price_attr = soup.find(attrs={'data-price': True})
        if price_attr:
            price = price_attr.get('data-price')

    # Check availability
    sold_out = soup.find(string=re.compile(r'sold out|no rooms|not available', re.IGNORECASE))
    if sold_out:
        availability = "sold out"
    elif price:
        availability = "available"

    # Get rating
    rating = None
    rating_elem = soup.find('span', {'class': re.compile(r'rating|ratingCount')})
    if not rating_elem:
        rating_elem = soup.find('p', {'class': re.compile(r'rating')})
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


def scrape_goibibo(driver, url):
    """
    Scrape hotel price from Goibibo (owned by MakeMyTrip, similar structure)
    """
    driver.get(url)
    time.sleep(10)
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    hotel_name = None
    price = None
    availability = "unknown"

    # Get hotel name
    name_elem = soup.find('h1', {'class': re.compile(r'HotelName|hotel-name')})
    if not name_elem:
        name_elem = soup.find('h1')
    if name_elem:
        hotel_name = name_elem.get_text(strip=True)

    # Try JSON-LD schema
    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        try:
            data = json.loads(script.string)
            if isinstance(data, dict) and data.get("@type") in ["Hotel", "LodgingBusiness"]:
                if not hotel_name:
                    hotel_name = data.get("name")
                offers = data.get("offers")
                if offers and isinstance(offers, dict):
                    price = offers.get("price")
        except Exception:
            continue

    # Fallback price parsing
    if not price:
        price_elem = soup.find(['span', 'div'], {'class': re.compile(r'price|Price|finalPrice')})
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            price_clean = re.sub(r'[^\d.]', '', price_text.replace(',', ''))
            if price_clean:
                price = price_clean

    # Check availability
    sold_out = soup.find(string=re.compile(r'sold out|no rooms|unavailable', re.IGNORECASE))
    if sold_out:
        availability = "sold out"
    elif price:
        availability = "available"

    return {
        "title": hotel_name,
        "price": price,
        "stock_status": availability,
        "type": "hotel"
    }
