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
    """Získává obrázky produktů z fourcom.dk pro zadané PNumber"""
    driver = get_chrome_driver()
    try:
        load_dotenv()
        FOURCOM_LOGIN = os.getenv("FOURCOM_LOGIN")
        FOURCOM_PASSWORD = os.getenv("FOURCOM_PASSWORD")

        if not FOURCOM_LOGIN or not FOURCOM_PASSWORD:
            logger.error("FourCom credentials not found in .env file")
            return []

        # 1. Navigace na hlavní stránku
        logger.debug("Navigating to https://en.fourcom.dk")
        driver.get("https://en.fourcom.dk")

        # 2. Přihlášení
        logger.debug("Filling login form")
        WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input#form-field-kundenummer"))
        ).send_keys(FOURCOM_LOGIN)

        driver.find_element(
            By.CSS_SELECTOR, "input#form-field-password"
        ).send_keys(FOURCOM_PASSWORD)

        driver.find_element(
            By.CSS_SELECTOR, "button.elementor-button[type='submit']"
        ).click()
        logger.debug("Login submitted")

        # 3. Vyhledávání produktu
        logger.debug(f"Searching for product: {PNumber}")
        search_input = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='ItemSearchPage-text']"))
        )
        search_input.clear()
        search_input.send_keys(PNumber)
        search_input.send_keys(Keys.RETURN)
        logger.debug("Search submitted with Enter key")

        # 4. Čekání na výsledky vyhledávání a kliknutí na první produkt
        logger.debug("Waiting for search results and clicking first product")
        first_product = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "div.thumb-item div.ajax-load-product"))
        )

        # Klik na produkt pomocí JavaScriptu pro větší spolehlivost
        driver.execute_script("arguments[0].click();", first_product)
        logger.debug("First product clicked")

        # 5. Čekání na načtení detailu produktu
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.thumbs, div.product-item"))
        )

        # 6. Získání obrázků z galerie - PRVNÍ METODA (standardní)
        logger.debug("Extracting product images - trying primary method")
        image_urls = []
        try:
            gallery = driver.find_element(By.CSS_SELECTOR, "div.thumbs")
            image_links = gallery.find_elements(By.CSS_SELECTOR, "a[data-fancybox='gallery']")
            image_urls = [link.get_attribute("href") for link in image_links]
            logger.debug(f"Primary method found {len(image_urls)} images")
        except Exception as e:
            logger.debug(f"Primary image extraction failed: {str(e)}")

        # 7. Získání obrázků - DRUHÁ METODA (alternativní)
        if not image_urls:
            logger.debug("Trying alternative image source from itemBoxImages")
            try:
                image_container = driver.find_element(By.CSS_SELECTOR, "div.itemBoxImages")
                image_divs = image_container.find_elements(By.CSS_SELECTOR, "div[data-src]")
                image_urls = [div.get_attribute("data-src") for div in image_divs]
                logger.debug(f"Alternative method found {len(image_urls)} images")
            except Exception as e:
                logger.debug(f"Alternative image extraction failed: {str(e)}")

        # 8. Získání obrázků - TŘETÍ METODA (nová struktura)
        if not image_urls:
            logger.debug("Trying fallback method for new product structure")
            try:
                product_container = driver.find_element(By.CSS_SELECTOR, "div.product-item")

                # Získání hlavního obrázku
                main_image = product_container.find_element(
                    By.CSS_SELECTOR, "div.big-image a[data-fancybox='gallery']"
                )
                image_urls.append(main_image.get_attribute("href"))

                # Získání dalších obrázků z galerie (pokud existují)
                thumb_images = product_container.find_elements(
                    By.CSS_SELECTOR, "div.thumbnails a[data-fancybox='gallery']"
                )
                image_urls.extend([img.get_attribute("href") for img in thumb_images])

                logger.debug(f"Fallback method found {len(image_urls)} images")
            except Exception as e:
                logger.debug(f"Fallback image extraction failed: {str(e)}")

        if image_urls:
            logger.debug(f"Total images found: {len(image_urls)}")
        else:
            logger.debug("No images found with any method")

        return image_urls

    except Exception as e:
        logger.error(f"Error in fourcom_get_product_images: {str(e)}", exc_info=True)
        try:
            driver.save_screenshot("fourcom_debug.png")
            logger.debug("Saved screenshot to fourcom_debug.png")
            logger.debug(f"Current page source (first 2000 chars):\n{driver.page_source[:2000]}")
        except:
            pass
        return []
    finally:
        try:
            driver.quit()
        except:
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
    print(asyncio.run(fourcom_get_product_images("440386")))