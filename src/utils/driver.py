from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def create_driver(headless: bool = True):
    """
    Selenium Chrome driver tuned to avoid the most common headless
    bot-detection signals (matters for Flipkart, Amul, Booking.com etc.).
    Set headless=False if a target site still redirects/blocks the headless run.
    """
    options = Options()
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1366,900')
    if headless:
        options.add_argument('--headless=new')
    # Stealth flags
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument(
        '--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36'
    )
    driver = webdriver.Chrome(options=options)
    # Mask navigator.webdriver
    driver.execute_cdp_cmd(
        'Page.addScriptToEvaluateOnNewDocument',
        {'source': "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"},
    )
    return driver
