"""Drive the ops console with Playwright and capture a video.

Run:
    .venv/bin/python scripts/record_demo.py

Produces ./screencast/_raw/<random>.webm. The shell wrapper next to
this file converts the webm to an optimized GIF at
./screencast/dealtracker-console.gif.

Assumes the container is running on http://localhost:8000.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "screencast" / "_raw"
TARGET_URL = "http://localhost:8000"
VIEWPORT = {"width": 1280, "height": 760}


def slow_type(page, selector: str, text: str, per_char_ms: int = 35) -> None:
    page.locator(selector).click()
    page.locator(selector).press_sequentially(text, delay=per_char_ms)


def main() -> None:
    if RAW_DIR.exists():
        shutil.rmtree(RAW_DIR)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            viewport=VIEWPORT,
            record_video_dir=str(RAW_DIR),
            record_video_size=VIEWPORT,
            color_scheme="dark",
            device_scale_factor=2,
        )
        page = context.new_page()

        # SSE keeps a connection open forever, so 'networkidle' never fires.
        page.goto(TARGET_URL, wait_until="domcontentloaded")
        page.wait_for_selector("text=DEALTRACKER", timeout=10_000)
        time.sleep(1.6)

        slow_type(page, 'input[placeholder^="https://www.amazon"]',
                  "https://www.amazon.in/dp/B08BPQ9CZ1")
        time.sleep(0.4)
        slow_type(page, 'input[placeholder*="@example.com"]', "you@example.com")
        time.sleep(0.4)

        page.locator('select').first.select_option("price")
        time.sleep(0.5)

        slow_type(page, 'input[placeholder^="₹ amount"]', "1000", per_char_ms=80)
        time.sleep(0.6)

        page.get_by_role("button", name="START", exact=False).click()
        time.sleep(2.5)

        page.wait_for_selector("text=tick start", timeout=45_000)
        time.sleep(2.2)
        page.wait_for_selector("text=stock=in stock", timeout=60_000)
        time.sleep(2.0)

        page.get_by_role("button", name="hotels").click()
        time.sleep(2.0)

        page.get_by_role("button", name="products").click()
        time.sleep(2.0)

        context.close()
        browser.close()

    videos = sorted(RAW_DIR.glob("*.webm"))
    if not videos:
        raise SystemExit("no video produced")
    print(videos[-1])


if __name__ == "__main__":
    main()
