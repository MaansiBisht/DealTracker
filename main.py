from datetime import datetime
import time

from src.cli import get_user_input
from src.utils.driver import create_driver
from src.utils.email import send_email
from src.scrapers import route_scraper, is_hotel_platform


def run_hotel_tracking(url, price_threshold, email, driver):
    """Single-date hotel tracking. The user-supplied URL has checkin/checkout
    baked in; we scrape that one stay every 3 hours until the threshold is met."""
    sent = False

    while not sent:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"\n[{now}] Scraping hotel price…")

        result = route_scraper(driver, url)
        if not result:
            print("Failed to scrape hotel info.")
        else:
            title = result.get('title') or 'Hotel'
            price_str = result.get('price')
            availability = result.get('stock_status', 'unknown')
            print(f"{title} — price={price_str} availability={availability}")

            if price_threshold and price_str:
                try:
                    price_num = float(str(price_str).replace('₹', '').replace(',', '').strip())
                    if price_num <= price_threshold:
                        msg = (
                            f"🔔 {title}\n"
                            f"Price ₹{price_num:,.0f} is at or below your threshold of ₹{price_threshold:,.0f}.\n\n"
                            f"URL: {url}"
                        )
                        send_email("Hotel Price Alert", msg, email)
                        print(msg)
                        sent = True
                    else:
                        print(f"Above threshold (₹{price_threshold:,.0f}); will retry.")
                except ValueError as e:
                    print(f"Could not parse price: {e}")

        if not sent:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"[{now}] Sleeping 3h (Ctrl+C to stop)…")
            time.sleep(10800)


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
        if is_hotel_platform(url):
            print("\n🏨 Hotel detected — scraping the date in your URL every 3 hours")
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
