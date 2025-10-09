# mssqlCheck.py
import os
import sys
import json
import pyodbc
from dotenv import load_dotenv

def load_config():
    load_dotenv()
    cfg = {
        "server": os.getenv("DB_SERVER"),
        "database": os.getenv("DB_DATABASE"),
        "table": os.getenv("DB_TABLE"),
        "username": os.getenv("DB_USERNAME"),
        "password": os.getenv("DB_PASSWORD"),
    }
    missing = [k for k, v in cfg.items() if not v]
    if missing:
        raise RuntimeError(f"V .env chybí: {', '.join(missing)}")
    return cfg

def connect_mssql(cfg):
    # Používám stejný driver style jako v projektu (DRIVER={SQL Server})
    conn_str = (
        f"DRIVER={{SQL Server}};"
        f"SERVER={cfg['server']};"
        f"DATABASE={cfg['database']};"
        f"UID={cfg['username']};"
        f"PWD={cfg['password']};"
        "TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str)

def build_query(user_input: str):
    """
    Bez * nebo % = přesná shoda.
    Pokud řetězec obsahuje * nebo %, použije se LIKE (hvězdičky se nahradí za %).
    Vrací (sql, params, used_like)
    """
    s = (user_input or "").strip()
    if not s:
        return None, None, False
    if "*" in s or "%" in s:
        s = s.replace("*", "%")
        sql = (
            "SELECT SivCode, SivName, SivNotePic, SivComId "
            f"FROM [{os.getenv('DB_TABLE')}] WITH (NOLOCK) "
            "WHERE SivCode LIKE ?"
        )
        return sql, (s,), True
    else:
        sql = (
            "SELECT SivCode, SivName, SivNotePic, SivComId "
            f"FROM [{os.getenv('DB_TABLE')}] WITH (NOLOCK) "
            "WHERE SivCode = ?"
        )
        return sql, (s,), False

def parse_urls_from_notes(notes: str):
    """
    V projektu se zapisují URL do poznámek jako 'url1;\\nurl2;\\n...;'
    Rozparsujeme na čisté seznamy URL.
    """
    if not notes:
        return []
    raw = notes.replace("\r", "\n")
    parts = []
    for line in raw.split("\n"):
        for chunk in line.split(";"):
            chunk = chunk.strip()
            if chunk:
                parts.append(chunk)
    # odfiltruj zjevně ne-URL zbytky, ale neriskuj falešné negativy
    return parts

def main():
    print("=== mssqlCheck.py – kontrola reálné DB podle SivCode ===")
    try:
        cfg = load_config()
    except Exception as e:
        print(f"[CHYBA] {e}")
        sys.exit(1)

    siv = input("Zadej SivCode (můžeš i * nebo % pro LIKE): ").strip()
    sql, params, used_like = build_query(siv)
    if not sql:
        print("Nebyl zadán výraz. Konec.")
        return

    try:
        conn = connect_mssql(cfg)
    except Exception as e:
        print(f"[CHYBA] Nepodařilo se připojit k MSSQL: {e}")
        sys.exit(2)

    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
    except Exception as e:
        print(f"[CHYBA] Dotaz selhal: {e}")
        sys.exit(3)
    finally:
        try:
            conn.close()
        except:
            pass

    if not rows:
        print("Nenalezen žádný záznam.")
        return

    print(f"Nalezeno záznamů: {len(rows)} (dotaz {'LIKE' if used_like else '='})")
    print("-" * 80)
    for i, r in enumerate(rows, 1):
        sivcode   = getattr(r, "SivCode", None)
        sivname   = getattr(r, "SivName", None)
        notespic  = getattr(r, "SivNotePic", None)
        sivcomid  = getattr(r, "SivComId", None)  # Nový sloupec
        urls = parse_urls_from_notes(notespic)

        print(f"[{i}] SivCode : {sivcode}")
        print(f"    SivName : {sivname or ''}")
        print(f"    SivComId: {sivcomid or ''}")  # Výpis nového sloupce
        if urls:
            print("    URL:")
            for u in urls:
                print(f"      - {u}")
        else:
            print("    URL: (žádné)")
        print("-" * 80)

if __name__ == "__main__":
    main()