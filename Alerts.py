import json
from dotenv import load_dotenv
import os
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
import time
import sys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import smtplib
from email.mime.text import MIMEText
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import re
from datetime import datetime

load_dotenv() 
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
PINCODE = os.getenv("PINCODE")

def get_user_input():
    print("=" * 50)
    print("        Welcome to the Product Alert Script")
    print("=" * 50)
    print("Currently supported: AMUL, MYNTRA\n")
    print("You can set up alerts for: Stock availablity , Low price")
    print("-" * 50)

    # URL input
    url = input("Enter the product URL (or type 'exit' to quit): ")
    if url.strip().lower() == 'exit':
        print("Stopped by user.")
        sys.exit()  

    # Alert type input
    print("\nSelect alert type:")
    print("  1. Stock alert")
    print("  2. Low price alert")
    print("  3. Exit")
    alert_type = input("Enter 1, 2, or 3: ")
    if alert_type.strip() == "3" or alert_type.strip().lower() == 'exit':
        print("Stopped by user.")
        sys.exit()

    if alert_type == "2":
        while True:
            price_input = input("Enter your target price (or type 'exit' to quit): ")
            if price_input.strip().lower() == 'exit':
                print("Stopped by user.")
                sys.exit()
            try:
                price_threshold = float(price_input)
                break
            except ValueError:
                print("Please enter a valid number for the price.")
    else:
        price_threshold = None

    # Email input
    email = input("Enter your email for notifications (or type 'exit' to quit): ")
    if email.strip().lower() == 'exit':
        print("Stopped by user.")
        sys.exit()

    print("=" * 50)
    return url, alert_type, price_threshold, email

def get_platform_from_url(url):
    if 'myntra.com' in url:
        return 'myntra'
    elif 'flipkart.com' in url:
        return 'flipkart'
    elif 'amazon.' in url:
        return 'amazon'
    elif 'amul.com' in url:
        return 'amul'
    else:
        return 'unknown'

def route_scraper(driver, url):
    platform = get_platform_from_url(url)
    if platform == 'amul':
        return scrape_amul(driver, url)
    elif platform == 'myntra':
        return scrape_myntra(driver, url)
    elif platform == 'flipkart':
        return scrape_flipkart(driver, url)
    elif platform == 'amazon':
        return scrape_amazon(driver, url)
    else:
        print("Unsupported platform or invalid URL.")
        return None

def scrape_amul(driver, url):
    driver.get(url)
    enter_pincode(driver, PINCODE)
    time.sleep(10) 
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    # Stock status
    sold_out_div = soup.find('div', class_='alert alert-danger mt-3')
    if sold_out_div and "Sold Out" in sold_out_div.get_text(strip=True):
        stock_status = "out of stock"
    else:
        stock_status = "in stock"

    # Price extraction
    price = None
    price_tags = soup.find_all("span", class_=lambda x: x and "price-new" in x)
    for tag in price_tags:
        price_text = tag.get_text(strip=True)
        if "₹" in price_text:
            price_clean = price_text.replace('₹', '').replace(',', '')
            try:
                price = price_clean
                break
            except ValueError:
                continue

    return {
        "stock_status": stock_status,
        "price": price
    }

def scrape_myntra(driver, url):
    driver.get(url)
    time.sleep(10)  # Wait for JS if needed
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    # Find all JSON-LD scripts
    scripts = soup.find_all("script", type="application/ld+json")
    product_data = None

    # Find the "Product" schema
    for script in scripts:
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                for item in data:
                    if item.get("@type") == "Product":
                        product_data = item
                        break
            elif data.get("@type") == "Product":
                product_data = data
                break
        except Exception:
            continue

    if not product_data:
        driver.save_screenshot("myntra_test.png")
        print("No Product schema found.")
        return None

    # Extract details
    name = product_data.get("name")
    price = None
    stock_status = None

    offers = product_data.get("offers", {})
    # Offers can be a list or dict
    if isinstance(offers, list):
        offer = offers[0]
    else:
        offer = offers

    price = offer.get("price")
    availability = offer.get("availability", "")

    if "InStock" in availability:
        stock_status = "in stock"
    elif "OutOfStock" in availability:
        stock_status = "out of stock"
    else:
        stock_status = "unknown"

    return {
        "title": name,
        "price": price,
        "stock_status": stock_status
    }

