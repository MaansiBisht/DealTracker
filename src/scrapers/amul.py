import time
from bs4 import BeautifulSoup
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from ..config import PINCODE


def enter_pincode(driver, pincode):
    try:
        print("Waiting for pincode overlay to appear...")
        WebDriverWait(driver, 15).until(
            EC.visibility_of_element_located((By.ID, "search"))
        )

        inputs = driver.find_elements(By.ID, "search")
        pincode_input = None
        for inp in inputs:
            if inp.is_displayed() and inp.is_enabled():
                pincode_input = inp
                break

        if not pincode_input:
            print("No interactable pincode input found.")
            return False

        driver.execute_script("arguments[0].scrollIntoView(true);", pincode_input)
        time.sleep(0.5)

        pincode_input.clear()
        pincode_input.send_keys(pincode)
        print(f"Pincode '{pincode}' entered.")

        print("Waiting for dropdown item to appear...")
        dropdown_item = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located(
                (By.XPATH, f"//p[@class='item-name text-dark mb-0 fw-semibold fs-6' and text()='{pincode}']")
            )
        )
        print("Dropdown item found:", dropdown_item.text)

        dropdown_item.click()
        print("Dropdown item clicked.")
        time.sleep(1)
        return True

    except Exception as e:
        print("Could not automate pincode entry:", e)
        return False


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
