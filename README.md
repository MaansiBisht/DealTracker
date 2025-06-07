# DealTracker
DealTracker is a Python script that monitors products on Amul, Myntra, Amazon, and Flipkart, sending direct email alerts when items are back in stock or when prices drop below your set threshold. This tool automates deal and restock tracking, so you never miss an update.

## Features

- **Stock Alerts:** Get notified when a product is back in stock.
- **Price Alerts:** Receive emails when a product’s price drops below your specified value.
- **Multi-Site Support:** Works with Amul, Myntra, Amazon, and Flipkart.
- **Automated Email Notifications:** Direct alerts sent to your inbox.
- **Customizable Monitoring:** Easily set your own products and price thresholds.

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
      EMAIL_USER=your_email@example.com
      EMAIL_PASS=your_password
      ```

5. **Run the script:**
    ```
    python Alerts.py
    ```
    
4. **Enter product details and thresholds via CLI:**
    - When you run the script, you will be prompted in the terminal to enter the product URLs, desired alert prices, and other relevant details for monitoring.

## Notes

- Make sure you have [ChromeDriver](https://sites.google.com/chromium.org/driver/) installed and available in your PATH for Selenium to work.
- This script is for personal use and educational purposes. Please respect the terms of service of the websites you monitor.

![Demo](/screencast/productAlerts.gif)
