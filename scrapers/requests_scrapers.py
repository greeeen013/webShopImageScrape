import requests
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv
from .base_scraper import BaseScraper
import traceback

# Common Headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

class OctoScraper(BaseScraper):
    def get_product_images(self, product_code: str) -> list[str]:
        search_url = f"https://www.octo24.com/result.php?keywords={product_code}"
        try:
            response = requests.get(search_url, headers=HEADERS, timeout=10)
            if response.status_code != 200: return []
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find product container
            product_container = soup.find('div', class_='flex_listing_container')
            if not product_container: return []
            
            first_product = product_container.find('div', class_='listing_item_box')
            if not first_product: return []
            
            product_link = first_product.find('a', href=True)
            if not product_link: return []
            
            product_url = product_link['href']
            
            # Product Page
            product_response = requests.get(product_url, headers=HEADERS, timeout=10)
            if product_response.status_code != 200: return []
            product_soup = BeautifulSoup(product_response.text, 'html.parser')
            
            image_container = product_soup.find('div', class_='pd_image_container')
            if not image_container: return []
            
            images = image_container.find_all('img', src=True)
            image_urls = []
            for img in images:
                src = img['src']
                if src.startswith('//'): src = 'https:' + src
                elif src.startswith('/'): src = 'https://www.octo24.com' + src
                if src and src not in image_urls:
                    image_urls.append(src)
            return image_urls
        except Exception:
            return []

class DirectDealScraper(BaseScraper):
    def get_product_images(self, product_code: str) -> list[str]:
        url = f"https://directdeal.me/search?search={product_code}"
        try:
            headers = HEADERS.copy()
            headers['Accept-Language'] = 'en-US,en;q=0.9'
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200: return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            tns_ovh = soup.find('div', {'id': 'tns17-mw'}) or soup.find('div', class_='tns-ovh')
            if not tns_ovh:
                 possible = soup.find_all(['div', 'section'], class_=lambda x: x and 'gallery' in x.lower())
                 if possible: tns_ovh = possible[0]
            
            if not tns_ovh: return []
            
            images = tns_ovh.find_all('img', class_=lambda x: x and 'image' in x.lower())
            if not images: images = tns_ovh.find_all('img')
            
            image_urls = []
            for img in images:
                src = img.get('src') or img.get('data-src') or img.get('data-full-image')
                if src:
                    if src.startswith('//'): src = "https:" + src
                    elif src.startswith('/'): src = f"https://directdeal.me{src}"
                    if src not in image_urls: image_urls.append(src)
            return image_urls
        except Exception:
            return []

class ApiScraper(BaseScraper):
    def get_product_images(self, product_code: str) -> list[str]:
        url = f"https://shop.api.de/product/details/{product_code}"
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            if response.status_code != 200: return []
            soup = BeautifulSoup(response.text, 'html.parser')
            images = soup.find_all('img', class_='slick-img')
            urls = []
            for img in images:
                src = img.get('src')
                if src:
                    if src.startswith('//'): src = 'https:' + src
                    elif src.startswith('/'): src = 'https://shop.api.de' + src
                    if src not in urls: urls.append(src)
            return urls
        except Exception:
            return []

class EasyNotebooksScraper(BaseScraper):
    def get_product_images(self, product_code: str) -> list[str]:
        url = f"https://www.easynotebooks.de/search?sSearch={product_code}"
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            if response.status_code != 200: return []
            soup = BeautifulSoup(response.text, 'html.parser')
            image_slider = soup.find('div', class_='image-slider--slide')
            if not image_slider: return []
            img_tags = image_slider.find_all('img', {'srcset': True})
            return [img['srcset'] for img in img_tags]
        except Exception:
            return []

class KosatecScraper(BaseScraper):
    def get_product_images(self, product_code: str) -> list[str]:
        search_url = f"https://shop.kosatec.de/factfinder/result?query={product_code}"
        try:
            response = requests.get(search_url, headers=HEADERS, timeout=10)
            if response.status_code != 200: return []
            soup = BeautifulSoup(response.text, 'html.parser')
            
            product_container = soup.find('div', class_='cms-listing-col')
            if not product_container: return []
            product_link = product_container.find('a', href=True)
            if not product_link: return []
            
            product_response = requests.get(product_link['href'], headers=HEADERS, timeout=10)
            if product_response.status_code != 200: return []
            product_soup = BeautifulSoup(product_response.text, 'html.parser')
            
            gallery = product_soup.find('div', class_='tns-inner') or product_soup.find('div', class_='gallery-slider-container')
            if not gallery: return []
            
            images = gallery.find_all('img', class_='gallery-slider-image') or gallery.find_all('img', src=True)
            urls = []
            for img in images:
                src = img.get('data-full-image') or img.get('src')
                if src:
                    if src.startswith('//'): src = 'https:' + src
                    elif src.startswith('/'): src = 'https://shop.kosatec.de' + src
                    if src not in urls: urls.append(src)
            return urls
        except Exception:
            return []

