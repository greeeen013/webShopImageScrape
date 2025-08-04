from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
from selenium.webdriver.common.keys import Keys
uc.Chrome.__del__ = lambda self: None
from webdriver_manager.chrome import ChromeDriverManager
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


async def notebooksbilliger_get_product_images(PNumber):
    encoded = urllib.parse.quote(urllib.parse.quote(PNumber, safe=''))
    url = f"https://www.notebooksbilliger.de/produkte/{encoded}"
    logger.debug(f"Navigating to {url}")

    chrome_options = Options()
    chrome_options.page_load_strategy = "eager"
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.199 Safari/537.36"
    )

    driver = uc.Chrome(options=chrome_options)
    try:
        driver.get(url)

        # Přímé hledání produktu bez pokusů o cookie bannery
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

        # Přejdeme na detail produktu
        driver.get(product_link)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "ul.image-modal__main-image-list"))
        )

        image_elements = driver.find_elements(
            By.CSS_SELECTOR,
            "ul.image-modal__main-image-list li img.image-modal__main-image"
        )
        image_urls = [img.get_attribute("src") for img in image_elements if img.get_attribute("src")]
        logger.debug(f"Found {len(image_urls)} product images")

        return image_urls

    except Exception as e:
        logger.error(f"Error in notebooksbilliger_get_product_images: {str(e)}", exc_info=True)
        try:
            driver.save_screenshot("debug.png")
            logger.debug("Saved screenshot to debug.png")
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
    chrome_options = Options()

    load_dotenv()
    login = os.getenv("FOURCOM_LOGIN")
    password = os.getenv("FOURCOM_PASSWORD")

    # Základní nastavení prohlížeče
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")

    # Nastavení proti detekci
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    # User-agents a další nastavení
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0"
    ]
    chrome_options.add_argument(f"user-agent={random.choice(user_agents)}")
    chrome_options.add_argument("--lang=en-GB")
    chrome_options.add_argument("--accept-language=en-GB,en;q=0.9")

    driver = None
    try:
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
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

        # 1. Přihlášení na stránku
        login_url = "https://en.fourcom.dk"
        logger.debug(f"Opening login page: {login_url}")
        driver.get(login_url)

        # Accept first cookies
        try:
            cookie_accept = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable((By.ID, "cookiescript_accept"))
            )
            cookie_accept.click()
            logger.debug("Accepted first cookies")
        except Exception as e:
            logger.warning(f"Could not accept first cookies: {str(e)}")

        # Vyplnění přihlašovacích údajů
        customer_number_field = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "form-field-kundenummer"))
        )
        customer_number_field.send_keys(login)

        password_field = driver.find_element(By.ID, "form-field-password")

        password_field.send_keys(password)
        try:
            cookie_accept = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.ID, "cookiescript_accept"))
            )
            cookie_accept.click()
            logger.debug("Accepted second cookies")
        except Exception as e:
            logger.debug("No second cookies to accept")

        # Kliknutí na přihlášení
        login_button = driver.find_element(By.CSS_SELECTOR, "button.elementor-button[type='submit']")
        login_button.click()
        logger.debug("Login submitted")

        # 2. Vyhledání produktu
        search_input = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='ItemSearchPage-text']"))
        )

        # Accept cookies again before searching
        try:
            cookie_accept = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.ID, "cookiescript_accept"))
            )
            cookie_accept.click()
            logger.debug("Accepted cookies before search")
        except Exception as e:
            logger.debug("No cookies to accept before search")

        # Zadávání textu
        search_input.send_keys(PNumber)

        # Wait for search suggestions to appear
        try:
            # Wait for the suggestions container to be visible
            WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "div.simple-autosuggester-items"))
            )

            # Find the suggestion that matches our product number
            suggestion_item = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH,
                                        f"//div[contains(@class, 'simple-autosuggester-items-item')]//em[text()='{PNumber}']/ancestor::a"))
            )

            # Click on the suggestion
            suggestion_item.click()
            logger.debug("Clicked on search suggestion")

        except Exception as e:
            logger.error(f"Could not find or click search suggestion for {PNumber}: {str(e)}")
            try:
                logger.debug(f"Current URL: {driver.current_url}")
                logger.debug("Page source (first 3000 chars):\n" + driver.page_source[:3000])
            except:
                pass
            return []

        # 3. Získání obrázků produktu
        image_urls = []

        # Čekání na načtení galerie s delším timeoutem
        try:
            WebDriverWait(driver, 25).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.thumbs a[data-fancybox='gallery']"))
            )
        except Exception as e:
            logger.warning(f"Gallery not found: {str(e)}")
            # Zkusíme alternativní přístup - možná je produkt na stránce, ale galerie se nenačetla
            try:
                product_container = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, f"div[data-itemnumber='{PNumber}']"))
                )
                logger.debug("Found product container, trying alternative image extraction")
            except:
                logger.debug("Page structure:\n" + driver.page_source[:3000])
                return []

        # Extrakce obrázků z galerie
        gallery_links = driver.find_elements(By.CSS_SELECTOR, "div.thumbs a[data-fancybox='gallery']")

        for link in gallery_links:
            img_url = link.get_attribute("href")
            if img_url:
                # Doplnění domény pokud chybí
                if img_url.startswith("/"):
                    img_url = f"https://en.fourcom.dk{img_url}"
                image_urls.append(img_url)
                logger.debug(f"Found product image: {img_url}")

        # Alternativní metoda, pokud galerie není nalezena
        if not image_urls:
            logger.debug("Trying alternative image search...")
            product_images = driver.find_elements(By.CSS_SELECTOR, "div.itemBoxImages img, div.itemBoxImage img")
            for img in product_images:
                img_url = img.get_attribute("src")
                if img_url and "upload/cnet" in img_url:
                    if img_url.startswith("/"):
                        img_url = f"https://en.fourcom.dk{img_url}"
                    if img_url not in image_urls:
                        image_urls.append(img_url)
                        logger.debug(f"Found alternative image: {img_url}")

        logger.debug(f"Found {len(image_urls)} images for product {PNumber}")
        return image_urls

    except Exception as e:
        logger.error(f"Error in fourcom_get_product_images: {str(e)}", exc_info=True)
        try:
            logger.debug(f"Current URL: {driver.current_url}")
            logger.debug("Page source (first 3000 chars):\n" + driver.page_source[:3000])
        except:
            pass
        return []
    finally:
        if driver:
            driver.quit()


