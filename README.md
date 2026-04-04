# DealTracker
DealTracker is a Python script that monitors products and hotels across multiple platforms, sending direct email alerts when items are back in stock or when prices drop below your set threshold. This tool automates deal and restock tracking for both products and hotel bookings.

## Features

- **Stock Alerts:** Get notified when a product is back in stock.
- **Price Alerts:** Receive emails when a product's price drops below your specified value.
- **Hotel Price Tracking:** Monitor hotel prices across Booking.com, MakeMyTrip, Goibibo, and Agoda.
- **30-Day Hotel Scanning:** Check prices for each day over the next month in a single scan.
- **Multi-Platform Support:** Works with Amul, Myntra, Amazon, Flipkart, Amazfit, and major hotel booking sites.
- **Automated Email Notifications:** Direct alerts sent to your inbox.
- **Customizable Monitoring:** Easily set your own products, hotels, and price thresholds.
- **Modular Architecture:** Easy to add new site scrapers.

## Project Structure

```
DealTracker/
├── main.py                           # Main entry point (auto-detects product vs hotel)
├── start_pullman_all_platforms.py   # Multi-platform hotel scanner
├── src/
│   ├── __init__.py
│   ├── config.py                     # Configuration and environment variables
│   ├── cli.py                        # User input handling
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── email.py                  # Email notification functionality
│   │   └── driver.py                 # Selenium driver setup
│   └── scrapers/
│       ├── __init__.py               # Scraper routing + hotel detection
│       ├── hotel_scanner.py          # 30-day hotel price scanning
│       ├── base.py                   # Base scraper utilities
│       ├── amul.py
│       ├── myntra.py
│       ├── flipkart.py
│       ├── amazon.py
│       ├── amazfit.py
│       ├── booking.py                # Booking.com scraper
│       ├── makemytrip.py             # MakeMyTrip + Goibibo scrapers
│       └── agoda.py                  # Agoda scraper
├── requirements.txt
└── README.md
```

## Technologies Used

- Python 3
- [Selenium](https://www.selenium.dev/) (for web automation)
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) (for HTML parsing)
- [smtplib](https://docs.python.org/3/library/smtplib.html) and [email.mime](https://docs.python.org/3/library/email.mime.html) (for sending emails)

## Setup & Usage

1. **Clone the repository:**
    ```
    git clone https://github.com/MaansiBisht/DealTracker.git
    cd DealTracker
    ```

2. **Install dependencies:**
    ```
    pip install -r requirements.txt
    ```

3. **Configure environment variables:**
    - Create a `.env` file in the project root with your email credentials and other required settings.
    - Example:
      ```
      EMAIL_ADDRESS=your_email@example.com
      EMAIL_PASSWORD=your_password
      PINCODE=123456
      ```

4. **Run the script:**
    ```
    python main.py
    ```
    
5. **Enter product/hotel details and thresholds via CLI:**
    - When you run the script, you will be prompted in the terminal to enter the product/hotel URLs, desired alert prices, and other relevant details for monitoring.
    - The script automatically detects if you're tracking a product or hotel and adjusts the monitoring accordingly.

## Hotel Tracking

For hotel price tracking, URLs must include check-in/check-out dates:
- **Booking.com:** `https://www.booking.com/hotel/in/hotel-name.html?checkin=2024-05-01&checkout=2024-05-02`
- **MakeMyTrip:** `https://www.makemytrip.com/hotels/hotel-details/?checkin=2024-05-01&checkout=2024-05-02`
- **Agoda:** `https://www.agoda.com/hotel-name/hotel/city.html?checkIn=2024-05-01&checkOut=2024-05-02`

**Multi-Platform Hotel Scanner:**
```bash
python start_pullman_all_platforms.py
```
This script scans a specific hotel across all supported platforms simultaneously and finds the best deals.

**Monitoring Intervals:**
- **Products:** Check every hour
- **Hotels:** Scan next 30 days every 3 hours

## Adding a New Site Scraper

### Product Scraper
1. Create a new file in `src/scrapers/` (e.g., `newsite.py`)
2. Implement a `scrape_newsite(driver, url)` function that returns:
   ```python
   {
       "title": "Product Name",  # optional
       "price": "1234.56",
       "stock_status": "in stock"  # or "out of stock"
   }
   ```
3. Register the scraper in `src/scrapers/__init__.py`:
   - Add import: `from src.scrapers.newsite import scrape_newsite`
   - Add to `SCRAPERS` dict: `'newsite': scrape_newsite`
   - Add to `PLATFORM_PATTERNS`: `'newsite.com': 'newsite'`
4. Update `SUPPORTED_PLATFORMS` in `src/config.py`

### Hotel Scraper
1. Create a new file in `src/scrapers/` (e.g., `newhotel.py`)
2. Implement a `scrape_newhotel(driver, url)` function that returns:
   ```python
   {
       "title": "Hotel Name",
       "price": "1234.56",
       "stock_status": "available",  # or "sold out", "unavailable"
       "rating": "8.5",  # optional
       "type": "hotel"
   }
   ```
3. Register the scraper in `src/scrapers/__init__.py`:
   - Add import: `from src.scrapers.newhotel import scrape_newhotel`
   - Add to `SCRAPERS` dict: `'newhotel': scrape_newhotel`
   - Add to `PLATFORM_PATTERNS`: `'newhotel.com': 'newhotel'`
   - Add to `HOTEL_PLATFORMS` list: `'newhotel'`
4. Update `SUPPORTED_HOTELS` in `src/config.py`

## Notes

- Make sure you have [ChromeDriver](https://sites.google.com/chromium.org/driver/) installed and available in your PATH for Selenium to work.
- This script is for personal use and educational purposes. Please respect the terms of service of the websites you monitor.

![Demo](/screencast/productAlerts.gif)
