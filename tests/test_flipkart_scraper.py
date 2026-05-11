"""Flipkart scraper — stock-classification correctness.

Regression-focused: the headline bug was that a URL pointing at an
out-of-stock variant (size/color) reported 'in stock' because sibling
variants on the same PDP kept the page-wide text free of OOS phrases.
These tests pin down the per-variant signals we now read.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from src.scrapers.flipkart import (
    _classify_availability,
    _classify_buybox_cta,
    _walk_jsonld,
    classify_stock,
    scrape_flipkart,
)


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


# ---------------------------------------------------------------------------
# _classify_availability — schema.org token mapping
# ---------------------------------------------------------------------------


class TestClassifyAvailability:
    def test_schema_url_out_of_stock(self):
        assert _classify_availability("https://schema.org/OutOfStock") == "out of stock"

    def test_schema_url_in_stock(self):
        assert _classify_availability("https://schema.org/InStock") == "in stock"

    def test_bare_token_sold_out(self):
        assert _classify_availability("SoldOut") == "out of stock"

    def test_bare_token_discontinued(self):
        assert _classify_availability("Discontinued") == "out of stock"

    def test_limited_availability_treated_as_in_stock(self):
        assert _classify_availability("LimitedAvailability") == "in stock"

    def test_none_input_returns_none(self):
        assert _classify_availability(None) is None

    def test_empty_string_returns_none(self):
        assert _classify_availability("") is None

    def test_unknown_token_returns_none(self):
        assert _classify_availability("MaybeMaybeNot") is None


# ---------------------------------------------------------------------------
# _walk_jsonld — Product offer extraction
# ---------------------------------------------------------------------------


class TestWalkJsonld:
    def test_returns_price_and_availability(self):
        html = """
        <script type="application/ld+json">
        {"@type":"Product","offers":{"price":"24999","availability":"https://schema.org/InStock"}}
        </script>
        """
        price, avail = _walk_jsonld(_soup(html))
        assert price == "24999"
        assert avail == "https://schema.org/InStock"

    def test_handles_offers_as_list(self):
        html = """
        <script type="application/ld+json">
        {"@type":"Product","offers":[{"price":"999","availability":"OutOfStock"}]}
        </script>
        """
        price, avail = _walk_jsonld(_soup(html))
        assert price == "999"
        assert avail == "OutOfStock"

    def test_returns_none_when_no_jsonld(self):
        assert _walk_jsonld(_soup("<div>nothing</div>")) == (None, None)

    def test_skips_malformed_jsonld(self):
        html = '<script type="application/ld+json">{not json}</script>'
        assert _walk_jsonld(_soup(html)) == (None, None)

    def test_falls_back_to_low_price(self):
        html = """
        <script type="application/ld+json">
        {"@type":"Product","offers":{"lowPrice":"500"}}
        </script>
        """
        price, _ = _walk_jsonld(_soup(html))
        assert price == "500"


# ---------------------------------------------------------------------------
# _classify_buybox_cta — action-button inspection
# ---------------------------------------------------------------------------


class TestClassifyBuyboxCta:
    def test_sold_out_button_signals_oos(self):
        html = '<button>Sold Out</button><button>Add to Wishlist</button>'
        assert _classify_buybox_cta(_soup(html)) == "out of stock"

    def test_notify_me_signals_oos(self):
        html = '<button>NOTIFY ME</button>'
        assert _classify_buybox_cta(_soup(html)) == "out of stock"

    def test_add_to_cart_signals_in_stock(self):
        html = '<button>ADD TO CART</button><button>BUY NOW</button>'
        assert _classify_buybox_cta(_soup(html)) == "in stock"

    def test_oos_wins_over_buy_cues_from_cross_sell(self):
        # The page lists 'add to cart' on related-product cards while the
        # main buy-box shows 'Sold Out' for the URL-pinned variant.
        html = """
        <button>Sold Out</button>
        <div class="recommendations">
          <button>Add to Cart</button>
          <button>Add to Cart</button>
        </div>
        """
        assert _classify_buybox_cta(_soup(html)) == "out of stock"

    def test_no_buttons_returns_none(self):
        assert _classify_buybox_cta(_soup("<div>nothing</div>")) is None

    def test_unrelated_buttons_return_none(self):
        html = '<button>Login</button><button>Help</button>'
        assert _classify_buybox_cta(_soup(html)) is None

    def test_anchor_role_button_counted(self):
        html = '<a role="button">Sold Out</a>'
        assert _classify_buybox_cta(_soup(html)) == "out of stock"


# ---------------------------------------------------------------------------
# classify_stock — layered decision (the headline regression)
# ---------------------------------------------------------------------------


class TestClassifyStock:
    def test_oos_variant_with_in_stock_siblings(self):
        """The bug: variant URL is OOS, page text doesn't say 'sold out'
        anywhere obvious because sibling variants dominate the markup.
        JSON-LD reflects the URL-pinned variant — trust it.
        """
        html = """
        <html><body>
          <script type="application/ld+json">
          {"@type":"Product","name":"Phone 128GB",
           "offers":{"price":"24999","availability":"https://schema.org/OutOfStock"}}
          </script>
          <div class="variant-picker">
            <span>64GB - available</span>
            <span>128GB - selected</span>
            <span>256GB - available</span>
          </div>
          <button>Notify Me</button>
          <div class="similar-products">
            <button>Add to Cart</button>
            <button>Add to Cart</button>
          </div>
        </body></html>
        """
        assert classify_stock(_soup(html)) == "out of stock"

    def test_in_stock_variant_via_jsonld(self):
        html = """
        <script type="application/ld+json">
        {"@type":"Product","offers":{"price":"24999","availability":"InStock"}}
        </script>
        <button>ADD TO CART</button>
        """
        assert classify_stock(_soup(html)) == "in stock"

    def test_no_jsonld_falls_back_to_cta_oos(self):
        html = '<html><body><button>Sold Out</button></body></html>'
        assert classify_stock(_soup(html)) == "out of stock"

    def test_no_jsonld_falls_back_to_cta_in_stock(self):
        html = '<html><body><button>ADD TO CART</button></body></html>'
        assert classify_stock(_soup(html)) == "in stock"

    def test_text_fallback_currently_unavailable(self):
        html = '<html><body><p>This item is currently unavailable.</p></body></html>'
        assert classify_stock(_soup(html)) == "out of stock"

    def test_returns_unknown_when_no_jsonld_no_cta_no_oos_text(self):
        """The recaptcha-interstitial / partial-render case. No JSON-LD
        Product, no buy-box buttons, no 'sold out' text → refuse to
        claim 'in stock'. Previously fell through to 'in stock' and
        caused false re-alerts on OOS variants.
        """
        html = '<html><body><p>Some unrelated content</p></body></html>'
        assert classify_stock(_soup(html)) == "unknown"

    def test_returns_in_stock_when_jsonld_present_but_no_availability_or_cta(self):
        """Page DID render (JSON-LD Product is there) but the JSON-LD
        lacked an availability field and no buttons surfaced. This is
        the legitimate 'rendered but quiet' case where 'in stock' is
        still the correct default.
        """
        html = """
        <script type="application/ld+json">
        {"@type":"Product","name":"thingy","offers":{"price":"100"}}
        </script>
        """
        assert classify_stock(_soup(html)) == "in stock"


# ---------------------------------------------------------------------------
# scrape_flipkart — end-to-end with a stub driver
# ---------------------------------------------------------------------------


class _StubDriver:
    """Minimal driver double — only get() and page_source are touched."""

    def __init__(self, page_source: str) -> None:
        self.page_source = page_source
        self.last_url: str | None = None

    def get(self, url: str) -> None:
        self.last_url = url


def test_scrape_flipkart_reports_oos_for_pinned_variant(monkeypatch):
    """End-to-end regression — the variant URL points at an OOS size and
    the scraper must report 'out of stock' even though sibling sizes are
    available in the variant picker."""
    monkeypatch.setattr("src.scrapers.flipkart.time.sleep", lambda *_: None)
    html = """
    <html><body>
      <script type="application/ld+json">
      {"@type":"Product",
       "offers":{"price":"24999","availability":"https://schema.org/OutOfStock"}}
      </script>
      <button>Notify Me</button>
      <div class="similar-products">
        <button>Add to Cart</button>
      </div>
    </body></html>
    """
    result = scrape_flipkart(_StubDriver(html), "https://www.flipkart.com/foo/p/itm1")
    assert result == {"stock_status": "out of stock", "price": "24999"}


def test_scrape_flipkart_unknown_when_page_empty(monkeypatch):
    monkeypatch.setattr("src.scrapers.flipkart.time.sleep", lambda *_: None)
    result = scrape_flipkart(_StubDriver("<html></html>"), "https://www.flipkart.com/x")
    assert result["stock_status"] == "unknown"
    assert result["price"] is None


def test_scrape_flipkart_recaptcha_returns_unknown(monkeypatch):
    """Flipkart's bot-detection interstitial — title is the giveaway.
    Must return 'unknown' and emit a warning, never a stock state.
    """
    monkeypatch.setattr("src.scrapers.flipkart.time.sleep", lambda *_: None)
    captcha_html = """
    <!DOCTYPE html><html lang=en><meta charset=UTF-8>
    <title>Flipkart reCAPTCHA</title>
    <link rel=stylesheet href=/recaptcha.css>
    <div id=challenge>verify you are human</div>
    """
    result = scrape_flipkart(_StubDriver(captcha_html), "https://www.flipkart.com/iphone/p/itm1")
    assert result == {"stock_status": "unknown", "price": None}


def test_scrape_flipkart_in_stock_happy_path(monkeypatch):
    monkeypatch.setattr("src.scrapers.flipkart.time.sleep", lambda *_: None)
    html = """
    <html><body>
      <script type="application/ld+json">
      {"@type":"Product",
       "offers":{"price":"1299","availability":"https://schema.org/InStock"}}
      </script>
      <button>ADD TO CART</button>
      <button>BUY NOW</button>
    </body></html>
    """
    result = scrape_flipkart(_StubDriver(html), "https://www.flipkart.com/foo/p/itm9")
    assert result == {"stock_status": "in stock", "price": "1299"}
