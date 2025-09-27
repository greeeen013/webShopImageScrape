# sqlCheck.py
import os
import sqlite3
import json
from pathlib import Path

DB_PATH = "queue.sqlite3"

def open_db(db_path: str):
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Soubor DB '{db_path}' nebyl nalezen.")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def normalize_pattern(user_input: str):
    """
    Pokud zadáš * nebo % použije se LIKE.
    Jinak se hledá přesnou shodou (=).
    Vrací (query_sql, params, used_like: bool)
    """
    s = user_input.strip()
    if not s:
        # prázdný dotaz → nic
        return None, None, False

    if "*" in s or "%" in s:
        s = s.replace("*", "%")
        return (
            "SELECT SivCode, SivName, image_urls, image_paths "
            "FROM queue WHERE SivCode LIKE ?",
            (s,),
            True,
        )
    else:
        # přesná shoda
        return (
            "SELECT SivCode, SivName, image_urls, image_paths "
            "FROM queue WHERE SivCode = ?",
            (s,),
            False,
        )

def parse_json_list(raw):
    if not raw:
        return []
    try:
        val = json.loads(raw)
        if isinstance(val, list):
            return [str(x) for x in val]
    except Exception:
        pass
    return []

def main():
    print("=== sqlCheck.py – dotaz na produkty ve frontě (queue.sqlite3) ===")
    siv = input("Zadej SivCode (můžeš použít * nebo % pro LIKE): ").strip()

    sql, params, used_like = normalize_pattern(siv)
    if not sql:
        print("Nebyl zadán žádný výraz. Konec.")
        return

    try:
        conn = open_db(DB_PATH)
    except FileNotFoundError as e:
        print(f"[CHYBA] {e}")
        return

    try:
        cur = conn.execute(sql, params)
        rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        print("Nenalezen žádný záznam.")
        return

    print(f"Nalezeno záznamů: {len(rows)} (dotaz {'LIKE' if used_like else '='})")
    print("-" * 80)
    for i, r in enumerate(rows, 1):
        sivcode = r["SivCode"]
        name = r["SivName"] or ""
        urls = parse_json_list(r["image_urls"])
        paths = parse_json_list(r["image_paths"]) if "image_paths" in r.keys() else []

        print(f"[{i}] SivCode : {sivcode}")
        print(f"    SivName : {name}")

        if urls:
            print("    URL:")
            for u in urls:
                print(f"      - {u}")
        else:
            print("    URL: (žádné)")

        if paths:
            print("    Lokální cesty:")
            for p in paths:
                # zvýrazni, jestli soubor existuje
                exists = "OK" if Path(p).exists() else "NEEXISTUJE"
                print(f"      - {p}   [{exists}]")
        print("-" * 80)

if __name__ == "__main__":
    main()
