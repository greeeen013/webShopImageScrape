import tkinter as tk
from tkinter import ttk, messagebox
import sv_ttk
from backend_services import SettingsManager, PreloaderService, ReviewService
from database import DatabaseManager
from ui.components import ProductFrame

class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("WebShopImageScrape v2")
        self.geometry("1400x900")
        
        # Init Services
        self.db_manager = DatabaseManager(db_path="data/queue.sqlite3")
        self.settings = SettingsManager("config/settings.json")
        
        self.preloader = PreloaderService(self.db_manager, self.settings)
        self.review_service = ReviewService(self.db_manager, self.settings, lib_path="data/saved_images")
        
        # Theme
        sv_ttk.set_theme(self.settings.get("theme") or "light")
        
        self.create_widgets()
        
    def create_widgets(self):
        # Top Bar
        top_bar = ttk.Frame(self, padding=10)
        top_bar.pack(fill="x")
        
        ttk.Button(top_bar, text="Přednačítat", command=self.open_preload_modal).pack(side="left", padx=5)
        
        self.btn_review = ttk.Button(top_bar, text="Odklikávat", command=self.load_next_batch)
        self.btn_review.pack(side="left", padx=5)
        
        # Batch Size
        ttk.Label(top_bar, text="Várka:").pack(side="left", padx=(15, 5))
        self.cmb_batch = ttk.Combobox(top_bar, values=["hodně málo", "málo", "středně", "hodně", "nejvíc"], state="readonly", width=10)
        self.cmb_batch.set(self.settings.get("last_batch_size"))
        self.cmb_batch.pack(side="left", padx=5)
        self.cmb_batch.bind("<<ComboboxSelected>>", self._on_batch_change)
        
        # Select All
        self.var_select_all = tk.BooleanVar(value=True)
        ttk.Checkbutton(top_bar, text="Vybrat vše", variable=self.var_select_all, command=self._toggle_select_all).pack(side="left", padx=15)
        
        # Settings
        ttk.Button(top_bar, text="Nastavení", command=self.open_settings).pack(side="right", padx=5)
        
        # Main Area (Canvas + Scroll)
        self.main_frame = ttk.Frame(self)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.canvas = tk.Canvas(self.main_frame)
        scrollbar = ttk.Scrollbar(self.main_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Mousewheel
        self.bind_all("<MouseWheel>", self._on_mousewheel)
        
        # Bottom Bar
        bottom_bar = ttk.Frame(self, padding=10)
        bottom_bar.pack(fill="x")
        
        ttk.Button(bottom_bar, text="Uložit a další várka", command=self.save_and_next).pack(side="right", padx=20)
        
        self.product_frames = []

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
    def _on_batch_change(self, event):
        self.settings.set("last_batch_size", self.cmb_batch.get())
        
    def _toggle_select_all(self):
        val = self.var_select_all.get()
        for pf in self.product_frames:
            for card in pf.image_cards:
                if not card.is_blacklisted:
                    card.selected.set(val)

    def open_preload_modal(self):
        modal = tk.Toplevel(self)
        modal.title("Přednačítání")
        modal.geometry("400x200")
        modal.transient(self)
        modal.grab_set()
        
        ttk.Label(modal, text="Probíhá vyhledávání obrázků...", font=("Arial", 12)).pack(pady=20)
        
        progress = ttk.Progressbar(modal, mode="determinate", length=300)
        progress.pack(pady=10)
        
        lbl_status = ttk.Label(modal, text="0 / ?")
        lbl_status.pack()
        
        def on_progress(done, total):
            modal.after(0, lambda: progress.config(maximum=total, value=done))
            modal.after(0, lambda: lbl_status.config(text=f"{done} / {total}"))
            
        def on_finished():
            modal.after(0, lambda: messagebox.showinfo("Hotovo", "Přednačítání dokončeno."))
            modal.after(0, modal.destroy)
            
        self.preloader.start_preload(on_progress, on_finished)
        
        ttk.Button(modal, text="Zrušit", command=lambda: [self.preloader.cancel(), modal.destroy()]).pack(pady=20)

    def load_next_batch(self):
        # Clear current
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.product_frames = []
        
        items = self.review_service.get_batch()
        if not items:
            messagebox.showinfo("Info", "Žádné další produkty k zobrazení.")
            return
            
        import json
        
        for item in items:
            try:
                urls = json.loads(item['image_urls'])
            except: urls = []
            
            # TODO: Filter URLs if they match "Blacklist Library" (Similarity Check)
            
            pf = ProductFrame(self.scrollable_frame, dict(item), urls, self.review_service, None, on_empty=self._on_product_empty)
            pf.pack(fill="x", pady=5)
            self.product_frames.append(pf)

    def _on_product_empty(self, pf):
        # Callback from ProductFrame when all images are filtered/invalid
        print(f"Product {pf.siv_code} has no valid images. Marking as seen and removing.")
        
        # 1. Mark as seen in DB so it doesn't reappear
        self.review_service.db.mark_as_seen(pf.siv_code)
        
        # 2. Remove from internal list
        if pf in self.product_frames:
            self.product_frames.remove(pf)
            
        # 3. Destroy UI
        pf.destroy()
        
        # 4. Auto-refill if list becomes empty
        # We use 'after' to avoid recursion depth issues or racing slightly
        if not self.product_frames:
            print("Batch empty after filtering. Loading next batch...")
            self.after(100, self.load_next_batch)

    def save_and_next(self):
        # 1. Collect and Save Blacklisted Items (Deferred)
        import hashlib
        for pf in self.product_frames:
            blacklisted = pf.get_blacklisted_items()
            for idx, img_data in blacklisted:
                h = hashlib.md5(img_data).hexdigest()
                fname = f"{pf.siv_code}_{idx}_{h[:8]}.jpg"
                self.review_service.save_to_library(img_data, fname)
                print(f"Saved blacklist item: {fname}")

        # 2. Collect results
        results = {}
        for pf in self.product_frames:
            sel_urls = pf.get_selected_urls()
            results[pf.siv_code] = sel_urls
            
        # Save to Backend
        self.review_service.confirm_products(results)
        
        # Load next
        self.load_next_batch()

    def open_settings(self):
        modal = tk.Toplevel(self)
        modal.title("Nastavení")
        modal.geometry("400x500")
        
        ttk.Label(modal, text="Povolení dodavatelé:").pack(pady=10)
        
        from constants import SUPPLIERS_CONFIG
        
        vars_map = {}
        enabled = self.settings.get("enabled_suppliers")
        
        frame = ttk.Frame(modal)
        frame.pack(fill="both", expand=True, padx=20)
        
        for name in SUPPLIERS_CONFIG.keys():
            v = tk.BooleanVar(value=name in enabled)
            vars_map[name] = v
            ttk.Checkbutton(frame, text=name, variable=v).pack(anchor="w")
            
        def save():
            new_enabled = [n for n, v in vars_map.items() if v.get()]
            self.settings.set("enabled_suppliers", new_enabled)
            modal.destroy()
            
        ttk.Button(modal, text="Uložit", command=save).pack(pady=20)

if __name__ == "__main__":
    app = MainApp()
    app.mainloop()
