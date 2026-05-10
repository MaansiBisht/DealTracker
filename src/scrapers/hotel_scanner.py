import logging
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse


log = logging.getLogger(__name__)


def get_base_hotel_url(url):
    """Extract base hotel URL without date parameters"""
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)
    
    # Remove date-related parameters
    date_params = ['checkin', 'checkout', 'checkIn', 'checkOut', 'check_in', 'check_out']
    for param in date_params:
        query_params.pop(param, None)
    
    # Rebuild URL without dates
    new_query = urlencode(query_params, doseq=True)
    base_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
    return base_url


def build_hotel_url_with_dates(base_url, checkin_date, checkout_date, platform):
    """Build hotel URL with specific check-in/check-out dates"""
    parsed = urlparse(base_url)
    query_params = parse_qs(parsed.query)
    
    checkin_str = checkin_date.strftime("%Y-%m-%d")
    checkout_str = checkout_date.strftime("%Y-%m-%d")
    
    if platform == 'booking':
        query_params['checkin'] = [checkin_str]
        query_params['checkout'] = [checkout_str]
    elif platform == 'agoda':
        query_params['checkIn'] = [checkin_str]
        query_params['checkOut'] = [checkout_str]
    elif platform in ['makemytrip', 'goibibo']:
        query_params['checkin'] = [checkin_str]
        query_params['checkout'] = [checkout_str]
    
    new_query = urlencode(query_params, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))


def scan_hotel_prices_monthly(driver, url, platform, scraper_func, days=30):
    """
    Scan hotel prices for each day over the next month.
    Returns a list of {date, price, availability} for each day.
    """
    base_url = get_base_hotel_url(url)
    today = datetime.now().date()
    
    results = []
    
    log.info("scanning hotel prices · platform=%s · %d days", platform, days)

    for i in range(days):
        checkin = today + timedelta(days=i)
        checkout = checkin + timedelta(days=1)
        
        dated_url = build_hotel_url_with_dates(base_url, checkin, checkout, platform)
        
        try:
            result = scraper_func(driver, dated_url)
            
            price = result.get('price')
            availability = result.get('stock_status', 'unknown')
            hotel_name = result.get('title')
            
            price_num = None
            if price:
                try:
                    price_num = float(str(price).replace('₹', '').replace(',', '').strip())
                except:
                    pass
            
            day_result = {
                'date': checkin.strftime("%Y-%m-%d"),
                'day': checkin.strftime("%a"),
                'price': price_num,
                'price_raw': price,
                'availability': availability,
                'hotel_name': hotel_name
            }
            results.append(day_result)
            
            status = f"₹{price_num:,.0f}" if price_num else availability
            log.debug("%s (%s): %s", checkin.strftime('%Y-%m-%d'), checkin.strftime('%a'), status)

        except Exception as e:
            results.append({
                'date': checkin.strftime("%Y-%m-%d"),
                'day': checkin.strftime("%a"),
                'price': None,
                'availability': 'error',
                'error': str(e),
            })
            log.warning("%s scan failed: %s", checkin.strftime('%Y-%m-%d'), e)
    
    return results


def find_best_prices(results, top_n=5):
    """Find the cheapest dates from scan results"""
    available = [r for r in results if r.get('price') is not None]
    if not available:
        return []
    
    sorted_by_price = sorted(available, key=lambda x: x['price'])
    return sorted_by_price[:top_n]


def format_price_report(results, hotel_name=None):
    """Format a summary report of scanned prices"""
    available = [r for r in results if r.get('price') is not None]
    unavailable = [r for r in results if r.get('availability') in ['sold out', 'unavailable']]
    
    report = []
    report.append("=" * 50)
    if hotel_name:
        report.append(f"Hotel: {hotel_name}")
    report.append(f"Scanned {len(results)} days")
    report.append(f"Available: {len(available)} days | Sold out: {len(unavailable)} days")
    report.append("=" * 50)
    
    if available:
        prices = [r['price'] for r in available]
        min_price = min(prices)
        max_price = max(prices)
        avg_price = sum(prices) / len(prices)
        
        report.append(f"Price Range: ₹{min_price:,.0f} - ₹{max_price:,.0f}")
        report.append(f"Average: ₹{avg_price:,.0f}")
        report.append("")
        report.append("Top 5 Cheapest Dates:")
        
        best = find_best_prices(available, 5)
        for r in best:
            report.append(f"  {r['date']} ({r['day']}): ₹{r['price']:,.0f}")
    else:
        report.append("No available rooms found for the next month.")
    
    report.append("=" * 50)
    return "\n".join(report)
