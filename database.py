import os
import sqlite3
import json
import pyodbc 
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class DatabaseManager:
    def __init__(self, db_path="queue.sqlite3"):
        self.sqlite_path = db_path
        # Ensure directory exists
        db_dir = os.path.dirname(self.sqlite_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
            
        self._ensure_sqlite_db()
        
    def _get_mssql_connection(self):
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
        return pyodbc.connect(conn_str)

    def _ensure_sqlite_db(self):
        conn = sqlite3.connect(self.sqlite_path)
        cursor = conn.cursor()
        
        # Main queue table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS queue (
                SivCode TEXT PRIMARY KEY,
                SivCode2 TEXT,
                SivName TEXT,
                SivComId TEXT,
                image_urls TEXT DEFAULT '[]',
                image_paths TEXT DEFAULT '[]',
                status TEXT DEFAULT 'pending', -- pending, searched, seen
                ignored INTEGER DEFAULT 0,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create index
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON queue(status)")
        
        conn.commit()
        conn.close()

    def get_queue_connection(self):
        """Returns a connection to the SQLite queue database."""
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn

    def fetch_candidates_from_mssql(self, supplier_ids=None):
        """
        Fetches products from MSSQL that don't have images.
        supplier_ids: List of supplier IDs to filter by. If None, fetches for all enabled logic.
        """
        table_name = os.getenv("DB_TABLE")
        
        # Construct the query based on the logic provided in queueScrapeDatabase.py
        # but cleaner.
        
        # If specific suppliers are requested
        supplier_filter = ""
        if supplier_ids:
            ids_str = ",".join([f"'{s}'" for s in supplier_ids])
            supplier_filter = f"AND SivComId IN ({ids_str})"

        query = f"""
            SELECT 
                [StoItemCom].SivCode,
                [StoItemCom].SivName,
                [StoItemCom].SivCode2,
                [StoItemCom].SivComId
            FROM [{table_name}] as StoItemCom
            JOIN StoItem with(nolock) ON (StoItemCom.SivStiId = StoItem.StiId)
            LEFT JOIN SCategory with(nolock) ON (StoItem.StiScaId = SCategory.ScaId)
            WHERE StoItemCom.SivOrdVen = 1
              AND NOT EXISTS (
                SELECT TOP 1 1 FROM Attach with(nolock) 
                WHERE AttSrcId = StiId AND AttPedId = 52 AND (AttTag like 'sys-gal%' OR AttTag = 'sys-thu' OR AttTag = 'sys-enl')
              )
              AND StoItem.StiPLPict IS NULL
              AND SCategory.ScaId NOT IN (8843,8388,8553,8387,6263,8231,7575,5203,2830,269,1668,2391,1634,7209,7150,7848)
              AND (StoItemCom.SivNotePic IS NULL OR StoItemCom.SivNotePic = '')
              AND (StoItemCom.SivStiId IS NOT NULL AND StoItemCom.SivStiId <> '')
              AND StoItem.StiHide = 0
              AND StoItem.StiHideI = 0
              {supplier_filter}
        """
        
        try:
            conn = self._get_mssql_connection()
            cursor = conn.cursor()
            print(f"--- [MSSQL DEBUG] EXECUTING QUERY ---\n{query}\n---------------------------------------")
            cursor.execute(query)
            rows = cursor.fetchall()
            print(f"--- [MSSQL DEBUG] RETURNED {len(rows)} ROWS ---")
            if rows:
                print(f"--- [MSSQL DEBUG] SAMPLE ROW: {tuple(rows[0])} ---")
            
            results = []
            for row in rows:
                results.append({
                    "SivCode": row.SivCode,
                    "SivName": row.SivName,
                    "SivCode2": row.SivCode2,
                    "SivComId": row.SivComId
                })
            conn.close()
            return results
        except Exception as e:
            print(f"MSSQL Error: {e}")
            return []

    def enqueue_products(self, products):
        """Adds products to SQLite queue, ignoring duplicates."""
        conn = self.get_queue_connection()
        cursor = conn.cursor()
        
        count = 0
        for p in products:
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO queue (SivCode, SivCode2, SivName, SivComId, status)
                    VALUES (?, ?, ?, ?, 'pending')
                """, (p['SivCode'], p.get('SivCode2'), p.get('SivName'), p['SivComId']))
                if cursor.rowcount > 0:
                    count += 1
            except Exception as e:
                print(f"Error enqueuing {p.get('SivCode')}: {e}")
        
        conn.commit()
        conn.close()
        return count

    def get_pending_tasks(self, limit=100):
        """Get items that need scraping."""
        conn = self.get_queue_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM queue WHERE status='pending' AND ignored=0 LIMIT ?", (limit,))
        tasks = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return tasks

    def update_task_results(self, siv_code, urls, paths, status='searched'):
        """Update a task with scraping results."""
        conn = self.get_queue_connection()
        cursor = conn.cursor()
        
        urls_json = json.dumps(urls)
        paths_json = json.dumps(paths)
        
        # If no images found, maybe mark as ignored or just searched (empty)
        # The logic in previous app was: if empty -> ignored=1.
        # But user wants 'searched' checkmark. 
        # "at uz je to naslo nebo nenaslo tak tohle se zaskrtne a tzn ze znova kdyby to uzivatle spustil... se nebude prohledavat"
        
        ignored = 0
        
        cursor.execute("""
            UPDATE queue 
            SET image_urls=?, image_paths=?, status=?, ignored=?
            WHERE SivCode=?
        """, (urls_json, paths_json, status, ignored, siv_code))
        
        conn.commit()
        conn.close()

    def get_review_batch(self, limit=20, supplier_ids=None):
        """Get items ready for review (images found, not yet seen)."""
        conn = self.get_queue_connection()
        cursor = conn.cursor()
        
        supplier_filter = ""
        if supplier_ids:
             # This is a bit tricky with param substitution in IN clause in sqlite
             # simple manual construction for trusted input
             ids_str = ",".join([f"'{s}'" for s in supplier_ids])
             supplier_filter = f"AND SivComId IN ({ids_str})"

        # We only want items that HAVE images (paths not empty json array)
        query = f"""
            SELECT * FROM queue 
            WHERE status='searched' 
              AND ignored=0 
              AND image_urls != '[]'
              {supplier_filter}
            LIMIT ?
        """
        cursor.execute(query, (limit,))
        items = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return items

    def mark_as_seen(self, siv_code):
        conn = self.get_queue_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE queue SET status='seen' WHERE SivCode=?", (siv_code,))
        conn.commit()
        conn.close()
        
    def save_product_images(self, siv_code, image_urls):
        """
        Updates the product's image note field in MSSQL with the list of URLs.
        format: url1;\nurl2;\n...;
        """
        table_name = os.getenv("DB_TABLE")
        # Columns mapping based on main.py
        # 'notes': 'SivNotePic', 'code': 'SivCode'
        
        if not image_urls:
            return

        formatted_str = ";\n".join(image_urls) + ";"
        
        query = f"UPDATE [{table_name}] SET SivNotePic = ? WHERE SivCode = ?"
        
        try:
            conn = self._get_mssql_connection()
            cursor = conn.cursor()
            print(f"--- [MSSQL DEBUG] UPDATING PRODUCT {siv_code} ---")
            print(f"--- [MSSQL DEBUG] QUERY: {query}")
            print(f"--- [MSSQL DEBUG] VALUES (SivNotePic length: {len(formatted_str)}): {formatted_str[:100]}...")
            cursor.execute(query, (formatted_str, siv_code))
            conn.commit()
            print(f"--- [MSSQL DEBUG] UPDATE SUCCESS ---")
            conn.close()
            return True
        except Exception as e:
            print(f"MSSQL Save Error: {e}")
            return False

