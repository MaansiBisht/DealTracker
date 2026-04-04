from datetime import datetime
import time

from src.cli import get_user_input
from src.utils.driver import create_driver
from src.utils.email import send_email
from src.scrapers import (
    route_scraper, 
    is_hotel_platform, 
    get_platform_from_url,
    SCRAPERS,
    scan_hotel_prices_monthly,
    format_price_report,
    find_best_prices
)


def run_hotel_tracking(url, price_threshold, email, driver):
    """Hotel-specific tracking: scan next 30 days, check once per day"""
    platform = get_platform_from_url(url)
    scraper = SCRAPERS.get(platform)
    
    if not scraper:
        print(f"Unsupported hotel platform: {platform}")
        return
    
    sent = False
    
    while not sent:
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting hotel price scan...")
        
        # Scan prices for next 30 days
        results = scan_hotel_prices_monthly(driver, url, platform, scraper, days=30)
        
        if not results:
            print("Failed to scan hotel prices.")
        else:
            # Get hotel name from first successful result
            hotel_name = next((r.get('hotel_name') for r in results if r.get('hotel_name')), 'Hotel')
            
            # Print summary report
            report = format_price_report(results, hotel_name)
            print(report)
            
            # Check if any date meets the price threshold
            if price_threshold:
                best_prices = find_best_prices(results, top_n=5)
                matching_dates = [r for r in results if r.get('price') and r['price'] <= price_threshold]
                
                if matching_dates:
                    alert_msg = f"🔔 {hotel_name} - Found {len(matching_dates)} dates below ₹{price_threshold:,.0f}:\n\n"
                    for r in matching_dates[:10]:
                        alert_msg += f"  {r['date']} ({r['day']}): ₹{r['price']:,.0f}\n"
                    alert_msg += f"\nURL: {url}"
                    
                    print(f"\n{alert_msg}")
                    send_email("Hotel Price Alert", alert_msg, email)
                    sent = True
                else:
                    if best_prices:
                        print(f"\nLowest price found: ₹{best_prices[0]['price']:,.0f} on {best_prices[0]['date']}")
                        print(f"Target price: ₹{price_threshold:,.0f}")
                    print("No dates below target price yet.")
        
        if not sent:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n[{now}] Next scan in 3 hours (Ctrl+C to stop)...")
            time.sleep(10800)  # 3 hours


def run_product_tracking(url, alert_type, price_threshold, email, driver):
    """Product tracking: check hourly"""
    sent = False
    
    while not sent:
        result = route_scraper(driver, url)
        if not result:
            print("Failed to scrape the product info.")
            break

        # Stock alert flow
        if alert_type == "1":
            stock_status = result.get('stock_status', '').lower()
            print(f"Stock status: {stock_status}")
            if stock_status == 'in stock':
                send_email("Stock Alert", f"Product is in stock: {url}", email)
                sent = True
            elif stock_status == 'out of stock':
                print("Product is out of stock.")
            else:
                print("Could not determine stock status.")

        # Price alert flow
        elif alert_type == "2":
            price_str = result.get('price')
            print(f"Price: {price_str}")
            if price_str:
                try:
                    price_num = float(str(price_str).replace('₹', '').replace(',', '').strip())
                    print(f"Current price: {price_num}")
                    if price_num <= price_threshold:
                        send_email("Price Alert", f"Price dropped to {price_num}: {url}", email)
                        sent = True
                    else:
                        print(f"Price is above threshold ({price_threshold}).")
                except Exception as e:
                    print(f"Could not parse price: {e}")
            else:
                print("Price not found.")

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] Sleeping (Ctrl+C to stop)...")
        time.sleep(3600)


def main():
    url, alert_type, price_threshold, email = get_user_input()

    driver = create_driver()

    try:
        # Check if this is a hotel URL
        if is_hotel_platform(url):
            print("\n🏨 Hotel detected - will scan prices for next 30 days, checking every 3 hours")
            run_hotel_tracking(url, price_threshold, email, driver)
        else:
            print("\n📦 Product detected - checking hourly")
            run_product_tracking(url, alert_type, price_threshold, email, driver)

    except KeyboardInterrupt:
        print("\nStopped by user. Exiting gracefully.")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
