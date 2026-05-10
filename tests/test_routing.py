"""URL → platform routing for both product and hotel scrapers."""

import pytest

from src.scrapers import (
    HOTEL_PLATFORMS,
    SCRAPERS,
    get_platform_from_url,
    is_hotel_platform,
)


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.amazon.in/dp/B08BPQ9CZ1", "amazon"),
        ("https://amazon.com/dp/foo", "amazon"),
        ("https://www.flipkart.com/foo/p/itm123", "flipkart"),
        ("https://www.myntra.com/tshirts/x/y/123/buy", "myntra"),
        ("https://shop.amul.com/en/product/x", "amul"),
        ("https://in.amazfit.com/products/foo", "amazfit"),
        ("https://www.booking.com/hotel/in/foo.html", "booking"),
        ("https://www.makemytrip.com/hotels/x", "makemytrip"),
        ("https://www.goibibo.com/hotels/x", "goibibo"),
        ("https://www.agoda.com/hotel/x", "agoda"),
        ("https://example.com/anything", "unknown"),
    ],
)
def test_get_platform_from_url(url, expected):
    assert get_platform_from_url(url) == expected


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.booking.com/hotel/in/foo.html", True),
        ("https://www.amazon.in/dp/B08BPQ9CZ1", False),
        ("https://example.com", False),
    ],
)
def test_is_hotel_platform(url, expected):
    assert is_hotel_platform(url) is expected


def test_every_hotel_platform_has_a_registered_scraper():
    for platform in HOTEL_PLATFORMS:
        assert platform in SCRAPERS, f"{platform} listed as hotel but no scraper"
