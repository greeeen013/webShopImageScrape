from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from urllib.parse import urljoin
import os
from dotenv import load_dotenv
from .base_scraper import BaseScraper
import time
from threading import Lock

DRIVER_LOCK = Lock()

def get_chrome_driver(headless=False):
    options = uc.ChromeOptions()
    options.page_load_strategy = "eager"
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    if headless:
        options.add_argument("--headless=new")
    
    with DRIVER_LOCK:
        driver = uc.Chrome(options=options, use_subprocess=True)
    return driver

class NotebooksbilligerScraper(BaseScraper):
    def get_product_images(self, product_code: str, driver=None) -> list[str]:
        import urllib.parse
        encoded = urllib.parse.quote(urllib.parse.quote(product_code, safe=''))
        url = f"https://www.notebooksbilliger.de/produkte/{encoded}"
        
        should_quit = False
        if not driver:
            driver = get_chrome_driver(headless=True)
            should_quit = True
            
        try:
            driver.get(url)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.product-card")))
            
            # Simple fuzzy lookup on listing
            xpath = f"//div[contains(translate(@data-product-article-number, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{product_code.lower()}')]"
            card = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, xpath)))
            
            link = card.find_element(By.CSS_SELECTOR, "a.product-card__link").get_attribute("href")
            driver.get(link)
            
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "js-pdp-big-image-list")))
            images = driver.find_elements(By.CSS_SELECTOR, "#js-pdp-big-image-list img")
            return [img.get_attribute("src") for img in images if img.get_attribute("src")]
        except Exception:
            return []
        finally:
            if should_quit:
                try: driver.quit()
                except: pass

class FourcomScraper(BaseScraper):
    def get_product_images(self, product_code: str, driver=None) -> list[str]:
        BASE = "https://en.fourcom.dk"
        load_dotenv()
        user = os.getenv("FOURCOM_LOGIN")
        pwd = os.getenv("FOURCOM_PASSWORD")
        if not user or not pwd: return []
        
        should_quit = False
        if not driver:
            driver = get_chrome_driver(headless=True)
            should_quit = True
            
        try:
            # Check login only if needed or generic retry
            if "login" in driver.current_url or "ItemSearchPage" not in driver.current_url:
                driver.get(BASE)
                try:
                    WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input#form-field-kundenummer"))).send_keys(user)
                    driver.find_element(By.CSS_SELECTOR, "input#form-field-password").send_keys(pwd)
                    driver.find_element(By.CSS_SELECTOR, "button.elementor-button[type='submit']").click()
                except: pass # Maybe already logged in
            
            try:
                # Direct check if we are on search page already to save time?
                # Just go to Base/Search directly if possible?
                # Actually, relying on main loop is safer.
                pass
            except: pass

            # Optimization: Try go directly to search?
            WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='ItemSearchPage-text']")))
            search = driver.find_element(By.CSS_SELECTOR, "input[name='ItemSearchPage-text']")
            search.clear()
            search.send_keys(product_code)
            search.send_keys(Keys.RETURN)
            
            items = WebDriverWait(driver, 20).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.thumb-item")))
            target = None
            for it in items:
                nums = it.find_elements(By.CSS_SELECTOR, "div.itemnumber")
                for n in nums:
                    txt = (n.text or "").strip()
                    if "Fourcom varenr:" in txt:
                        if product_code in txt:
                            target = it
                            break
                if target: break
            
            if not target: return []
            
            try: click_el = target.find_element(By.CSS_SELECTOR, "div.ajax-load-product")
            except: click_el = target.find_element(By.CSS_SELECTOR, "h3.itemname.ajax-load-product")
            driver.execute_script("arguments[0].click();", click_el)
            
            WebDriverWait(driver, 20).until(lambda d: d.find_elements(By.CSS_SELECTOR, "div.thumbs a[data-fancybox='gallery']") or d.find_elements(By.CSS_SELECTOR, "div.big-image a[data-fancybox='gallery']"))
            
            links = driver.find_elements(By.CSS_SELECTOR, "div.thumbs a[data-fancybox='gallery']")
            if not links: links = driver.find_elements(By.CSS_SELECTOR, "div.big-image a[data-fancybox='gallery']")
            
            return [urljoin(BASE, a.get_attribute("href")) for a in links if a.get_attribute("href")]
        except Exception:
            return []
        finally:
            if should_quit:
                try: driver.quit()
                except: pass