def scrape_flipkart(driver, url):
    driver.get(url)
    time.sleep(10)
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    sold_out_div = soup.find('div', class_='Z8JjpR')
    stock_status = "unknown"
    if sold_out_div and "Sold Out" in sold_out_div.get_text(strip=True):
        stock_status = "out of stock"
    else:
        found_sold_out_script = False
        scripts = soup.find_all("script")
        for script in scripts:
            if script.string and '"type":"AnnouncementValue"' in script.string:
                if '"title":"Sold Out"' in script.string:
                    stock_status = "out of stock"
                    found_sold_out_script = True
                    break
        if not found_sold_out_script:
            stock_status = "in stock"

    price = None
    scripts = soup.find_all("script")
    for script in scripts:
        if script.string:
            matches = re.search(r'"finalPrice":\s*({.*?})', script.string)
            if matches:
                try:
                    final_price = json.loads(matches.group(1))
                    if "decimalValue" in final_price:
                        price = final_price["decimalValue"]
                        break 
                except json.JSONDecodeError:
                    continue

    return {
        "stock_status": stock_status,
        "price": price
    }

def scrape_amazon(driver, url):
    driver.get(url)
    time.sleep(10)
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    # Extract stock availability
    stock_status = None
    stock_div = soup.find('div', id='availability')
    if stock_div:
        span = stock_div.find('span', class_='a-color-success')
        if span:
            stock_status = span.text.strip()
            if stock_status == "in stock":
                stock_status = "in stock"
            elif  stock_status == "currently unavailable":
                stock_status = "out of stock"
            else:
                stock_status = "unknown"

    # Extract price
    price_text = None
    price_span = soup.find('span', class_='a-price')
    if price_span:
        offscreen_span = price_span.find('span', class_='a-offscreen')
        if offscreen_span:
            price_text = offscreen_span.text.strip()

    return {'stock_status': stock_status, 'price': price_text}

def enter_pincode(driver, pincode):
    try:
        print("Waiting for pincode overlay to appear...")
        # Wait for the overlay/input to be present and visible
        WebDriverWait(driver, 15).until(
            EC.visibility_of_element_located((By.ID, "search"))
        )

        # Find all elements with id="search" and pick the visible one
        inputs = driver.find_elements(By.ID, "search")
        pincode_input = None
        for inp in inputs:
            if inp.is_displayed() and inp.is_enabled():
                pincode_input = inp
                break

        if not pincode_input:
            print("No interactable pincode input found.")
            return False

        # Scroll into view in case it's off-screen
        driver.execute_script("arguments[0].scrollIntoView(true);", pincode_input)
        time.sleep(0.5)

        # Enter the pincode
        pincode_input.clear()
        pincode_input.send_keys(pincode)
        print(f"Pincode '{pincode}' entered.")

        # Wait for the dropdown item with the matching pincode
        print("Waiting for dropdown item to appear...")
        dropdown_item = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located(
                (By.XPATH, f"//p[@class='item-name text-dark mb-0 fw-semibold fs-6' and text()='{pincode}']")
            )
        )
        print("Dropdown item found:", dropdown_item.text)

        # Click the dropdown item
        dropdown_item.click()
        print("Dropdown item clicked.")
        time.sleep(1)
        return True

    except Exception as e:
        print("Could not automate pincode entry:", e)
        return False

def send_email(subject, body, recipient_email):
    sender_email = EMAIL_ADDRESS
    app_password = EMAIL_PASSWORD

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = recipient_email

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(sender_email, app_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())
    print(f"Alert email sent to {recipient_email}")

def main():
    url, alert_type, price_threshold, email = get_user_input()
    sent = False

    # --- Setup Selenium driver ---
    options = Options()
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument("--headless=new")
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
    driver = webdriver.Chrome(options=options)

    try:
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
                        price_num = float(price_str.replace('₹', '').replace(',', '').strip())
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
            time.sleep(3600)  # Sleep  hours

    except KeyboardInterrupt:
        print("\nStopped by user. Exiting gracefully.")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()

