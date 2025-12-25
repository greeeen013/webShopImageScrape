from playwright.sync_api import sync_playwright
import os
import re
from dotenv import load_dotenv
from .base_scraper import BaseScraper
from urllib.parse import urljoin

class ComLineScraper(BaseScraper):
    def get_product_images(self, product_code: str) -> list[str]:
        load_dotenv()
        email = os.getenv("COMLINE_EMAIL")
        password = os.getenv("COMLINE_PASSWORD")
        if not email or not password: return []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True) # Changed to True for bg processing
            context = browser.new_context()
            page = context.new_page()
            try:
                page.goto("https://shop.comline-shop.de/static/login.htm")
                try: page.get_by_role("button", name="Allow all").click(timeout=3000)
                except: pass
                
                page.locator("input[name=\"font1\"]").fill(email)
                page.locator("input[name=\"font2\"]").fill(password)
                page.get_by_role("button", name="Anmelden").click()
                
                # Search
                page.get_by_role("textbox", name="Suche nach…").fill(product_code)
                page.get_by_role("search").get_by_role("button").filter(has_text=re.compile(r"^$")).click()
                
                page.locator(f"a[href='/art/{product_code}']").first.click(timeout=5000)
                page.wait_for_selector(".artikel-bild-nav img[alt='produktbild']", timeout=5000)
                
                urls = []
                for i in range(1, 5):
                    try:
                        img = page.get_by_role("img", name="produktbild").nth(i)
                        url = img.get_attribute("href")
                        if url:
                            if url.startswith("//"): url = "https:" + url
                            urls.append(url)
                    except: break
                return urls
            except Exception:
                return []
            finally:
                browser.close()

class CyberportScraper(BaseScraper):
    def get_product_images(self, product_code: str) -> list[str]:
        # TODO: Implement Cyberport scraper. ID 177521.
        # User did not provide explicit logic, only ID.
        # Assuming Playwright needed.
        return []
