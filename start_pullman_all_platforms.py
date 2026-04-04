#!/usr/bin/env python3
"""
Start tracking Pullman New Delhi Aerocity across all hotel platforms
"""

import sys
import time
from datetime import datetime, timedelta
from src.utils.driver import create_driver
from src.utils.email import send_email
from src.scrapers import (
    SCRAPERS, 
    scan_hotel_prices_monthly,
    find_best_prices
)

def get_pullman_urls():
    """Generate Pullman Delhi URLs for all platforms"""
    today = datetime.now().date()
    next_monday = today + timedelta(days=(7-today.weekday())%7 or 7)
    next_tuesday = next_monday + timedelta(days=1)
    
    checkin = next_monday.strftime("%Y-%m-%d")
    checkout = next_tuesday.strftime("%Y-%m-%d")
    
    urls = {
        'booking': f"https://www.booking.com/hotel/in/pullman-new-delhi-aerocity.html?checkin={checkin}&checkout={checkout}",
        'makemytrip': f"https://www.makemytrip.com/hotels/pullman-new-delhi-aerocity-hotel-details/?checkin={checkin}&checkout={checkout}",
        'goibibo': f"https://www.goibibo.com/hotels/pullman-new-delhi-aerocity-hotel-details/?checkin={checkin}&checkout={checkout}",
        'agoda': f"https://www.agoda.com/pullman-new-delhi-aerocity/hotel/new-delhi-in.html?checkIn={checkin}&checkOut={checkout}",
    }
    
    return urls

def scan_all_platforms(driver, urls, price_threshold):
    """Scan Pullman prices across all platforms"""
    all_results = {}
    
    print("=" * 80)
    print("🏨 Pullman New Delhi Aerocity - Multi-Platform Price Scan")
    print("=" * 80)
    print(f"Scanning next 30 days across {len(urls)} platforms...")
    print(f"Target price: ₹{price_threshold:,.0f}" if price_threshold else "No price threshold set")
    print("-" * 80)
    
    for platform, url in urls.items():
        print(f"\n📱 {platform.upper()}")
        print(f"URL: {url}")
        print("-" * 40)
        
        scraper = SCRAPERS.get(platform)
        if not scraper:
            print(f"❌ No scraper available for {platform}")
            continue
        
        try:
            results = scan_hotel_prices_monthly(driver, url, platform, scraper, days=30)
            all_results[platform] = results
            
            if results:
                hotel_name = next((r.get('hotel_name') for r in results if r.get('hotel_name')), 'Pullman Delhi')
                available = [r for r in results if r.get('price') is not None]
                unavailable = [r for r in results if r.get('availability') in ['sold out', 'unavailable']]
                
                print(f"✅ {hotel_name}")
                print(f"   Available: {len(available)} days | Sold out: {len(unavailable)} days")
                
                if available:
                    prices = [r['price'] for r in available]
                    min_price = min(prices)
                    max_price = max(prices)
                    avg_price = sum(prices) / len(prices)
                    
                    print(f"   Price range: ₹{min_price:,.0f} - ₹{max_price:,.0f}")
                    print(f"   Average: ₹{avg_price:,.0f}")
                    
                    best = find_best_prices(available, 3)
                    print(f"   Top 3 cheapest dates:")
                    for r in best:
                        print(f"     {r['date']} ({r['day']}): ₹{r['price']:,.0f}")
                    
                    # Check for price threshold matches
                    if price_threshold:
                        matching = [r for r in results if r.get('price') and r['price'] <= price_threshold]
                        if matching:
                            print(f"   🎯 {len(matching)} dates below target price!")
                else:
                    print("   ❌ No available rooms found")
            else:
                print(f"❌ Failed to get results from {platform}")
                
        except Exception as e:
            print(f"❌ Error scanning {platform}: {e}")
            all_results[platform] = []
    
    return all_results

