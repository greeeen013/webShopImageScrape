from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
from selenium.webdriver.common.keys import Keys

uc.Chrome.__del__ = lambda self: None

import time
import logging
from selenium.webdriver.common.action_chains import ActionChains
import random
import os
from dotenv import load_dotenv
import urllib.parse
from urllib.parse import urljoin

# Nastavení podrobného logování
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(levelname)s] %(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def get_chrome_driver(headless=False):
    """Vytvoří Chrome driver s automatickou detekcí verze Chrome"""
    chrome_options = uc.ChromeOptions()
    chrome_options.page_load_strategy = "eager"
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--window-size=1920,1080")

    if headless:
        chrome_options.add_argument("--headless=new")

    # Automatická detekce a použití správné verze ChromeDriveru
    driver = uc.Chrome(
        options=chrome_options,
        use_subprocess=True,
        version_main=None  # Automaticky detekuje verzi Chrome
    )

    # Skrytí automatizace
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
        """
    })

    return driver

async def notebooksbilliger_get_product_images(PNumber):
    import urllib.parse
    encoded = urllib.parse.quote(urllib.parse.quote(PNumber, safe=''))
    url = f"https://www.notebooksbilliger.de/produkte/{encoded}"
    logger.debug(f"Navigating to {url}")

    chrome_options = Options()
    chrome_options.page_load_strategy = "eager"
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.199 Safari/537.36"
    )

    driver = uc.Chrome(options=chrome_options)
    try:
        driver.get(url)

        # Najdi produkt kartu
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.product-card"))
        )
        product_card = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH,
                f"//div[contains(translate(@data-product-article-number, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{PNumber.lower()}')]"))
        )
        product_link = product_card.find_element(
            By.CSS_SELECTOR, "a.product-card__link"
        ).get_attribute("href")
        logger.debug(f"Found product link: {product_link}")

        # Přejdi na detail produktu
        driver.get(product_link)

        # Čekej na slider s obrázky
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "js-pdp-big-image-list"))
        )

        # Získej všechny <img> z hlavního seznamu
        image_elements = driver.find_elements(
            By.CSS_SELECTOR,
            "#js-pdp-big-image-list img"
        )
        image_urls = [
            img.get_attribute("src")
            for img in image_elements
            if img.get_attribute("src")
        ]

        logger.debug(f"Found {len(image_urls)} product images")
        return image_urls

    except Exception as e:
        logger.error(f"Error in notebooksbilliger_get_product_images: {str(e)}", exc_info=True)
        try:
            driver.save_screenshot("debug_notebooksbilliger.png")
            logger.debug("Saved screenshot to debug_notebooksbilliger.png")
            logger.debug(f"Current page source (first 2000 chars):\n{driver.page_source[:2000]}")
        except:
            pass
        return []
    finally:
        try:
            driver.quit()
        except:
            pass


async def fourcom_get_product_images(PNumber):
    """
    Přihlásí se na fourcom.dk, vyhledá PNumber, v listu najde položku,
    kde v <div class="itemnumber"> je 'Fourcom varenr: {PNumber}',
    přejde na produkt a vrátí absolutní URL obrázků (z galerie nebo z big-image).
    """
    BASE = "https://en.fourcom.dk"
    driver = get_chrome_driver()
    try:
        load_dotenv()
        user = os.getenv("FOURCOM_LOGIN")
        pwd  = os.getenv("FOURCOM_PASSWORD")
        if not user or not pwd:
            logger.error("Fourcom credentials not found in .env")
            return []

        # 1) login
        driver.get(BASE)
        WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input#form-field-kundenummer"))
        ).send_keys(user)
        driver.find_element(By.CSS_SELECTOR, "input#form-field-password").send_keys(pwd)
        driver.find_element(By.CSS_SELECTOR, "button.elementor-button[type='submit']").click()

        # 2) search
        WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='ItemSearchPage-text']"))
        )
        search = driver.find_element(By.CSS_SELECTOR, "input[name='ItemSearchPage-text']")
        search.clear()
        search.send_keys(PNumber)
        search.send_keys(Keys.RETURN)

        # 3) výsledky – najdi správný thumb-item podle "Fourcom varenr"
        items = WebDriverWait(driver, 20).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.thumb-item"))
        )

        target = None
        for it in items:
            # pro jistotu projdeme všechny <div class="itemnumber">
            for n in it.find_elements(By.CSS_SELECTOR, "div.itemnumber"):
                txt = (n.text or "").strip().replace("\xa0", " ")
                if "Fourcom varenr:" in txt:
                    val = "".join(ch for ch in txt.split(":", 1)[1] if ch.isdigit())
                    if val == str(PNumber):
                        target = it
                        break
            if target:
                break

        if not target:
            logger.debug(f"Fourcom: {PNumber} nenalezen ve výsledcích podle 'Fourcom varenr'")
            return []

        # 4) klik na správný produkt
        try:
            click_el = target.find_element(By.CSS_SELECTOR, "div.ajax-load-product")
        except Exception:
            click_el = target.find_element(By.CSS_SELECTOR, "h3.itemname.ajax-load-product")
        driver.execute_script("arguments[0].click();", click_el)

        # 5) počkej na detail – buď je tam galerie (div.thumbs) nebo jen big-image
        WebDriverWait(driver, 20).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, "div.thumbs a[data-fancybox='gallery']") or
                      d.find_elements(By.CSS_SELECTOR, "div.big-image a[data-fancybox='gallery']")
        )

        # 6) seber hrefy – priorita: galerie, jinak big-image
        links = driver.find_elements(By.CSS_SELECTOR, "div.thumbs a[data-fancybox='gallery']")
        if not links:
            links = driver.find_elements(By.CSS_SELECTOR, "div.big-image a[data-fancybox='gallery']")

        image_urls = [
            urljoin(BASE, a.get_attribute("href"))
            for a in links
            if a.get_attribute("href")
        ]

        return image_urls

    except Exception as e:
        logger.error(f"fourcom_get_product_images error: {e}", exc_info=True)
        return []
    finally:
        # vždy ukončit prohlížeč
        try:
            driver.quit()
        except Exception:
            pass

async def komputronik_get_product_images(PNumber):
    driver = get_chrome_driver()
    try:
        load_dotenv()

        # 1. Přihlášení
        login_url = "https://b2b.komputronik.eu/customer/login"
        logger.debug(f"Navigating to login page: {login_url}")
        driver.get(login_url)

        # Vyplnění přihlašovacích údajů
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='custom_identify']"))
        ).send_keys(os.getenv("KOMPUTRONIK_LOGIN"))

        driver.find_element(
            By.CSS_SELECTOR, "input[name='customer_password']"
        ).send_keys(os.getenv("KOMPUTRONIK_PASSWORD"))

        # Kliknutí na přihlášení
        driver.find_element(
            By.CSS_SELECTOR, "button.tfg-actions__sign-in"
        ).click()
        logger.debug("Login submitted")

        # 2. Vyhledání produktu
        search_input = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='Enter what you are looking for']"))
        )
        search_input.send_keys(PNumber)
        search_input.send_keys(Keys.RETURN)
        logger.debug(f"Searching for product: {PNumber}")

        # 3. Získání obrázků z galerie
        image_urls = []
        max_images = 20  # Bezpečnostní limit
        collected_urls = set()

        try:
            # Čekáme na načtení galerie
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "img[ng-src][src]"))
            )

            # Najdeme šipku pro další obrázek
            next_btn = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "button.nav-right.screen-only"))
            )

            # Procházíme galerii
            for _ in range(max_images):
                # Najdeme aktuální obrázek
                current_img = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "img[ng-src][src]"))
                )
                img_url = current_img.get_attribute("src")

                # Kontrola duplicity
                if not img_url or img_url in collected_urls:
                    break

                image_urls.append(img_url)
                collected_urls.add(img_url)
                logger.debug(f"Found image: {img_url}")

                # Klik na další obrázek
                try:
                    next_btn.click()
                    time.sleep(0.5)  # Krátká pauza pro načtení
                except:
                    break  # Pokud nelze kliknout, ukončíme

        except Exception as e:
            logger.error(f"Error navigating gallery: {str(e)}")
            try:
                driver.save_screenshot("komputronik_gallery_error.png")
            except:
                pass

        logger.debug(f"Found {len(image_urls)} images for product {PNumber}")
        return image_urls

    except Exception as e:
        logger.error(f"Error in komputronik_get_product_images: {str(e)}", exc_info=True)
        return []
    finally:
        try:
            driver.quit()
        except:
            pass


if __name__ == "__main__":
    import asyncio

    #print(asyncio.run(notebooksbilliger_get_product_images("A1064333")))
    #print(asyncio.run(komputronik_get_product_images("MOD-PHA-047")))
    print(asyncio.run(fourcom_get_product_images("532754")))