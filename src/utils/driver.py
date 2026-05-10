import os

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


def create_driver(headless: bool = True):
    """
    Selenium Chrome driver tuned to avoid the most common headless
    bot-detection signals (matters for Flipkart, Amul, Booking.com etc.).

    Honors two env vars so the same code runs on macOS dev (Selenium Manager
    auto-downloads chromedriver) and in Docker (chromium + chromium-driver
    are pre-installed via apt; both paths are exported by the image):

        CHROME_BIN          path to chromium/chrome binary
        CHROMEDRIVER_PATH   path to a matching chromedriver
    """
    options = Options()
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1366,900')
    if headless:
        options.add_argument('--headless=new')

    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument(
        '--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36'
    )

    chrome_bin = os.getenv('CHROME_BIN')
    if chrome_bin:
        options.binary_location = chrome_bin

    chromedriver_path = os.getenv('CHROMEDRIVER_PATH')
    if chromedriver_path:
        driver = webdriver.Chrome(
            options=options,
            service=Service(executable_path=chromedriver_path),
        )
    else:
        driver = webdriver.Chrome(options=options)

    driver.execute_cdp_cmd(
        'Page.addScriptToEvaluateOnNewDocument',
        {'source': "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"},
    )
    return driver