def find_best_across_platforms(all_results, price_threshold=None):
    """Find the best deals across all platforms"""
    platform_bests = {}
    
    for platform, results in all_results.items():
        if results:
            available = [r for r in results if r.get('price') is not None]
            if available:
                best = min(available, key=lambda x: x['price'])
                platform_bests[platform] = best
    
    if not platform_bests:
        return None
    
    # Find overall best
    overall_best = min(platform_bests.values(), key=lambda x: x['price'])
    
    print("\n" + "=" * 80)
    print("🏆 BEST DEALS ACROSS PLATFORMS")
    print("=" * 80)
    
    for platform, result in sorted(platform_bests.items(), key=lambda x: x[1]['price']):
        price = result['price']
        date = result['date']
        day = result['day']
        status = "🎯" if price_threshold and price <= price_threshold else "💰"
        print(f"{status} {platform.upper()}: ₹{price:,.0f} on {date} ({day})")
    
    print(f"\n🥇 OVERALL BEST: {overall_best['price']:,.0f} on {overall_best['date']} ({overall_best['day']})")
    
    return overall_best

def main():
    print("=" * 80)
    print("🏨 Pullman New Delhi Aerocity - Multi-Platform Tracking")
    print("=" * 80)
    
    # Get user preferences
    print("\nSelect alert type:")
    print("  1. Price alert (notify when any platform has dates below target price)")
    print("  2. Daily scan only (just show prices, no alerts)")
    print("  3. Exit")
    
    alert_type = input("Enter 1, 2, or 3: ")
    if alert_type.strip() == "3" or alert_type.strip().lower() == 'exit':
        print("Stopped by user.")
        sys.exit()
    
    price_threshold = None
    if alert_type == "1":
        while True:
            price_input = input("Enter your target price per night (or type 'exit' to quit): ")
            if price_input.strip().lower() == 'exit':
                print("Stopped by user.")
                sys.exit()
            try:
                price_threshold = float(price_input)
                break
            except ValueError:
                print("Please enter a valid number for the price.")
    
    email = input("Enter your email for notifications (or type 'exit' to quit): ")
    if email.strip().lower() == 'exit':
        print("Stopped by user.")
        sys.exit()
    
    # Get URLs for all platforms
    urls = get_pullman_urls()
    
    driver = create_driver()
    sent = False
    
    try:
        while not sent:
            print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting multi-platform scan...")
            
            # Scan all platforms
            all_results = scan_all_platforms(driver, urls, price_threshold)
            
            # Find best deals
            best_deal = find_best_across_platforms(all_results, price_threshold)
            
            # Check for alerts
            if alert_type == "1" and price_threshold and all_results:
                matching_deals = []
                
                for platform, results in all_results.items():
                    if results:
                        matching = [r for r in results if r.get('price') and r['price'] <= price_threshold]
                        if matching:
                            matching_deals.extend([(platform, r) for r in matching])
                
                if matching_deals:
                    # Sort by price
                    matching_deals.sort(key=lambda x: x[1]['price'])
                    
                    alert_msg = f"🔔 Pullman Delhi - Found {len(matching_deals)} dates below ₹{price_threshold:,.0f}:\n\n"
                    
                    for platform, result in matching_deals[:15]:  # Top 15 matches
                        alert_msg += f"  {platform.upper()}: {result['date']} ({result['day']}) - ₹{result['price']:,.0f}\n"
                    
                    alert_msg += f"\nBest deal: {matching_deals[0][0].upper()} - ₹{matching_deals[0][1]['price']:,.0f} on {matching_deals[0][1]['date']}"
                    alert_msg += f"\n\nHotel: Pullman New Delhi Aerocity"
                    
                    print(f"\n{alert_msg}")
                    send_email("Pullman Delhi - Price Alert!", alert_msg, email)
                    sent = True
                else:
                    if best_deal:
                        print(f"\n💡 Best price across all platforms: ₹{best_deal['price']:,.0f} on {best_deal['date']}")
                        print(f"🎯 Target price: ₹{price_threshold:,.0f}")
                    print("No dates below target price yet.")
            
            if not sent:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"\n[{now}] Next scan in 3 hours (Ctrl+C to stop)...")
                time.sleep(10800)  # 3 hours
    
    except KeyboardInterrupt:
        print("\nStopped by user. Exiting gracefully.")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
