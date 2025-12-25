import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import io
import threading
import requests

class ImageCard(tk.Frame):
    def __init__(self, parent, image_url, image_data, index, on_toggle, on_right_click, on_middle_click):
        super().__init__(parent, bd=1, relief="solid")
        self.url = image_url
        self.index = index
        self.on_toggle = on_toggle
        self.on_right_click = on_right_click
        self.on_middle_click = on_middle_click
        self.selected = tk.BooleanVar(value=True)
        self.is_favorite = False
        self.is_duplicate = False # Hidden state
        self.is_blacklisted = False

        # Load Image
        try:
            pil_img = Image.open(io.BytesIO(image_data))
            pil_img.thumbnail((200, 200)) # Card size
            self.tk_img = ImageTk.PhotoImage(pil_img)
        except:
            self.tk_img = None
            
        # Layout
        self.chk = tk.Checkbutton(self, variable=self.selected, command=self._on_check)
        self.chk.pack(anchor="nw")
        
        self.lbl_img = tk.Label(self, image=self.tk_img)
        self.lbl_img.pack()
        
        # Bindings
        self.lbl_img.bind("<Button-1>", lambda e: self._on_left_click())
        self.lbl_img.bind("<Button-3>", self._on_rclick)   # Right click -> Favorite
        self.lbl_img.bind("<Button-2>", self._on_mclick)   # Middle click -> Blacklist
        # Wheel click might be Button-2 on Windows? User said "koleckem".
        
    def _on_left_click(self):
        if not self.is_blacklisted:
            self.selected.set(not self.selected.get())

    def _on_check(self):
        if self.on_toggle: self.on_toggle(self.index, self.selected.get())
        
    def _on_rclick(self, event):
        self.on_right_click(self.index)
        
    def _on_mclick(self, event):
        # Toggle Blacklist State
        self.is_blacklisted = not self.is_blacklisted
        
        if self.is_blacklisted:
            # Block
            self.selected.set(False)
            self.chk.config(state="disabled")
            self.config(bg="#555555") # Dark gray
            self.lbl_img.config(bg="#555555")
        else:
            # Unblock
            self.selected.set(True) # Default back to selected? Or keeping false? User said "nepujde zaskrtnout".
            # Usually revert to default state (True).
            self.chk.config(state="normal")
            self.config(bg=self.master.cget("bg")) # Revert to default
            self.lbl_img.config(bg=self.master.cget("bg"))
            
        # self.on_middle_click(self.index, self) # Old immediate save logic removed/deferred
        
    def set_favorite(self, state):
        self.is_favorite = state
        if state:
            self.config(bd=3, highlightbackground="red", highlightcolor="red", highlightthickness=2)
            # Add "1" overlay if not exists
            if not hasattr(self, 'lbl_fav'):
                self.lbl_fav = tk.Label(self, text="1", bg="white", font=("Arial", 12, "bold"))
                self.lbl_fav.place(x=25, y=0)
        else:
            self.config(bd=1, highlightthickness=0)
            if hasattr(self, 'lbl_fav'):
                self.lbl_fav.destroy()
                del self.lbl_fav
                
    def hide_card(self):
        self.pack_forget()
        self.grid_forget()
        self.selected.set(False)