async def komputronik_get_product_images(PNumber):
    chrome_options = Options()
    chrome_options.page_load_strategy = "eager"
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.199 Safari/537.36"
    )
    #chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")

    driver = uc.Chrome(options=chrome_options)
    try:
        # 1. Přihlášení
        login_url = "https://b2b.komputronik.eu/customer/login"
        logger.debug(f"Navigating to login page: {login_url}")
        driver.get(login_url)

        load_dotenv()  # Načte proměnné z .env souboru

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
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='Enter what you are looking for']"))
        )

        search_input = driver.find_element(
            By.CSS_SELECTOR, "input[placeholder='Enter what you are looking for']"
        )
        search_input.send_keys(PNumber)
        search_input.send_keys(Keys.RETURN)
        logger.debug(f"Searching for product: {PNumber}")

        # 3. Zpracování výsledků vyhledávání
        try:
            # Čekáme na načtení produktové stránky
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "img[ktr-lazy-image]"))
            )
        except Exception as e:
            logger.error(f"Product page not loaded: {str(e)}")
            try:
                driver.save_screenshot("komputronik_search_error.png")
                logger.debug("Saved screenshot to komputronik_search_error.png")
            except:
                pass
            return []

        # 4. Získání obrázků
        image_urls = []
        collected_urls = set()
        max_images = 20  # Bezpečnostní limit

        try:
            # Najít první obrázek
            first_img = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "img[ktr-lazy-image]"))
            )
            first_url = first_img.get_attribute("src")

            if first_url:
                image_urls.append(first_url)
                collected_urls.add(first_url)
                logger.debug(f"Found initial image: {first_url}")

            # Pokus najít tlačítko pro další obrázek
            try:
                next_btn = driver.find_element(By.CSS_SELECTOR, "button.nav-right.screen-only")

                # Procházení galerie
                for _ in range(max_images):
                    try:
                        next_btn.click()
                        time.sleep(1)  # Krátká pauza pro načtení

                        # Získat aktuální obrázek
                        current_img = WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "img[ktr-lazy-image]"))
                        )
                        img_url = current_img.get_attribute("src")

                        # Kontrola konce galerie nebo duplicity
                        if not img_url or img_url in collected_urls:
                            break

                        image_urls.append(img_url)
                        collected_urls.add(img_url)
                        logger.debug(f"Found image: {img_url}")

                    except Exception as e:
                        logger.warning(f"Could not navigate to next image: {str(e)}")
                        break
            except Exception as e:
                logger.warning(f"Next button not found, using single image: {str(e)}")

        except Exception as e:
            logger.error(f"Error getting images: {str(e)}")
            try:
                driver.save_screenshot("komputronik_images_error.png")
                logger.debug("Saved screenshot to komputronik_images_error.png")
            except:
                pass

        logger.debug(f"Found {len(image_urls)} images for product {PNumber}")
        return image_urls

    except Exception as e:
        logger.error(f"Error in komputronik_get_product_images: {str(e)}", exc_info=True)
        try:
            driver.save_screenshot("komputronik_debug.png")
            logger.debug("Saved screenshot to komputronik_debug.png")
        except:
            pass
        return []
    finally:
        try:
            driver.quit()
        except:
            pass


# Testovací kód
if __name__ == "__main__":
    import asyncio

    # Původní test
    # print("Testing Notebooksbilliger...")
    # images = asyncio.run(notebooksbilliger_get_product_images("a 455306"))
    # print(images)

    print("\nTesting Komputronik...")
    komputronik_images = asyncio.run(komputronik_get_product_images("MOD-PHA-047"))
    print(komputronik_images)

    # Nový test pro Fourcom
    # print("\nTesting Fourcom...")
    # fourcom_images = asyncio.run(fourcom_get_product_images("PB5W0001SE"))
    # print(fourcom_images)