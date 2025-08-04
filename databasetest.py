import pyodbc
import pandas as pd


def main():
    # Nastavení připojení - upravte podle potřeby
    server = '192.168.1.14'
    database = 'I6ABCtest'
    username = 'test'
    password = 'test'

    try:
        # Vytvoření připojovacího řetězce
        conn_str = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'

        # Připojení k databázi
        with pyodbc.connect(conn_str) as conn:
            print("Úspěšně připojeno k databázi!")

            # SQL dotaz
            query = "SELECT TOP 5 * FROM dbo.StoItemCom"

            # Načtení dat do pandas DataFrame pro lepší zobrazení
            df = pd.read_sql(query, conn)

            # Výpis výsledků
            print("\nPrvních 5 záznamů z tabulky dbo.StoItemCom:")
            print(df)

    except Exception as e:
        print(f"Došlo k chybě: {e}")
    finally:
        input("\nStiskněte Enter pro ukončení...")


if __name__ == "__main__":
    main()