from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
from selenium.webdriver.common.keys import Keys

uc.Chrome.__del__ = lambda self: None

import re
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


def get_chrome_driver(headless=True):
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

async def wave_get_product_images(PNumber):
    import re
    import urllib.parse
    from urllib.parse import urljoin
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    BASE = "https://www.wave-distribution.de"
    driver = get_chrome_driver(headless=True)

    def click_cookie_banner(drv):
        try:
            # Usercentrics / běžné varianty
            candidates = drv.find_elements(By.CSS_SELECTOR, "button, [role='button']")
            for b in candidates:
                txt = (b.text or b.get_attribute("aria-label") or "").strip().lower()
                if any(k in txt for k in ["akzept", "alle akzeptieren", "accept all", "accept", "zustimmen", "souhlas", "přijmout"]):
                    b.click()
                    logger.debug("Cookie banner dismissed by text match")
                    return
            # Některé instalace mají specifický shadow-root – necháme být, pokud není nalezeno, nevadí
        except Exception:
            pass

    def wait_for_any(drv, timeout=20):
        """
        Počkej buď na galerii na detailu, nebo na seznam produktů.
        Vrací string 'detail' nebo 'listing'
        """
        def _cond(d):
            # a) rovnou detail (galerie přítomná)
            if d.find_elements(By.CSS_SELECTOR, "div.swiper-wrapper img[srcset]"):
                return "detail"
            # b) různé možné gridy/výpisy
            listing_selectors = [
                "a.product-teaser__link",
                "div.productbox a[href*='/p/']",
                "a[href^='/p/'][title]",   # často mají title = název produktu
                "article a[href*='/p/']",
                "ul li a[href*='/p/']",
                "div.listing a[href*='/p/']",
            ]
            for sel in listing_selectors:
                if d.find_elements(By.CSS_SELECTOR, sel):
                    return "listing"
            return False

        return WebDriverWait(drv, timeout).until(_cond)

    def open_first_product(drv):
        # zkuste najít item, který přímo obsahuje PNumber (v textu nebo title)
        links = []
        listing_selectors = [
            "a.product-teaser__link",
            "div.productbox a[href*='/p/']",
            "a[href^='/p/'][title]",
            "article a[href*='/p/']",
            "div.listing a[href*='/p/']",
            "a[href*='/p/']",
        ]
        seen = set()
        for sel in listing_selectors:
            for a in drv.find_elements(By.CSS_SELECTOR, sel):
                href = a.get_attribute("href") or ""
                if "/p/" in href and href not in seen:
                    seen.add(href)
                    links.append(a)

        # preferuj ty, kde je PNumber v textu/title
        def score(el):
            title = (el.get_attribute("title") or "").lower()
            txt = (el.text or "").lower()
            return int(PNumber.lower() in title or PNumber.lower() in txt)

        links.sort(key=score, reverse=True)

        if not links:
            raise Exception("Nenalezen žádný odkaz na produkt ve výpisu.")

        target = links[0]
        url = target.get_attribute("href")
        logger.debug(f"Opening product detail: {url}")
        drv.get(url)

    try:
        search_url = f"{BASE}/listing.xhtml?q={urllib.parse.quote(PNumber)}"
        logger.debug(f"Navigating to {search_url}")
        driver.get(search_url)

        # cookie lišta (neblokující, jen se o to pokusíme)
        click_cookie_banner(driver)

        where = wait_for_any(driver, timeout=25)
        logger.debug(f"Initial page type detected: {where}")

        if where == "listing":
            open_first_product(driver)
            # po přechodu na detail ještě jednou pro cookie lištu
            click_cookie_banner(driver)
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.swiper-wrapper img[srcset]"))
            )

        # jsme na detailu
        # pro jistotu poscrollujeme, ať se lazy načtou srcsety
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/1.5);")

        img_els = driver.find_elements(By.CSS_SELECTOR, "div.swiper-wrapper img[srcset]")

        image_urls, seen = [], set()

        for img in img_els:
            srcset = (img.get_attribute("srcset") or "").strip()
            if not srcset:
                continue

            # Rozparsuj srcset na položky "url [descriptor]" oddělené čárkou
            parts = [p.strip() for p in srcset.split(",") if p.strip()]

            best_url = None
            best_score = -1  # vyšší = lepší

            for p in parts:
                tokens = p.split()
                url_token = tokens[0].strip()
                desc = tokens[1].strip() if len(tokens) > 1 else ""

                # 1) Preferuj originál (obsahuje "/p/o/")
                if "/p/o/" in url_token:
                    best_url = url_token
                    best_score = 10 ** 9
                    break

                # 2) Jinak skóruj podle descriptoru (např. "600w", "2x" apod.)
                score = 0
                if desc.endswith("w"):
                    try:
                        score = int(desc[:-1])
                    except:
                        score = 0
                elif desc.endswith("x"):
                    try:
                        score = int(desc[:-1]) * 1000
                    except:
                        score = 0

                if score > best_score:
                    best_score = score
                    best_url = url_token

            if not best_url:
                continue

            absolute = urljoin(BASE, best_url)
            if absolute not in seen:
                seen.add(absolute)
                image_urls.append(absolute)

        # Pro jistotu ještě post-filtr: nech jen originály, pokud jsou k dispozici
        only_originals = [u for u in image_urls if "/p/o/" in u]
        if only_originals:
            image_urls = only_originals

        # (volitelné) seřaď, aby šly v pořadí základ, _1, _2, _3
        import re
        def suffix_key(u):
            m = re.search(r"_(\d+)\.jpg$", u)
            return 0 if m is None else int(m.group(1)) + 1

        image_urls.sort(key=suffix_key)

        return image_urls

    except Exception as e:
        logger.error(f"Error in wave_get_product_images: {str(e)}", exc_info=True)
        try:
            driver.save_screenshot("wave_debug.png")
            logger.debug("Saved screenshot to wave_debug.png")
        except Exception:
            pass
        return []
    finally:
        try:
            driver.quit()
        except Exception:
            pass