class ProductFrame(tk.LabelFrame):
    def __init__(self, parent, product_data, image_urls, review_service, on_product_update, on_empty=None):
        super().__init__(parent, text="", font=("Arial", 10, "bold"), padx=5, pady=5)
        self.product_data = product_data
        self.siv_code = product_data['SivCode']
        self.review_service = review_service
        self.image_cards = []
        self.on_product_update = on_product_update 
        self.on_empty = on_empty
        
        # Title
        title = f"{self.siv_code} - {product_data.get('SivName','')} - {product_data.get('SivCode2','')} - {product_data.get('SivComId','')}"
        tk.Label(self, text=title, font=("Arial", 11, "bold"), fg="blue").pack(anchor="w")
        
        # Images Container (Grid)
        self.grid_frame = tk.Frame(self)
        self.grid_frame.pack(fill="x", expand=True)
        
        self.loading_lbl = tk.Label(self.grid_frame, text="Načítám obrázky...")
        self.loading_lbl.pack()
        
        threading.Thread(target=self._load_images, args=(image_urls,), daemon=True).start()
        
    def _load_images(self, urls):
        # Fetch images
        valid_images = []
        for url in urls:
            try:
                r = requests.get(url, timeout=5)
                if r.status_code == 200:
                    # Check similarity against library (blacklist)
                    is_sim, _ = self.review_service.check_similarity(r.content)
                    if not is_sim:
                        valid_images.append((url, r.content))
                    else:
                        print(f"Skipping blacklisted image: {url}")
            except: pass
            
        # Update UI in main thread
        self.after(0, self._render_images, valid_images)

    def _render_images(self, images):
        self.loading_lbl.destroy()
        
        if not images:
            if self.on_empty:
                self.on_empty(self)
            return
        
        col = 0
        row = 0
        MAX_COLS = 6 # Default
        
        for i, (url, data) in enumerate(images):
            card = ImageCard(
                self.grid_frame, 
                url, data, i,
                on_toggle=self._on_card_toggle,
                on_right_click=self._on_card_right_click,
                on_middle_click=self._on_card_middle_click
            )
            card.image_data = data # Store for saving
            card.grid(row=row, column=col, padx=4, pady=4)
            self.image_cards.append(card)
            
            col += 1
            if col >= MAX_COLS:
                col = 0
                row += 1

    def _on_card_toggle(self, index, state):
        pass # Just state update

    def _on_card_right_click(self, index):
        # Exclusive favorite
        for i, card in enumerate(self.image_cards):
            if i == index:
                # Toggle
                new_state = not card.is_favorite
                card.set_favorite(new_state)
                # If setting true, ensure it is selected
                if new_state: card.selected.set(True)
                
                # Move to first position if favorited? User: "ten oznacenej produkt se ulozi jako prvni a ostatni zustanou tak jak byli"
                if new_state:
                     # Reorder logic visually?
                     # Tkinter grid reorder is tricky. We can forget and re-grid.
                     self._move_to_first(card)
            else:
                 # Unset others
                 if card.is_favorite:
                     card.set_favorite(False)
                     
    def _move_to_first(self, fav_card):
        # Remove all
        for card in self.image_cards:
            card.grid_forget()
            
        # Re-grid: Fav first, then others
        others = [c for c in self.image_cards if c != fav_card]
        reordered = [fav_card] + others
        
        col = 0
        row = 0
        MAX_COLS = 6
        for card in reordered:
            card.grid(row=row, column=col, padx=4, pady=4)
            col += 1
            if col >= MAX_COLS:
                col = 0
                row += 1
        
        # Update list order?
        # self.image_cards = reordered # Maybe dont mess with index matching original URLs unless we map carefully.
        # But we need index for callbacks?
        # Simplest is just visual reorder.
        pass

    def _on_card_middle_click(self, index, card_widget):
        # Check similarity
        # User: "kdyz klikne na obrazek koleckem tak se ulozi do nejake slozky a pak ... se zkontroluje jestli tam neni obrazek kterej ma 90% podobnost ... a pokud ma tak se ten danej obrazek ani nezobrazi"
        
        # 1. Save to library
        # Generate filename
        import hashlib
        h = hashlib.md5(card_widget.image_data).hexdigest()
        fname = f"{self.siv_code}_{index}_{h[:8]}.jpg"
        
        self.review_service.save_to_library(card_widget.image_data, fname)
        print(f"Saved {fname} to library.")
        
        # 2. Check current batch for similarity?
        # The user said: "pri dalsim nacteni varky... se zkontroluje".
        # But also: "a tim ze se nezobrazi tak nebude ani zaskrtlej jakoby proste neexistuje".
        # This implies immediate check might be useful OR it affects FUTURE loads.
        # Reading carefully: "ulozi do navky slozky a PAK PRI DALSIM NACTENI VARKY se zkontroluje".
        # So we dont need to hide it NOW? 
        # "a pokud ma tak se ten danej obrazek ani nezobrazi...".
        # Maybe middle click just marks it as "bad/duplicate reference" for future?
        # "tzn ze znova kdyby to uzivatle spustil... se nebude ten produkt prohledavat" -> Preload logic.
        
        # User logic seems to be: "I see a generic image (e.g. 'No Image Available placeholder'). I middle click it to save it to my 'blacklist reference library'. Next time I load a batch, if any image matches this blacklist, it won't show up."
        
        # So: Middle Click -> Save to library (Blacklist).
        # AND check similarity against OTHER images currently shown?
        # "a pak pri dalsim nacteni varky ... se zkontroluje".
        # Okay, so just save for now.
        # Maybe visual feedback "Added to Blacklist".
        
        card_widget.config(bg="gray") # visual feedback
        
    def get_selected_urls(self):
        # We need to return URLs in the visual order (Favorite first)
        # Find visual order
        selected = []
        
        # Find favorite
        fav = None
        for card in self.image_cards:
            if card.is_favorite and card.selected.get():
                fav = card.url
                break
                
        others = []
        for card in self.image_cards:
            if card.selected.get() and card.url != fav:
                others.append(card.url)
                
        if fav:
            return [fav] + others
        return others

    def get_blacklisted_items(self):
        """Returns list of (index, image_data) for blacklisted items."""
        items = []
        for i, card in enumerate(self.image_cards):
            if card.is_blacklisted:
                items.append((i, card.image_data))
        return items
