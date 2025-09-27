import os
import json
import sqlite3
import threading
import time
import requests
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

DB_PATH = "queue.sqlite3"
IGNORE_FILE = "ignoreSivCode.json"

# lokální cache obrázků (používá se při „Odklikávat“)
CACHE_DIR = Path("cache_images")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# počet vláken pro scraping (lze přepsat env proměnnou QUEUE_WORKERS)
DEFAULT_QUEUE_WORKERS = int(os.getenv("QUEUE_WORKERS", "5"))

# omezit debug spam z HTTP klienta
logging.getLogger("urllib3").setLevel(logging.WARNING)

# === SCHÉMA TABULKY FRONTY (MUSÍ BÝT NAHOŘE, PŘED ensure_db) ===
QUEUE_SCHEMA = """
CREATE TABLE IF NOT EXISTS queue (
    SivCode      TEXT PRIMARY KEY,
    SivCode2     TEXT,
    SivName      TEXT,
    SivComId     TEXT,
    image_urls   TEXT,   -- JSON list[str]
    image_paths  TEXT,   -- JSON list[str] - cesty na disk (cache)
    zpracovano   INTEGER DEFAULT 0,  -- bool 0/1
    ignorovat    INTEGER DEFAULT 0   -- bool 0/1
);
CREATE INDEX IF NOT EXISTS idx_queue_flags ON queue(zpracovano, ignorovat);
"""

def _open():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def _migrate_schema(conn: sqlite3.Connection):
    """
    Jemná migrace – když ve starší DB chybí nové sloupce, přidáme je.
    """
    cur = conn.execute("PRAGMA table_info(queue)")
    cols = {row[1] for row in cur.fetchall()}
    if "image_paths" not in cols:
        conn.execute("ALTER TABLE queue ADD COLUMN image_paths TEXT")
    # případně další ALTERy sem…
    conn.commit()

def ensure_db():
    """
    Vytvoří tabulku fronty, pokud neexistuje, a provede lehké migrace.
    """
    conn = _open()
    try:
        # vytvoření (idempotentní)
        for stmt in QUEUE_SCHEMA.strip().split(";"):
            s = stmt.strip()
            if s:
                conn.execute(s)
        # migrace (doplnění nových sloupců)
        _migrate_schema(conn)
        conn.commit()
    finally:
        conn.close()



def db_exists() -> bool:
    return os.path.exists(DB_PATH)

