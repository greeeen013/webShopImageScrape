import json
import os
import threading
import queue
import time
from pathlib import Path
from constants import SUPPLIERS_CONFIG
from database import DatabaseManager
from scrapers import * # Import all scrapers if strictly needed, but actually we get them via config now.
# But actually constants.py imports them.

from utils.image_utils import ImageHashManager

class SettingsManager:
    def __init__(self, config_path="config/settings.json"):
        self.config_path = Path(config_path)
        self.config = self._load_defaults()
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self.config.update(saved)
            except: pass
            
    def _load_defaults(self):
        defaults = {
            "enabled_suppliers": list(SUPPLIERS_CONFIG.keys()),
            "last_batch_size": "středně",
            "images_per_row": 6,
            "theme": "light"
        }
        return defaults

    def save(self):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4)
            
    def get(self, key):
        return self.config.get(key)
        
    def set(self, key, value):
        self.config[key] = value
        self.save()


class PreloaderService:
    def __init__(self, db_manager: DatabaseManager, settings: SettingsManager):
        self.db = db_manager
        self.settings = settings
        self.stop_event = threading.Event()
        self.progress_callback = None
        self.finished_callback = None
        
    def start_preload(self, on_progress, on_finished):
        self.progress_callback = on_progress
        self.finished_callback = on_finished
        self.stop_event.clear()
        threading.Thread(target=self._run, daemon=True).start()
        
    def cancel(self):
        self.stop_event.set()
        
    def _run(self):
        # 1. Fetch missing from MSSQL
        enabled_names = self.settings.get("enabled_suppliers")
        supplier_ids = []
        
        # Resolve IDs logic
        if "Všechny dodavatele" in enabled_names:
             for name, info in SUPPLIERS_CONFIG.items():
                 if name != "Všechny dodavatele":
                     supplier_ids.append(info["id"])
        else:
            for name in enabled_names:
                if name in SUPPLIERS_CONFIG:
                   supplier_ids.append(SUPPLIERS_CONFIG[name]["id"])
        
        print(f"Fetching candidates for IDs: {supplier_ids}")
        candidates = self.db.fetch_candidates_from_mssql(supplier_ids)
        new_count = self.db.enqueue_products(candidates)
        print(f"Enqueued {new_count} new products.")
        
        # 2. Process Queue
        tasks = self.db.get_pending_tasks()
        total = len(tasks)
        if total == 0:
            if self.finished_callback: self.finished_callback()
            return

        completed = 0
        if self.progress_callback:
            self.progress_callback(0, total)
            
        # Queue for persistent workers
        task_queue = queue.Queue()
        for t in tasks:
            task_queue.put(t)
            
        # Worker function for threads
        def worker():
            nonlocal completed
            # Init persistent driver for this thread
            driver = None
            try:
                # Lazy init or just init here.
                # Import here to avoid circular logic depending on structure, but global import is fine.
                from scrapers.selenium_scrapers import get_chrome_driver
                driver = get_chrome_driver(headless=True)
                
                while not self.stop_event.is_set():
                    try:
                        item = task_queue.get(timeout=1) # Check stop event periodically
                    except queue.Empty:
                        break
                        
                    try:
                        siv_com_id = item['SivComId']
                        supplier_conf = None
                        for name, conf in SUPPLIERS_CONFIG.items():
                            if conf["id"] == siv_com_id:
                                supplier_conf = conf
                                break
                        
                        urls = []
                        if supplier_conf:
                            ScraperClass = supplier_conf.get("scraper_class")
                            if ScraperClass:
                                scraper = ScraperClass()
                                # Reuse driver!
                                urls = scraper.get_product_images(item['SivCode'], driver=driver)
                        
                        self.db.update_task_results(item['SivCode'], urls, [])
                        
                        # Update progress
                        # Lock for counter safety? Python ints are atomic-ish but better safe.
                        # Simple non-locked increment usually fine for progress bar only.
                        completed += 1
                        if self.progress_callback:
                            self.progress_callback(completed, total)
                            
                    except Exception as e:
                        print(f"Worker Error: {e}")
                    finally:
                        task_queue.task_done()
                        
            except Exception as e:
                print(f"Worker Init Error: {e}")
            finally:
                if driver:
                    try: driver.quit()
                    except: pass

        # Start Workers
        threads = []
        num_workers = 5 # config?
        for _ in range(num_workers):
            t = threading.Thread(target=worker, daemon=True)
            t.start()
            threads.append(t)
            
        # Wait for queue to empty (or stop event)
        # We can join threads.
        for t in threads:
            t.join()
                    
        if self.finished_callback:
            self.finished_callback()


class ReviewService:
    def __init__(self, db_manager: DatabaseManager, settings: SettingsManager, lib_path="data/library"):
        self.db = db_manager
        self.settings = settings
        self.hash_manager = ImageHashManager(lib_path)
        
    def get_batch(self):
        batch_size_str = self.settings.get("last_batch_size")
        # Map string to number
        # "hodně málo": 15, "málo": 25, "středně": 50...
        mapping = {
            "hodně málo": 15, "málo": 25, "středně": 50, "hodně": 100, "nejvíc": 150
        }
        limit = mapping.get(batch_size_str, 20)
        
        enabled_names = self.settings.get("enabled_suppliers")
        supplier_ids = [] # Resolving similar logic to Preloader
        for name in enabled_names:
            if name in SUPPLIERS_CONFIG and name != "Všechny dodavatele":
                supplier_ids.append(SUPPLIERS_CONFIG[name]["id"])
        
        items = self.db.get_review_batch(limit, supplier_ids)
        return items
        
    def save_to_library(self, image_data, filename):
        path = self.hash_manager.library_path / filename
        with open(path, "wb") as f:
            f.write(image_data)
        self.hash_manager.add_to_library(path)
        
    def check_similarity(self, image_data):
        # Need simpler method in hash manager that accepts bytesIO/image object
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(image_data))
        return self.hash_manager.is_similar(img, threshold=5) # 5 is <10% diff roughly for phash size 8? User asked for 90% similarity.
        # phash difference of 0 is identical. range 0-64.
        # 90% prodobnost -> 10% difference. 64 * 0.1 = 6.4. So threshold <= 6 is safe.
        
    def confirm_products(self, products_map):
        """
        products_map: { siv_code: [url1, url2...] }
        """
        for code, urls in products_map.items():
            if urls:
                self.db.save_product_images(code, urls)
            # Mark seen regardless of save (if user clicked save/next batch)
            self.db.mark_as_seen(code)