class KomputronikScraper(BaseScraper):
    def get_product_images(self, product_code: str, driver=None) -> list[str]:
        load_dotenv()
        should_quit = False
        if not driver:
            driver = get_chrome_driver(headless=True)
            should_quit = True

        try:
            # Login only if needed. Komputronik might require fresh login often.
            if "customer/login" in driver.current_url or "login" not in driver.current_url: # Simplistic check
                 driver.get("https://b2b.komputronik.eu/customer/login")
                 try:
                     WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='custom_identify']"))).send_keys(os.getenv("KOMPUTRONIK_LOGIN"))
                     driver.find_element(By.CSS_SELECTOR, "input[name='customer_password']").send_keys(os.getenv("KOMPUTRONIK_PASSWORD"))
                     driver.find_element(By.CSS_SELECTOR, "button.tfg-actions__sign-in").click()
                 except: pass

            # Ensure we are logged in / ready to search
            inp = WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='Enter what you are looking for']")))
            inp.clear()
            inp.send_keys(product_code)
            inp.send_keys(Keys.RETURN)
            
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "img[ng-src][src]")))
            
            urls = []
            collected = set()
            try:
                next_btn = driver.find_element(By.CSS_SELECTOR, "button.nav-right.screen-only")
                for _ in range(20):
                    img = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "img[ng-src][src]")))
                    src = img.get_attribute("src")
                    if not src or src in collected: break
                    urls.append(src)
                    collected.add(src)
                    next_btn.click()
                    time.sleep(0.5)
            except: pass
            return urls
        except Exception:
            return []
        finally:
            if should_quit:
                try: driver.quit()
                except: pass

class WaveScraper(BaseScraper):
    def get_product_images(self, product_code: str, driver=None) -> list[str]:
        import urllib.parse
        BASE = "https://www.wave-distribution.de"
        
        should_quit = False
        if not driver:
            driver = get_chrome_driver(headless=True)
            should_quit = True
            
        try:
            driver.get(f"{BASE}/listing.xhtml?q={urllib.parse.quote(product_code)}")
            
            # Simple wait logic
            try:
                # Cookie banner
                btns = driver.find_elements(By.CSS_SELECTOR, "button")
                for b in btns: 
                    if "accept" in (b.text or "").lower(): b.click(); break
            except: pass
            
            # Listing vs Detail
            try:
                WebDriverWait(driver, 10).until(lambda d: d.find_elements(By.CSS_SELECTOR, "div.swiper-wrapper img[srcset]") or d.find_elements(By.CSS_SELECTOR, "a[href*='/p/']"))
            except: return []

            if not driver.find_elements(By.CSS_SELECTOR, "div.swiper-wrapper img[srcset]"):
                 # Listing
                 links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/p/']")
                 if not links: return []
                 driver.get(links[0].get_attribute("href"))
            
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.swiper-wrapper img[srcset]")))
            
            img_els = driver.find_elements(By.CSS_SELECTOR, "div.swiper-wrapper img[srcset]")
            urls = []
            for img in img_els:
                srcset = img.get_attribute("srcset")
                if srcset:
                    parts = srcset.split(",")
                    # Logic to pick best resolution (simplified)
                    best = parts[-1].strip().split()[0]
                    if "/p/o/" in best:
                        urls.append(urljoin(BASE, best))
            return list(set(urls))
        except Exception:
            return []
        finally:
            if should_quit:
                try: driver.quit()
                except: pass

class MichaelAgScraper(BaseScraper):
    def get_product_images(self, product_code: str, driver=None) -> list[str]:
        load_dotenv()
        user = os.getenv("MICHAELAG_USERNAME")
        pwd = os.getenv("MICHAELAG_PASSWORD")
        if not user or not pwd: return []
        
        should_quit = False
        if not driver:
            driver = get_chrome_driver(headless=True)
            should_quit = True
            
        try:
            if "login" in driver.current_url or "shop" not in driver.current_url:
                driver.get("https://www.michael-ag.de/login")
                try:
                    WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='_username']"))).send_keys(user)
                    driver.find_element(By.CSS_SELECTOR, "input[name='_password']").send_keys(pwd)
                    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
                    WebDriverWait(driver, 20).until(lambda d: "login" not in d.current_url)
                except: pass
            
            driver.get(f"https://www.michael-ag.de/shop/article/details/{product_code}")
            
            # Check 404
            if "nicht gefunden" in driver.page_source: return []
            
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.slick-track")))
            
            urls = []
            imgs = driver.find_elements(By.CSS_SELECTOR, "div.slick-track img")
            base = "https://www.michael-ag.de"
            for img in imgs:
                src = img.get_attribute("data-src") or img.get_attribute("src")
                if src and "/media/" in src:
                    urls.append(urljoin(base, src))
            
            return list(set(urls))
        except Exception:
            return []
        finally:
            if should_quit:
                try: driver.quit()
                except: pass
