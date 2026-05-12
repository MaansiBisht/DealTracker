import logging
from urllib.parse import urlparse

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

# Hostname → platform key. Matched exactly OR by domain suffix
# (so `in.amazfit.com` and `amazfit.com` both resolve to `amazfit`).
# Short / share hostnames included so app-share links route correctly
# even before url_normalizer follows their redirect.
PLATFORM_HOSTS = {
    # canonical
    'amazon.in': 'amazon',
    'amazon.com': 'amazon',
    'amazon.co.uk': 'amazon',
    'amazon.de': 'amazon',
    'amazon.fr': 'amazon',
    'amazon.it': 'amazon',
    'amazon.es': 'amazon',
    'amazon.ae': 'amazon',
    'amazon.sa': 'amazon',
    'flipkart.com': 'flipkart',
    'myntra.com': 'myntra',
    'amul.com': 'amul',
    'amazfit.com': 'amazfit',
    'booking.com': 'booking',
    'makemytrip.com': 'makemytrip',
    'goibibo.com': 'goibibo',
    'agoda.com': 'agoda',
    # short / share links
    'amzn.in': 'amazon',
    'amzn.eu': 'amazon',
    'amzn.to': 'amazon',
    'a.co': 'amazon',
    'fkrt.it': 'flipkart',
    'dl.flipkart.com': 'flipkart',
}


HOTEL_PLATFORMS = ['booking', 'makemytrip', 'goibibo', 'agoda']


def get_platform_from_url(url):
    """Return the platform key for a URL, or 'unknown'.

    Hostname-based: parses the URL, strips a leading `www.`, then matches
    either exactly against PLATFORM_HOSTS or by domain suffix (so subdomains
    like `in.amazfit.com` or `shop.amul.com` route correctly).
    """
    try:
        host = (urlparse(url).hostname or '').lower()
    except Exception:
        return 'unknown'
    if not host:
        return 'unknown'
    if host.startswith('www.'):
        host = host[4:]
    for pattern, platform in PLATFORM_HOSTS.items():
        if host == pattern or host.endswith('.' + pattern):
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