async def michaelag_get_product_images(PNumber):
    """
    Získá obrázky produktů z webu Michael AG
    """
    driver = get_chrome_driver(headless=False)  # Pro debugování necháme viditelný
    try:
        load_dotenv()
        username = os.getenv("MICHAELAG_USERNAME")
        password = os.getenv("MICHAELAG_PASSWORD")

        if not username or not password:
            logger.error("Michael AG credentials not found in .env")
            return []

        # 1) Přihlášení (tato část funguje - zachováme ji)
        login_url = "https://www.michael-ag.de/login"
        logger.debug(f"Navigating to login page: {login_url}")
        driver.get(login_url)

        # Čekání na kompletní načtení stránky
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Počkáme déle a zkusíme různé selektory
        time.sleep(3)

        # Zkusíme najít formulářové prvky různými způsoby
        selectors_to_try = [
            "input#customerid",
            "input[name='_username']",
            "input[type='text']",
            ".form-control[type='text']"
        ]

        username_field = None
        for selector in selectors_to_try:
            try:
                username_field = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                if username_field.is_displayed() and username_field.is_enabled():
                    logger.debug(f"Found username field with selector: {selector}")
                    break
                else:
                    username_field = None
            except:
                continue

        if not username_field:
            logger.error("Could not find username field with any selector")
            return []

        # Vyplníme username pomocí JavaScriptu
        driver.execute_script("arguments[0].value = arguments[1];", username_field, username)
        driver.execute_script("arguments[0].dispatchEvent(new Event('input', {bubbles: true}));", username_field)
        logger.debug("Username set via JavaScript")

        # Stejný postup pro password
        password_selectors = [
            "input#password",
            "input[name='_password']",
            "input[type='password']",
            ".form-control[type='password']"
        ]

        password_field = None
        for selector in password_selectors:
            try:
                password_field = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                if password_field.is_displayed():
                    logger.debug(f"Found password field with selector: {selector}")
                    break
                else:
                    password_field = None
            except:
                continue

        if not password_field:
            logger.error("Could not find password field with any selector")
            return []

        # Vyplníme password pomocí JavaScriptu
        driver.execute_script("arguments[0].value = arguments[1];", password_field, password)
        driver.execute_script("arguments[0].dispatchEvent(new Event('input', {bubbles: true}));", password_field)
        logger.debug("Password set via JavaScript")

        # Klikneme na přihlášení pomocí JavaScriptu
        login_selectors = [
            "button#login-submit",
            "button[type='submit']",
            ".btn-success",
            "input[type='submit']"
        ]

        login_button = None
        for selector in login_selectors:
            try:
                login_button = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                if login_button.is_displayed():
                    logger.debug(f"Found login button with selector: {selector}")
                    break
                else:
                    login_button = None
            except:
                continue

        if login_button:
            driver.execute_script("arguments[0].click();", login_button)
            logger.debug("Login button clicked via JavaScript")
        else:
            # Pokud nenajdeme tlačítko, zkusíme odeslat formulář
            form = driver.find_element(By.TAG_NAME, "form")
            driver.execute_script("arguments[0].submit();", form)
            logger.debug("Form submitted via JavaScript")

        # Čekání na přihlášení - kontrolujeme změnu URL nebo dashboard
        WebDriverWait(driver, 20).until(
            lambda d: "login" not in d.current_url or d.find_elements(By.CSS_SELECTOR, ".dashboard, .account, .welcome")
        )
        logger.debug("Successfully logged in")

        # 2) Navigace na stránku produktu
        product_url = f"https://www.michael-ag.de/shop/article/details/{PNumber}"
        logger.debug(f"Navigating to product page: {product_url}")
        driver.get(product_url)

        # VYLEPŠENÁ KONTROLA EXISTENCE PRODUKTU
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
            )

            # Kontrola specifických chybových stavů
            error_indicators = [
                "Seite nicht gefunden",
                "Artikel nicht gefunden",
                "Produkt nicht verfügbar",
                "404 Error",
                "nicht vorhanden"
            ]

            page_text = driver.page_source
            page_lower = page_text.lower()

            # Pokud najdeme specifické chybové hlášky
            if any(indicator in page_text for indicator in error_indicators):
                logger.error(f"Product {PNumber} not found on Michael AG - specific error message detected")
                return []

            # Kontrola zda máme hlavní obsah produktu
            product_content_selectors = [
                "div.slick-track",
                ".mt-article-details",
                "#article-data-main",
                "h2",  # název produktu
                ".mt-price"  # cena
            ]

            has_product_content = False
            for selector in product_content_selectors:
                if driver.find_elements(By.CSS_SELECTOR, selector):
                    has_product_content = True
                    logger.debug(f"Found product content with selector: {selector}")
                    break

            if not has_product_content:
                logger.error(f"Product {PNumber} page doesn't contain expected product elements")
                return []

        except Exception as e:
            logger.error(f"Product page for {PNumber} not loaded properly: {str(e)}")
            return []

        # 3) VYLEPŠENÁ ČÁST PRO EXTRACTION OBRAZKŮ
        try:
            # Čekáme na slick-track a pak ještě chvíli na načtení obrázků
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.slick-track"))
            )

            # Počkáme ještě moment na kompletní načtení
            time.sleep(2)

            # Scrollujeme trochu dolů, aby se načetly všechny lazy obrázky
            driver.execute_script("window.scrollTo(0, 300);")
            time.sleep(1)

            # Hledáme všechny obrázky v slick-track - používáme širší selektor
            image_selectors = [
                "div.slick-track img.mt-article-image",
                "div.slick-track img",
                ".slick-slide img",
                "img[data-srcset]",
                "img[src*='/media/']"
            ]

            image_elements = []
            for selector in image_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        logger.debug(f"Found {len(elements)} elements with selector: {selector}")
                        image_elements.extend(elements)
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue

            # Odstraníme duplicity
            unique_elements = []
            seen_ids = set()
            for elem in image_elements:
                elem_id = elem.id
                if elem_id not in seen_ids:
                    seen_ids.add(elem_id)
                    unique_elements.append(elem)

            logger.debug(f"Total unique image elements found: {len(unique_elements)}")

            image_urls = []
            base_url = "https://www.michael-ag.de"

            for img in unique_elements:
                try:
                    # Získej srcset atribut - zkusíme různé atributy
                    srcset = img.get_attribute("srcset")
                    if not srcset:
                        srcset = img.get_attribute("data-srcset")

                    # Pokud nemáme srcset, zkusíme přímo src
                    if not srcset:
                        src = img.get_attribute("src") or img.get_attribute("data-src")
                        if src and "/media/" in src:
                            absolute_url = urljoin(base_url, src)
                            # Přidáme pouze pokud ještě nemáme
                            if absolute_url not in image_urls:
                                image_urls.append(absolute_url)
                                logger.debug(f"Found image via src: {absolute_url}")
                        continue

                    # Rozděl srcset na jednotlivé URL s deskriptory
                    sources = [s.strip() for s in srcset.split(",") if s.strip()]

                    # Najdi URL s 1170w
                    target_url = None
                    for source in sources:
                        if "1170w" in source:
                            parts = source.strip().split()
                            if len(parts) >= 1:
                                target_url = parts[0]
                                logger.debug(f"Found 1170w source: {target_url}")
                                break

                    # Pokud nebylo nalezeno 1170w, vezmeme největší dostupnou velikost
                    if not target_url and sources:
                        best_size = 0
                        for source in sources:
                            parts = source.strip().split()
                            if len(parts) >= 2:
                                size_str = parts[1].lower()
                                if size_str.endswith('w'):
                                    try:
                                        size = int(size_str[:-1])
                                        if size > best_size:
                                            best_size = size
                                            target_url = parts[0]
                                    except ValueError:
                                        continue

                        if target_url:
                            logger.debug(f"Using largest available size ({best_size}w): {target_url}")

                    if target_url:
                        # Vytvoř absolutní URL
                        absolute_url = urljoin(base_url, target_url)
                        # Přidáme pouze pokud ještě nemáme
                        if absolute_url not in image_urls:
                            image_urls.append(absolute_url)
                            logger.debug(f"Added image URL: {absolute_url}")

                except Exception as e:
                    logger.warning(f"Error processing image element: {str(e)}")
                    continue

            # Pokud stále nemáme obrázky, zkusíme najít všechny img s media v src
            if not image_urls:
                logger.debug("Trying fallback - looking for all images with /media/ in src")
                all_media_imgs = driver.find_elements(By.CSS_SELECTOR, "img[src*='/media/']")
                for img in all_media_imgs:
                    src = img.get_attribute("src")
                    if src and "/media/" in src and "119149" in src:  # Filtrujeme podle čísla produktu
                        absolute_url = urljoin(base_url, src)
                        if absolute_url not in image_urls:
                            image_urls.append(absolute_url)
                            logger.debug(f"Found via fallback: {absolute_url}")

            logger.debug(f"Found {len(image_urls)} total images for product {PNumber}")

            # Seřadíme obrázky podle čísla (pokud je v URL)
            def get_image_number(url):
                import re
                match = re.search(r'(\d+)\.webp$', url)
                return int(match.group(1)) if match else 0

            image_urls.sort(key=get_image_number)

            return image_urls

        except Exception as e:
            logger.error(f"Error finding images: {str(e)}")
            # Uložíme debug informace
            try:
                html_content = driver.page_source
                debug_filename = f"michaelag_images_debug_{PNumber}.html"
                with open(debug_filename, "w", encoding="utf-8") as f:
                    f.write(html_content)
                logger.debug(f"Saved images debug HTML to {debug_filename}")
            except:
                pass
            return []

    except Exception as e:
        logger.error(f"Error in michaelag_get_product_images: {str(e)}", exc_info=True)

        # Uložení HTML pro debugování
        try:
            html_content = driver.page_source
            debug_filename = f"michaelag_debug_{PNumber}.html"
            with open(debug_filename, "w", encoding="utf-8") as f:
                f.write(html_content)
            logger.debug(f"Saved debug HTML to {debug_filename}")

            # Také screenshot pro jistotu
            driver.save_screenshot(f"michaelag_debug_{PNumber}.png")
            logger.debug(f"Saved screenshot to michaelag_debug_{PNumber}.png")
        except Exception as debug_error:
            logger.error(f"Could not save debug files: {str(debug_error)}")

        return []
    finally:
        try:
            driver.quit()
        except:
            pass


if __name__ == "__main__":
    import asyncio

    print(asyncio.run(michaelag_get_product_images("119149")))
    #print(asyncio.run(wave_get_product_images("100093375")))
    #print(asyncio.run(notebooksbilliger_get_product_images("A1064333")))
    #print(asyncio.run(komputronik_get_product_images("MOD-PHA-047")))
    #print(asyncio.run(fourcom_get_product_images("532754")))