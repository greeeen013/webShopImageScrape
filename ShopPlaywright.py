import re
from urllib.parse import urljoin
from playwright.sync_api import Playwright, sync_playwright
from dotenv import load_dotenv
import os


def comline_get_product_images(playwright: Playwright, product_code: str) -> list[str]:
    """
    Získá URL obrázků produktu z Comline shopu.

    Args:
        playwright: Playwright instance
        product_code: Kód produktu (např. "PWAZ-5000012")

    Returns:
        List URL adres obrázků produktu
    """
    # Načtení přihlašovacích údajů z .env
    load_dotenv()
    email = os.getenv("COMLINE_EMAIL")
    password = os.getenv("COMLINE_PASSWORD")

    if not email or not password:
        raise ValueError("COMLINE_EMAIL a COMLINE_PASSWORD musí být nastaveny v .env souboru")

    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    try:
        # Přihlášení
        page.goto("https://shop.comline-shop.de/static/login.htm")
        page.get_by_role("button", name="Allow all").click()
        page.locator("input[name=\"font1\"]").fill(email)
        page.locator("input[name=\"font2\"]").fill(password)
        page.get_by_role("button", name="Anmelden").click()

        # Vyhledání produktu
        page.get_by_role("textbox", name="Suche nach…").fill(product_code)
        page.get_by_role("search").get_by_role("button").filter(has_text=re.compile(r"^$")).click()

        # Kliknutí na první výsledek (můžete upravit podle potřeby)
        page.get_by_role("textbox", name="Suche nach…").fill(product_code)
        page.get_by_role("search").get_by_role("button").filter(has_text=re.compile(r"^$")).click()

        # Kliknutí na link produktu - použít váš původní selektor
        page.locator(f"a[href='/art/{product_code}']").first.click()

        # Počkání na načtení obrázků
        page.wait_for_selector(".artikel-bild-nav img[alt='produktbild']")

        # Získání URL obrázků
        image_urls = []
        for i in range(1, 5):
            try:
                img = page.get_by_role("img", name="produktbild").nth(i)
                url = img.get_attribute("href")

                # Přidání https: pokud URL začíná //
                if url and url.startswith("//"):
                    url = "https:" + url

                if url:
                    image_urls.append(url)
                    print(f"Obrázek {i}: {url}")
            except Exception as e:
                print(f"Nepodařilo se získat obrázek {i}: {e}")
                break

        return image_urls

    finally:
        context.close()
        browser.close()



with sync_playwright() as playwright:
    comline_get_product_images(playwright, "PWAZ-5000012")
