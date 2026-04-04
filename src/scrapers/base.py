import time
from bs4 import BeautifulSoup


def get_soup(driver, url, wait_time=10):
    """Load URL and return BeautifulSoup object."""
    driver.get(url)
    time.sleep(wait_time)
    return BeautifulSoup(driver.page_source, 'html.parser')
