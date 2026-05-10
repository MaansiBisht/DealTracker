import logging

from .amul import scrape_amul
from .myntra import scrape_myntra
from .flipkart import scrape_flipkart
from .amazon import scrape_amazon
from .amazfit import scrape_amazfit
from .booking import scrape_booking
from .makemytrip import scrape_makemytrip, scrape_goibibo
from .agoda import scrape_agoda

log = logging.getLogger(__name__)


SCRAPERS = {
    'amul': scrape_amul,
    'myntra': scrape_myntra,
    'flipkart': scrape_flipkart,
    'amazon': scrape_amazon,
    'amazfit': scrape_amazfit,
    'booking': scrape_booking,
    'makemytrip': scrape_makemytrip,
    'goibibo': scrape_goibibo,
    'agoda': scrape_agoda,
}

PLATFORM_PATTERNS = {
    'myntra.com': 'myntra',
    'flipkart.com': 'flipkart',
    'amazon.': 'amazon',
    'amul.com': 'amul',
    'amazfit.com': 'amazfit',
    'booking.com': 'booking',
    'makemytrip.com': 'makemytrip',
    'goibibo.com': 'goibibo',
    'agoda.com': 'agoda',
}


HOTEL_PLATFORMS = ['booking', 'makemytrip', 'goibibo', 'agoda']


def get_platform_from_url(url):
    for pattern, platform in PLATFORM_PATTERNS.items():
        if pattern in url:
            return platform
    return 'unknown'


def is_hotel_platform(url):
    platform = get_platform_from_url(url)
    return platform in HOTEL_PLATFORMS


def route_scraper(driver, url):
    platform = get_platform_from_url(url)
    scraper = SCRAPERS.get(platform)
    if scraper:
        return scraper(driver, url)
    else:
        log.warning("unsupported platform or invalid URL: %s", url)
        return None
