import tkinter as tk
from tkinter import ttk, messagebox
import requests
from PIL import Image, ImageTk
import io
import pyodbc
import threading
import queue
import asyncio
import json
import os
from dotenv import load_dotenv

from ShopScraper import octo_get_product_images, directdeal_get_product_images, api_get_product_images, easynotebooks_get_product_images, kosatec_get_product_images, dcs_get_product_images, incomgroup_get_product_images, wortmann_get_product_images, wave_get_product_images
from ShopSelenium import fourcom_get_product_images, notebooksbilliger_get_product_images, komputronik_get_product_images


# ... (původní kód)

DODAVATELE = {
    # klasickej scrape
    "octo it": {"kod": "348651", "produkt_dotaz_kod": "SivCode", "funkce": octo_get_product_images},
    "directdeal/everit": {"kod": "268493", "produkt_dotaz_kod": "SivCode", "funkce": directdeal_get_product_images},
    "api": {"kod": "161784", "produkt_dotaz_kod": "SivCode", "funkce": api_get_product_images},
    "NetFactory/easynotebooks": {"kod": "351191", "produkt_dotaz_kod": "SivCode", "funkce": easynotebooks_get_product_images},
    "Kosatec": {"kod": "165463", "produkt_dotaz_kod": "SivCode", "funkce": kosatec_get_product_images},
    "Dcs (nekvalitní)": {"kod": "319004", "produkt_dotaz_kod": "SivCode", "funkce": dcs_get_product_images},
    "IncomGroup": {"kod": "169701", "produkt_dotaz_kod": "SivCode2", "funkce": incomgroup_get_product_images},
    "Wortmann": {"kod": "190157", "produkt_dotaz_kod": "SivCode", "funkce": wortmann_get_product_images},
    "Wave": {"kod": "115565", "produkt_dotaz_kod": "SivCode", "funkce": wave_get_product_images},

    # selenium
    "notebooksbilliger (selenium)": {"kod": "340871", "produkt_dotaz_kod": "SivCode", "funkce": notebooksbilliger_get_product_images},
    "fourcom (selenium)": {"kod": "312585", "produkt_dotaz_kod": "SivCode", "funkce": fourcom_get_product_images},
    "Komputronik (selenium)": {"kod": "104584", "produkt_dotaz_kod": "SivCode", "funkce": komputronik_get_product_images},
}
POCTY_PRODUKTU = [25, 50]
OBRAZKY_NA_RADEK = ["2", "3", "4", "5", "6", "nekonečno"]

# Nová konstanta pro soubor s ignorovanými produkty
IGNORE_FILE = "ignoreSivCode.json"


class LoadingScreen:
    def __init__(self, root):
        self.root = root
        self.loading_window = tk.Toplevel(root)
        self.loading_window.title("Načítání...")
        self.loading_window.geometry("300x150")
        self.loading_window.resizable(False, False)

        # Center the loading window
        window_width = 300
        window_height = 150
        screen_width = self.loading_window.winfo_screenwidth()
        screen_height = self.loading_window.winfo_screenheight()
        position_top = int(screen_height / 2 - window_height / 2)
        position_right = int(screen_width / 2 - window_width / 2)
        self.loading_window.geometry(f"{window_width}x{window_height}+{position_right}+{position_top}")

        self.overlay = None  # Přidáno pro překryvnou obrazovku

        # Make it modal
        self.loading_window.grab_set()
        self.loading_window.transient(root)

        # Loading label
        tk.Label(self.loading_window, text="Načítám produkty...", font=("Arial", 14)).pack(pady=20)

        # Progress bar
        self.progress = ttk.Progressbar(
            self.loading_window,
            orient='horizontal',
            mode='indeterminate',
            length=200
        )
        self.progress.pack(pady=10)
        self.progress.start()

        # Disable close button
        self.loading_window.protocol("WM_DELETE_WINDOW", lambda: None)

    def close(self):
        self.progress.stop()
        self.loading_window.grab_release()
        self.loading_window.destroy()


class ObrFormApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Doplnění obrázků k produktům")
        self.root.geometry("1400x900")

        self.conn = None
        self.cursor = None
        self.filtrovane_produkty = []
        self.img_refs = {}
        self.vybrany_dodavatel = None
        self.vybrany_dodavatel_kod = None
        self.df = None
        self.produkty_k_zpracovani = []
        self.produkt_widgety = {}
        self.buffer_size = 25
        self.image_queue = queue.Queue()
        self.loading_threads = []
        self.all_check_var = tk.BooleanVar(value=True) # zaškrtnutý checkbox pro "Vybrat vše"
        self.produkt_check_vars = {}
        self.image_check_vars = {}
        self.loading_active = False
        self.max_threads = 5
        self.image_cache = {}
        self.obrazky_na_radek = 6
        self.scrollregion_scheduled = False
        self.loading_screen = None

        # Načtení ignorovaných kódů při startu
        self.ignored_codes = self.load_ignored_codes()

        load_dotenv()
        db_table = os.getenv('DB_TABLE')


        # Konfigurace databáze
        self.table_name = db_table
        self.column_mapping = {
            'code': 'SivCode',
            'name': 'SivName',
            'supplier': 'SivComId',
            'notes': 'SivNotePic',
            'pairing': 'SivStiId'
        }

        print("[DEBUG] Inicializace GUI...")
        self.setup_gui()

    def load_ignored_codes(self):
        """Načte ignorované kódy z JSON souboru"""
        try:
            if os.path.exists(IGNORE_FILE):
                with open(IGNORE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"[CHYBA] Načtení ignorovaných kódů: {e}")
            return {}

    def save_ignored_codes(self):
        """Uloží ignorované kódy do JSON souboru"""
        try:
            with open(IGNORE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.ignored_codes, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"[CHYBA] Ukládání ignorovaných kódů: {e}")

    def add_ignored_code(self, supplier_code, siv_code):
        """Přidá kód do seznamu ignorovaných pro daného dodavatele"""
        if supplier_code not in self.ignored_codes:
            self.ignored_codes[supplier_code] = []

        if siv_code not in self.ignored_codes[supplier_code]:
            self.ignored_codes[supplier_code].append(siv_code)
            self.save_ignored_codes()

    def connect_to_database(self):
        """Připojí se k SQL Serveru"""
        try:
            # Load environment variables from .env file
            load_dotenv()

            server = os.getenv('DB_SERVER')
            database = os.getenv('DB_DATABASE')
            username = os.getenv('DB_USERNAME')
            password = os.getenv('DB_PASSWORD')

            conn_str = (
                f'DRIVER={{SQL Server}};'
                f'SERVER={server};'
                f'DATABASE={database};'
                f'UID={username};'
                f'PWD={password}'
            )

            print("[DEBUG] Pokus o připojení k databázi...")
            self.conn = pyodbc.connect(conn_str)
            self.cursor = self.conn.cursor()
            print("[DEBUG] Úspěšně připojeno k SQL Serveru")
            return True
        except Exception as e:
            print(f"[CHYBA] Připojení k databázi: {str(e)}")
            messagebox.showerror("Chyba", f"Chyba při připojování k databázi:\n{str(e)}")
            return False

    def check_database_structure(self):
        """Zkontroluje existenci potřebných sloupců"""
        try:
            required_columns = ['SivCode', 'SivComId', 'SivNotePic', 'SivName']

            query = f"""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = '{self.table_name}'
            """
            self.cursor.execute(query)
            existing_columns = [row.COLUMN_NAME for row in self.cursor.fetchall()]

            missing_columns = [col for col in required_columns if col not in existing_columns]

            if missing_columns:
                messagebox.showerror("Chyba",
                                     f"V tabulce chybí potřebné sloupce!\n"
                                     f"Chybějící sloupce: {', '.join(missing_columns)}")
                return False

            print("[DEBUG] Všechny potřebné sloupce existují")
            return True

        except Exception as e:
            print(f"[CHYBA] Při kontrole struktury databáze: {str(e)}")
            messagebox.showerror("Chyba", f"Chyba při kontrole struktury databáze:\n{str(e)}")
            return False

    def setup_gui(self):
        """Vytvoří GUI prvky aplikace."""
        top_frame = tk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=10, pady=10)

        # Combobox pro výběr dodavatele
        tk.Label(top_frame, text="Dodavatel:", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        self.combo_dodavatel = ttk.Combobox(top_frame, values=list(DODAVATELE.keys()), state="readonly",
                                            font=("Arial", 12), width=20)
        self.combo_dodavatel.pack(side=tk.LEFT, padx=5)
        self.combo_dodavatel.bind("<<ComboboxSelected>>", self.combo_selected)

        # Combobox pro výběr počtu produktů
        tk.Label(top_frame, text="Počet produktů:", font=("Arial", 12)).pack(side=tk.LEFT, padx=(20, 5))
        self.combo_pocet = ttk.Combobox(top_frame, values=POCTY_PRODUKTU, state="readonly", font=("Arial", 12),
                                        width=10)
        self.combo_pocet.current(0)
        self.combo_pocet.pack(side=tk.LEFT, padx=5)

        # Combobox pro výběr počtu obrázků na řádek
        tk.Label(top_frame, text="Obrázky na řádek:", font=("Arial", 12)).pack(side=tk.LEFT, padx=(20, 5))
        self.combo_obrazky_na_radek = ttk.Combobox(top_frame, values=OBRAZKY_NA_RADEK, state="readonly",
                                                   font=("Arial", 12), width=10)
        self.combo_obrazky_na_radek.current(4)  # 4. pozice toho listu takze (6)
        self.combo_obrazky_na_radek.pack(side=tk.LEFT, padx=5)
        self.combo_obrazky_na_radek.bind("<<ComboboxSelected>>", self.update_obrazky_na_radek)

        # Checkbox "Vybrat vše"
        self.chk_all = tk.Checkbutton(top_frame, text="Vybrat vše", variable=self.all_check_var,
                                      font=("Arial", 12), command=self.toggle_all)
        self.chk_all.pack(side=tk.LEFT, padx=20)

        # Canvas s scrollbarem
        self.canvas_frame = tk.Frame(self.root)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.canvas = tk.Canvas(self.canvas_frame)
        self.scroll_y = tk.Scrollbar(self.canvas_frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scroll_y.set)

        self.scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.inner_frame = tk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.inner_frame, anchor=tk.NW)

        self.inner_frame.bind("<Configure>", lambda e: self.schedule_scrollregion_update())
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.inner_frame.bind("<MouseWheel>", self._on_mousewheel)

        # PŘIDÁNO: Scrollování v celé aplikaci
        self.root.bind("<MouseWheel>", self._on_mousewheel)

        # Tlačítka dole
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="Potvrdit", command=self.potvrdit_vse,
                  font=("Arial", 14), height=2, width=15).pack(side=tk.LEFT, padx=20)
        tk.Button(btn_frame, text="Zrušit", command=self.zrusit_vse,
                  font=("Arial", 14), height=2, width=15).pack(side=tk.LEFT, padx=20)

    def schedule_scrollregion_update(self):
        """Plánuje aktualizaci scrollregionu pro plynulejší scrollování."""
        if not self.scrollregion_scheduled:
            self.scrollregion_scheduled = True
            self.root.after(100, self.update_scrollregion)

    def update_scrollregion(self):
        """Aktualizuje scrollregion canvasu s kontrolou existence."""
        if self.inner_frame.winfo_exists():
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.scrollregion_scheduled = False

    def update_obrazky_na_radek(self, event=None):
        """Aktualizuje počet obrázků na řádek podle výběru uživatele."""
        vyber = self.combo_obrazky_na_radek.get()
        if vyber == "nekonečno":
            self.obrazky_na_radek = float('inf')
        else:
            self.obrazky_na_radek = int(vyber)

        # Přerozdělení obrázků podle nového nastavení
        for kod, data in self.produkt_widgety.items():
            self.reorganize_images(data['images_frame'], data['urls'], kod)

    def reorganize_images(self, frame, urls, kod):
        """Přerozdělí obrázky v frame podle aktuálního nastavení počtu na řádek."""
        # Odstranění všech obrázků z frame
        for widget in frame.winfo_children():
            widget.destroy()

        # Vytvoření nových frame pro řádky
        current_row = 0
        current_col = 0
        row_frame = None

        for i, url in enumerate(urls):
            if current_col % self.obrazky_na_radek == 0:
                row_frame = tk.Frame(frame)
                row_frame.pack(fill=tk.X)
                current_col = 0

            # Vytvoření frame pro obrázek
            img_frame = tk.Frame(row_frame)
            img_frame.grid(row=0, column=current_col, padx=5, pady=5)
            current_col += 1

            # Checkbox
            img_var = self.image_check_vars[kod][i]
            chk = tk.Checkbutton(
                img_frame,
                variable=img_var,
                command=lambda k=kod: self.update_product_check(k)
            )
            chk.pack()

            # Label s obrázkem
            label = tk.Label(img_frame, image=self.img_refs[kod][i])
            label.image = self.img_refs[kod][i]
            label.pack()
            label.bind("<Button-1>", lambda e, var=img_var: var.set(not var.get()))

    def _on_mousewheel(self, event):
        """Zpracování scrollování myší s akcelerací."""
        scroll_amount = int(-1 * (event.delta / 40))
        self.canvas.yview_scroll(scroll_amount, "units")

    def combo_selected(self, event):
        """Zpracuje výběr dodavatele a počtu produktů."""
        self.vybrany_dodavatel = self.combo_dodavatel.get()
        info = DODAVATELE[self.vybrany_dodavatel]
        self.vybrany_dodavatel_kod = info["kod"]
        self.vybrana_funkce = info["funkce"]

        print(
            f"[DEBUG] Vybrán dodavatel: {self.vybrany_dodavatel}, kód: {self.vybrany_dodavatel_kod}, počet: {self.buffer_size}")

        # Zobrazit černou překryvnou obrazovku
        self.show_overlay()

        # Vytvořit loading screen (bude nad černou obrazovkou)
        self.loading_screen = LoadingScreen(self.root)
        self.root.update()  # Force update to show loading screen immediately

        # Zakázat UI prvky během načítání
        self.combo_dodavatel.config(state='disabled')
        self.combo_pocet.config(state='disabled')
        self.combo_obrazky_na_radek.config(state='disabled')
        self.chk_all.config(state='disabled')

        # Spustit načítání v samostatném vlákně
        loading_thread = threading.Thread(target=self.load_products_thread, daemon=True)
        loading_thread.start()

    def show_overlay(self):
        """Zobrazí černou překryvnou obrazovku a deaktivuje UI"""
        self.overlay = tk.Canvas(self.root, bg='black', highlightthickness=0)
        self.overlay.place(x=0, y=0, relwidth=1, relheight=1)

        # Opraveno: Pro Canvas používáme jiný způsob pro zvednutí nad ostatní widgety
        self.overlay.tag_raise(tk.ALL)  # Místo self.overlay.lift()

        # Přidat průhlednost (volitelné)
        try:
            self.overlay.attributes('-alpha', 0.7)
        except:
            pass  # Některé platformy nepodporují průhlednost

    def hide_overlay(self):
        """Skryje černou překryvnou obrazovku"""
        if hasattr(self, 'overlay') and self.overlay:
            self.overlay.destroy()
            self.overlay = None

    def load_products_thread(self):
        """Thread for loading products to keep UI responsive"""
        try:
            # Připojení k databázi
            if not self.connect_to_database():
                self.root.after(0, self.loading_screen.close)
                return

            if not self.check_database_structure():
                self.close_database()
                self.root.after(0, self.loading_screen.close)
                return

            # Získání ignorovaných kódů pro tohoto dodavatele
            ignored_codes = self.ignored_codes.get(self.vybrany_dodavatel_kod, [])

            # Před hlavním dotazem - s explicitní kolací
            self.cursor.execute("""
                CREATE TABLE #IgnoredCodes (
                    SivCode VARCHAR(50) COLLATE DATABASE_DEFAULT
                )
            """)

            # Vložení ignorovaných kódů
            if ignored_codes:
                self.cursor.executemany("INSERT INTO #IgnoredCodes VALUES (?)",
                                        [(code,) for code in ignored_codes])

            # Hlavní dotaz
            query = f"""
                SELECT TOP {self.buffer_size} SivCode, SivName 
                FROM [{self.table_name}] 
                WHERE [{self.column_mapping['supplier']}] = ?
                AND ([{self.column_mapping['notes']}] IS NULL OR [{self.column_mapping['notes']}] = '')
                AND ([{self.column_mapping['pairing']}] IS NOT NULL AND [{self.column_mapping['pairing']}] <> '')
                AND NOT EXISTS (
                    SELECT 1 FROM #IgnoredCodes WHERE SivCode = [{self.table_name}].[{self.column_mapping['code']}] COLLATE DATABASE_DEFAULT
                ) ORDER BY NEWID()
            """
            print(f"[DEBUG] Provádím dotaz: {query}")
            print(f"[DEBUG] Parametry: {[self.vybrany_dodavatel_kod]}")

            self.cursor.execute(query, [self.vybrany_dodavatel_kod])
            self.filtrovane_produkty = [
                {'SivCode': row.SivCode, 'SivName': row.SivName}
                for row in self.cursor.fetchall()
            ]

            print(f"[DEBUG] Načteno {len(self.filtrovane_produkty)} produktů (ignorováno {len(ignored_codes)})")

            # Uzavření databáze
            self.close_database()

            if not self.filtrovane_produkty:
                self.root.after(0, lambda: messagebox.showinfo("Info", "Žádné produkty k doplnění."))
                self.root.after(0, self.loading_screen.close)
                return

            # Vyčištění GUI
            self.root.after(0, self.clear_gui)

            self.produkty_k_zpracovani = self.filtrovane_produkty[:]
            self.produkt_widgety = {}
            self.produkt_check_vars = {}
            self.image_check_vars = {}
            self.img_refs = {}
            self.all_check_var.set(False)

            # Spuštění asynchronního načítání obrázků
            self.start_async_image_loading()

        except Exception as e:
            print(f"[CHYBA] Při načítání produktů: {e}")
            self.root.after(0, lambda: messagebox.showerror("Chyba", f"Chyba při načítání produktů:\n{e}"))
            self.root.after(0, self.loading_screen.close)
            self.root.after(0, self.hide_overlay)
            self.close_database()

    def clear_gui(self):
        """Clear the GUI in the main thread"""
        for widget in self.inner_frame.winfo_children():
            widget.destroy()

    def start_async_image_loading(self):
        """Spustí asynchronní načítání obrázků s optimalizovaným počtem vláken."""
        if not self.loading_active:
            self.loading_active = True
            print(f"[THREAD] Spouštím {self.max_threads} vláken")

            for _ in range(min(self.max_threads, len(self.produkty_k_zpracovani))):
                if self.produkty_k_zpracovani:
                    produkt = self.produkty_k_zpracovani.pop(0)
                    t = threading.Thread(target=self.load_product_images, args=(produkt,))
                    t.daemon = True
                    t.start()
                    self.loading_threads.append(t)

            # Pravidelně kontrolovat stav
            self.root.after(500, self.check_threads)

    def check_threads(self):
        """Kontroluje stav načítacích vláken a spouští nová podle potřeby."""
        # Odstranění ukončených vláken
        self.loading_threads = [t for t in self.loading_threads if t.is_alive()]

        free_slots = self.max_threads - len(self.loading_threads)

        # Spuštění nových vláken pro volné sloty
        for _ in range(min(free_slots, len(self.produkty_k_zpracovani))):
            if self.produkty_k_zpracovani:
                produkt = self.produkty_k_zpracovani.pop(0)
                t = threading.Thread(target=self.load_product_images, args=(produkt,))
                t.daemon = True
                t.start()
                self.loading_threads.append(t)

        # Kontrola dokončení
        if not self.loading_threads and not self.produkty_k_zpracovani:
            self.loading_active = False
            print("[THREAD] Všechna vlákna dokončena")
            self.root.after(0, self.enable_ui_elements)
            self.root.after(0, self.loading_screen.close)
            self.root.after(0, self.hide_overlay)
        else:
            # Plánování další kontroly
            self.root.after(200, self.check_threads)

    def enable_ui_elements(self):
        """Re-enable UI elements after loading is complete"""
        self.combo_dodavatel.config(state='readonly')
        self.combo_pocet.config(state='readonly')
        self.combo_obrazky_na_radek.config(state='readonly')
        self.chk_all.config(state='normal')

    def load_product_images(self, produkt):
        """Načte obrázky pro produkt ve vlákně."""
        try:
            kod = produkt['SivCode']
            print(f"[THREAD] Načítám obrázky pro produkt: {kod}")

            # ZÍSKÁNÍ FUNKCE PRO VYBRANÉHO DODAVATELE
            funkce_pro_dodavatele = self.vybrana_funkce

            if not funkce_pro_dodavatele:
                print(f"[CHYBA] Pro dodavatele {self.vybrany_dodavatel_kod} není definována funkce")
                return

            # Získání URL obrázků pomocí funkce pro daného dodavatele
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            urls = loop.run_until_complete(funkce_pro_dodavatele(kod))
            loop.close()

            # Pokud nejsou žádné obrázky, přidáme do ignore listu
            if not urls:
                print(f"[INFO] Žádné obrázky pro produkt {kod}, přidávám do ignorovaných")
                self.add_ignored_code(self.vybrany_dodavatel_kod, kod)
                return

            # Zobraz produkt pouze pokud má obrázky
            self.root.after(0, lambda: self.display_product_with_images(produkt))

            # Načti a zobraz obrázky
            for url in urls:
                try:
                    r = requests.get(url, timeout=10)

                    # Zkontroluj, zda odpověď obsahuje obrázek
                    if 'image' not in r.headers.get('Content-Type', '').lower():
                        print(f"[INFO] Přeskočeno (není obrázek): {url}")
                        continue

                    try:
                        img = Image.open(io.BytesIO(r.content))
                        img.verify()  # Ověří validitu obrázku
                        img = Image.open(io.BytesIO(r.content))  # Nutno znovu otevřít po verify
                        img.thumbnail((300, 300))
                        photo = ImageTk.PhotoImage(img)
                    except Exception as e:
                        print(f"[INFO] Chyba při zpracování obrázku {url}: {e}")
                        continue

                    # Přidej obrázek do GUI
                    self.root.after_idle(self.add_single_image, produkt, url, photo)
                except Exception as e:
                    print(f"[CHYBA] Obrázek {url} nelze načíst: {e}")

        except Exception as e:
            print(f"[CHYBA] Při načítání obrázků: {e}")

    def display_product_with_images(self, produkt):
        """Zobrazí základní informace o produktu."""
        kod = produkt['SivCode']
        nazev = produkt.get('SivName', "")

        # Frame pro celý produkt
        frame_produkt = tk.LabelFrame(
            self.inner_frame,
            text=f"{kod} - {nazev}",
            font=("Arial", 12, "bold"),
            padx=10,
            pady=10,
        )
        frame_produkt.pack(fill=tk.X, padx=10, pady=5, ipadx=5, ipady=5)
        frame_produkt.grid_columnconfigure(0, weight=1)

        # Checkbox pro výběr všech obrázků v produktu
        var_produkt = tk.BooleanVar(value=True) # zaksrtnuty checkbox
        self.produkt_check_vars[kod] = var_produkt

        chk_produkt = tk.Checkbutton(
            frame_produkt,
            text="Vybrat všechny obrázky",
            variable=var_produkt,
            font=("Arial", 14, "bold"),
            command=lambda k=kod: self.toggle_product_images(k)
        )
        chk_produkt.grid(row=0, column=0, sticky=tk.W, pady=(0, 10))

        # Frame pro obrázky
        frame_obrazky = tk.Frame(frame_produkt)
        frame_obrazky.grid(row=1, column=0, sticky=tk.W)

        # Uložení widgetů
        self.produkt_widgety[kod] = {
            'frame': frame_produkt,
            'images_frame': frame_obrazky,
            'image_vars': [],
            'urls': [],
            'produkt': produkt
        }
        self.image_check_vars[kod] = []

        # Aktualizovat GUI
        self.canvas.update_idletasks()

    def ignore_product(self, kod):
        """Přidá produkt do seznamu ignorovaných."""
        self.add_ignored_code(self.vybrany_dodavatel_kod, kod)
        if kod in self.produkt_widgety:
            self.produkt_widgety[kod]['frame'].destroy()
            del self.produkt_widgety[kod]
        messagebox.showinfo("Info", f"Produkt {kod} byl přidán do ignorovaných")

    def add_single_image(self, produkt, url, photo):
        """Přidá jeden načtený obrázek k produktu."""
        kod = produkt['SivCode']

        if kod not in self.produkt_widgety:
            return

        # Uložení reference
        if kod not in self.img_refs:
            self.img_refs[kod] = []
        self.img_refs[kod].append(photo)

        # Uložit URL
        self.produkt_widgety[kod]['urls'].append(url)

        # Přidat checkbox pro obrázek
        img_var = tk.BooleanVar(value=True) # Základně zaškrtnutý
        self.image_check_vars[kod].append(img_var)
        self.produkt_widgety[kod]['image_vars'].append(img_var)

        # Reorganizovat obrázky podle aktuálního nastavení
        self.reorganize_images(
            self.produkt_widgety[kod]['images_frame'],
            self.produkt_widgety[kod]['urls'],
            kod
        )

        # Okamžitá aktualizace GUI
        self.root.update_idletasks()

    def toggle_all(self):
        """Vybere nebo zruší výběr všech obrázků u všech produktů."""
        select = self.all_check_var.get()
        for kod in self.produkt_check_vars:
            self.produkt_check_vars[kod].set(select)
            self.toggle_product_images(kod, select)

    def toggle_product_images(self, kod, value=None):
        """Vybere nebo zruší výběr všech obrázků v produktu."""
        if value is None:
            value = self.produkt_check_vars[kod].get()

        for var in self.image_check_vars[kod]:
            var.set(value)

    def update_product_check(self, kod):
        """Aktualizuje stav checkboxu produktu na základě obrázků."""
        # Zkontrolovat, zda stále existují image_vars
        if kod not in self.image_check_vars or not self.image_check_vars[kod]:
            return

        all_checked = all(var.get() for var in self.image_check_vars[kod])
        any_checked = any(var.get() for var in self.image_check_vars[kod])

        if all_checked:
            self.produkt_check_vars[kod].set(True)
        elif any_checked:
            # Pro částečný výběr necháme checkbox v "částečném" stavu
            pass
        else:
            self.produkt_check_vars[kod].set(False)

    def potvrdit_vse(self):
        """Potvrdí všechny vybrané produkty a uloží je do databáze."""
        if not self.connect_to_database():
            return

        products_to_remove = []
        try:
            for kod, data in self.produkt_widgety.items():
                vybrane_urls = [
                    url for i, url in enumerate(data['urls'])
                    if i < len(data['image_vars']) and data['image_vars'][i].get()
                ]

                if vybrane_urls:
                    produkt = data['produkt']
                    zapis = ";\n".join(vybrane_urls) + ";"

                    query = f"""
                        UPDATE [{self.table_name}] 
                        SET [{self.column_mapping['notes']}] = ? 
                        WHERE [{self.column_mapping['code']}] = ?
                    """
                    self.cursor.execute(query, (zapis, produkt['SivCode']))
                    products_to_remove.append(kod)
                else:
                    # ZMĚNA: Pokud nebyly vybrány žádné obrázky, přidat do ignorovaných
                    self.add_ignored_code(self.vybrany_dodavatel_kod, kod)
                    products_to_remove.append(kod)

            self.conn.commit()
            messagebox.showinfo("Info", "Všechny vybrané produkty byly uloženy.")

            # Odstranění uložených produktů z GUI
            for kod in products_to_remove:
                if kod in self.produkt_widgety:
                    self.produkt_widgety[kod]['frame'].destroy()
                    del self.produkt_widgety[kod]
                if kod in self.img_refs:
                    del self.img_refs[kod]

        except Exception as e:
            print(f"[CHYBA] Při ukládání do DB: {e}")
            messagebox.showerror("Chyba", f"Chyba při ukládání:\n{e}")
        finally:
            self.close_database()

            # Automaticky načíst další produkty
            if self.vybrany_dodavatel and self.vybrany_dodavatel_kod:
                self.combo_selected(None)
            else:
                self.hide_overlay()

    def zrusit_vse(self):
        """Zruší všechny produkty bez uložení."""
        for kod in list(self.produkt_widgety.keys()):
            self.produkt_widgety[kod]['frame'].destroy()
            del self.produkt_widgety[kod]
            if kod in self.img_refs:
                del self.img_refs[kod]
        self.hide_overlay()  # Přidáno skrytí overlay
        messagebox.showinfo("Info", "Všechny produkty byly zrušeny.")

    def close_database(self):
        """Uzavře databázové připojení."""
        if self.conn:
            try:
                self.conn.close()
                print("[DEBUG] Databázové připojení uzavřeno.")
            except:
                pass
            finally:
                self.conn = None
                self.cursor = None


if __name__ == "__main__":
    print("[DEBUG] Spouštím aplikaci...")
    root = tk.Tk()
    app = ObrFormApp(root)
    root.mainloop()