class DcsScraper(BaseScraper):
    def get_product_images(self, product_code: str) -> list[str]:
        load_dotenv()
        username = os.getenv('DCS_USERNAME')
        password = os.getenv('DCS_PASSWORD')
        if not username or not password: return []

        try:
            with requests.Session() as session:
                headers = HEADERS.copy()
                headers.update({'Accept-Language': 'cs,en;q=0.9', 'DNT': '1', 'Upgrade-Insecure-Requests': '1'})
                
                login_r = session.post("https://www.dcs.dk/en/login", headers=headers,
                                     data={'_username': username, '_password': password, '_submit': ''}, timeout=15)
                if login_r.status_code != 200 or "login" in login_r.url: return []
                
                search_r = session.get(f"https://www.dcs.dk/en/search?q={product_code}", timeout=10)
                if search_r.status_code != 200: return []
                
                soup = BeautifulSoup(search_r.text, 'html.parser')
                link = soup.find('a', class_='product-link')
                if not link: return []
                
                prod_u = f"https://www.dcs.dk{link.get('href')}"
                prod_r = session.get(prod_u, timeout=10)
                if prod_r.status_code != 200: return []
                
                p_soup = BeautifulSoup(prod_r.text, 'html.parser')
                gallery = p_soup.find('div', class_='product-lightbox-carousel')
                if not gallery: return []
                
                images = gallery.find_all('img')
                urls = []
                for img in images:
                    src = img.get('src')
                    if src:
                        if src.startswith('//'): src = f"https:{src}"
                        elif src.startswith('/'): src = f"https://www.dcs.dk{src}"
                        if src not in urls: urls.append(src)
                return urls
        except Exception:
            return []

class IncomGroupScraper(BaseScraper):
    def get_product_images(self, product_code: str) -> list[str]:
        search_url = f"https://www.incomgroup.pl/?s={product_code}&post_type=produkt"
        try:
            response = requests.get(search_url, headers=HEADERS, timeout=10)
            if response.status_code != 200: return []
            soup = BeautifulSoup(response.text, 'html.parser')
            
            container = soup.find('ul', class_='products columns-4')
            if not container: return []
            
            li = container.find('li', class_='product')
            if not li: return []
            link = li.find('a', href=True)
            if not link: return []
            
            prod_resp = requests.get(link['href'], headers=HEADERS, timeout=10)
            if prod_resp.status_code != 200: return []
            p_soup = BeautifulSoup(prod_resp.text, 'html.parser')
            
            # Check Manufacturer Code
            found = False
            for div in p_soup.find_all('div', class_='et_pb_text_inner'):
                if "Symbol producenta:" in div.get_text() and product_code in div.get_text():
                    found = True
                    break
            if not found: return []
            
            gallery = p_soup.find('div', class_='woocommerce-product-gallery__wrapper')
            if not gallery: return []
            
            urls = []
            for a in gallery.find_all('a', href=True):
                if a['href'] not in urls: urls.append(a['href'])
            return urls
        except Exception:
            return []

class WortmannScraper(BaseScraper):
    def get_product_images(self, product_code: str) -> list[str]:
        search_url = f"https://www.wortmann.de/de-de/search.aspx?q={product_code}"
        base_url = "https://www.wortmann.de/de-de"
        try:
            response = requests.get(search_url, headers=HEADERS, timeout=10)
            if response.status_code != 200: return []
            soup = BeautifulSoup(response.text, 'html.parser')
            
            anchor = soup.find('a', id=lambda x: x and x.endswith('_HyperLinkProduct'))
            if not anchor: return []
            
            prod_href = anchor['href']
            prod_url = base_url + '/' + prod_href.lstrip('/')
            
            prod_resp = requests.get(prod_url, headers=HEADERS, timeout=10)
            if prod_resp.status_code != 200: return []
            
            p_soup = BeautifulSoup(prod_resp.text, 'html.parser')
            carousel = p_soup.find('div', class_='carousel-inner')
            if not carousel: return []
            
            urls = []
            for img in carousel.find_all('img', src=True):
                src = img['src']
                if src.startswith('http'): urls.append(src)
                elif src.startswith('/'): urls.append(base_url + src)
            return urls
        except Exception:
            return []

class AxroScraper(BaseScraper):
    def get_product_images(self, product_code: str) -> list[str]:
        search_url = f"https://www.axro.com/en/search?search={product_code}"
        try:
            response = requests.get(search_url, headers=HEADERS, timeout=10)
            if response.status_code != 200: return []
            soup = BeautifulSoup(response.text, 'html.parser')
            
            container = soup.find('div', class_='product-detail')
            if not container: return []
            
            gallery = container.find('div', class_='gallery-slider-container') or \
                      container.find('div', class_='gallery-slider') or \
                      container.find('div', class_='product-image-gallery')
            if not gallery: return []
            
            images = gallery.find_all('img', class_='gallery-slider-image') or gallery.find_all('img', src=True)
            urls = []
            for img in images:
                src = img.get('data-full-image') or img.get('src')
                if src:
                    if src.startswith('//'): src = 'https:' + src
                    elif src.startswith('/'): src = 'https://www.axro.com' + src
                    if src not in urls: urls.append(src)
            return urls
        except Exception:
            return []