def _load_ignore():
    try:
        if os.path.exists(IGNORE_FILE):
            with open(IGNORE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _save_ignore(d):
    try:
        with open(IGNORE_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=4)
    except Exception:
        pass

def add_ignored_code(supplier_code: str, siv_code: str):
    data = _load_ignore()
    arr = data.get(supplier_code, [])
    if siv_code not in arr:
        arr.append(siv_code)
        data[supplier_code] = arr
        _save_ignore(data)

# --------- importy scraperů (reused z projektu) ----------
# get_all_suppliers_product_images vrací list URL dle dodavatele / všech dodavatelů
from allSuppliersHandler import get_all_suppliers_product_images  # async i sync wrappery viz modul
# Pozn.: používáme stávající logiku vašich scraperů. :contentReference[oaicite:4]{index=4}

# --------- dotahování kandidátů ze SQL Serveru (jen "Všechny dodavatele") ----------
def fetch_all_missing_from_sqlserver():
    """
    Vrátí list dictů: {SivCode, SivName, SivCode2, SivComId} pro VŠECHNY produkty bez obrázku.
    Používá stejné filtry jako v main.py, jen bez TOP a náhodného řazení.
    """
    import pyodbc
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv()

    table_name = os.getenv("DB_TABLE")
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
    rows_out = []
    conn = None
    try:
        conn = pyodbc.connect(conn_str)
        cur = conn.cursor()

        # ignorované kódy (trvalé)
        ignore_map = _load_ignore()
        ignored_codes = set()
        # posbíráme všechny ignorované kódy ze všech dodavatelů
        for supplier_code, arr in ignore_map.items():
            for code in arr:
                ignored_codes.add(code)

        # vytvoříme temp tabulku s ignored
        cur.execute("IF OBJECT_ID('tempdb..#IgnoredCodes') IS NOT NULL DROP TABLE #IgnoredCodes;")
        cur.execute("CREATE TABLE #IgnoredCodes (SivCode VARCHAR(50) COLLATE DATABASE_DEFAULT)")
        if ignored_codes:
            cur.executemany("INSERT INTO #IgnoredCodes VALUES (?)", [(c,) for c in ignored_codes])

        # dotaz pro "Všechny dodavatele" bez TOP
        q = f"""
            SELECT 
                [StoItemCom].SivCode,
                [StoItemCom].SivName,
                [StoItemCom].SivCode2,
                [StoItemCom].SivComId
            FROM [{table_name}] as StoItemCom
            JOIN StoItem with(nolock)   ON (StoItemCom.SivStiId = StoItem.StiId)
            LEFT JOIN SCategory with(nolock) ON (StoItem.StiScaId = SCategory.ScaId)
            WHERE StoItemCom.SivOrdVen = 1
              AND NOT EXISTS (
                SELECT TOP 1 1 FROM Attach with(nolock) 
                WHERE AttSrcId = StiId AND AttPedId = 52 AND (AttTag like 'sys-gal%' OR AttTag = 'sys-thu' OR AttTag = 'sys-enl')
              )
              AND StoItem.StiPLPict IS NULL
              AND SCategory.ScaId NOT IN (8843,8388,8553,8387,6263,8231,7575,5203,2830,269,1668,2391,1634,7209)
              AND (StoItemCom.SivNotePic IS NULL OR StoItemCom.SivNotePic = '')
              AND (StoItemCom.SivStiId IS NOT NULL AND StoItemCom.SivStiId <> '')
              AND StoItem.StiHide = 0
              AND StoItem.StiHideI = 0
              AND NOT EXISTS (
                SELECT 1 FROM #IgnoredCodes WHERE SivCode = [StoItemCom].[SivCode] COLLATE DATABASE_DEFAULT
              )
        """
        cur.execute(q)
        rows = cur.fetchall()
        for r in rows:
            rows_out.append({
                "SivCode": r.SivCode,
                "SivName": r.SivName,
                "SivCode2": r.SivCode2,
                "SivComId": r.SivComId,
            })
    finally:
        try:
            if conn:
                conn.close()
        except:
            pass
    return rows_out

# --------- enqueue & diff ----------
def upsert_products(products):
    """
    products: list[dict] se sloupci: SivCode, SivName, SivCode2, SivComId
    Nové přidá, existující ponechá, jen když přibyl nový produkt, vloží jej.
    """
    ensure_db()
    conn = _open()
    try:
        cur = conn.cursor()
        cur.execute("BEGIN")
        for p in products:
            cur.execute("""
                INSERT OR IGNORE INTO queue (SivCode, SivCode2, SivName, SivComId, image_urls, zpracovano, ignorovat)
                VALUES (?, ?, ?, ?, '[]', 0, 0)
            """, (p.get("SivCode"), p.get("SivCode2"), p.get("SivName"), p.get("SivComId")))
        conn.commit()
    finally:
        conn.close()

def diff_and_enqueue():
    """
    Stáhne aktuální seznam kandidátů ze SQL a doplní do lokální queue nové kusy.
    """
    products = fetch_all_missing_from_sqlserver()
    upsert_products(products)
    return len(products)

# --------- processing (scraping & plnění image_urls) ----------
def _download_and_cache_images(code: str, urls: list[str]) -> list[str]:
    """Stáhne URL do cache_images/<SivCode>/ a vrátí list lokálních cest."""
    if not urls:
        return []
    folder = CACHE_DIR / code
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, u in enumerate(urls, 1):
        try:
            r = requests.get(u, timeout=15)
            ct = (r.headers.get("Content-Type") or "").lower()
            if r.status_code == 200 and "image" in ct:
                ext = ".jpg"
                if "png" in ct: ext = ".png"
                elif "webp" in ct: ext = ".webp"
                elif "jpeg" in ct: ext = ".jpg"
                out = folder / f"{i}{ext}"
                out.write_bytes(r.content)
                paths.append(str(out))
        except Exception:
            continue
    return paths

def _save_urls_for(code: str, urls: list):
    """Zapíše URL + lokální cesty; když nic, nastaví ignorovat=1."""
    paths = _download_and_cache_images(code, urls)
    conn = _open()
    try:
        js_urls = json.dumps(urls or [], ensure_ascii=False)
        js_paths = json.dumps(paths or [], ensure_ascii=False)
        ignor = 0 if (urls and paths) else 1  # když nic nestáhlo, ignorovat
        conn.execute("UPDATE queue SET image_urls=?, image_paths=?, ignorovat=? WHERE SivCode=?",
                     (js_urls, js_paths, ignor, code))
        conn.commit()
    finally:
        conn.close()


def _get_batch_for_processing(limit=200):
    """
    Vrací kusy, které ještě nemají obrázky ani nejsou ignorované a nejsou zpracované.
    """
    conn = _open()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT SivCode, SivComId FROM queue 
            WHERE zpracovano=0 AND ignorovat=0 
              AND (image_urls IS NULL OR image_urls='[]')
            LIMIT ?
        """, (limit,))
        return [{"SivCode": r[0], "SivComId": r[1]} for r in cur.fetchall()]
    finally:
        conn.close()

def process_all_images(progress_cb=None, supplier_code_for_ignore="ALL", max_workers=None, batch_size=200):
    """
    Projde frontu a pro každý produkt bez URL dotáhne obrázky.
    Pokud žádné nesežene, zapíše do ignoreSivCode.json + nastaví ignorovat=1.

    Běží paralelně ve vláknové frontě:
      - max_workers: počet vláken (default z env QUEUE_WORKERS nebo 5)
      - batch_size:  kolik záznamů si bere každá smyčka (default 200)
    """
    if max_workers is None or max_workers <= 0:
        max_workers = DEFAULT_QUEUE_WORKERS

    def _scrape_one(item):
        code = item["SivCode"]
        try:
            produkt_info = {"SivCode": code, "SivComId": item.get("SivComId") or ""}
            urls = []
            try:
                import asyncio
                if asyncio.iscoroutinefunction(get_all_suppliers_product_images):
                    urls = asyncio.run(get_all_suppliers_product_images(produkt_info))
                else:
                    urls = get_all_suppliers_product_images(produkt_info)
            except RuntimeError:
                urls = get_all_suppliers_product_images(produkt_info)

            urls = [u for u in urls if u] or []
            _save_urls_for(code, urls)
            if not urls:
                add_ignored_code(supplier_code_for_ignore, code)
        except Exception:
            _save_urls_for(code, [])
            add_ignored_code(supplier_code_for_ignore, code)
        finally:
            if progress_cb:
                try:
                    progress_cb(code)
                except Exception:
                    pass

    # postupné dávky, každou dávku zpracujeme paralelně
    while True:
        batch = _get_batch_for_processing(limit=batch_size)
        if not batch:
            break
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = [ex.submit(_scrape_one, item) for item in batch]
            for _ in as_completed(futures):
                pass
    return True


# --------- dávka pro odklikávání ----------
def fetch_click_batch(limit:int):
    """
    Vrací list produktů připravených k odklikávání:
      {SivCode, SivName, SivCode2, SivComId, urls: list[str], paths: list[str]}
    """
    ensure_db()
    conn = _open()
    out = []
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT SivCode, SivName, SivCode2, SivComId, image_urls, image_paths
            FROM queue
            WHERE zpracovano=0 AND ignorovat=0 
              AND image_urls IS NOT NULL AND image_urls <> '[]'
              AND image_paths IS NOT NULL AND image_paths <> '[]'
            LIMIT ?
        """, (limit,))
        for r in cur.fetchall():
            try:
                urls = json.loads(r[4] or "[]")
            except Exception:
                urls = []
            try:
                paths = json.loads(r[5] or "[]")
            except Exception:
                paths = []
            out.append({
                "SivCode": r[0],
                "SivName": r[1],
                "SivCode2": r[2],
                "SivComId": r[3],
                "urls": urls,
                "paths": paths
            })
    finally:
        conn.close()
    return out


def mark_processed(codes:list[str]):
    if not codes:
        return
    conn = _open()
    try:
        cur = conn.cursor()
        cur.execute("BEGIN")
        for c in codes:
            cur.execute("UPDATE queue SET zpracovano=1 WHERE SivCode=?", (c,))
        conn.commit()
    finally:
        conn.close()
