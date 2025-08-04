
# ObrFormApp

Tento projekt je aplikace pro správu obrázků produktů, která umožňuje výběr, potvrzení a zrušení produktů. Aplikace je postavena na Pythonu a využívá knihovnu `tkinter` pro GUI.

## Požadavky

Před spuštěním aplikace je nutné nainstalovat všechny požadované balíčky uvedené v souboru `requirements.txt`. Dále je potřeba vytvořit soubor `.env` s potřebnými konfiguracemi.

### Instalace požadavků

1. Ujistěte se, že máte nainstalovaný Python (doporučená verze: 3.8 nebo vyšší).
2. Nainstalujte požadované balíčky pomocí příkazu:

   ```bash
   pip install -r requirements.txt
   ```

### Konfigurace `.env` souboru

V kořenovém adresáři projektu vytvořte soubor `.env` a přidejte následující konfigurace:

```env
DB_SERVER=<adresa_hostitele_databáze>
DB_DATABASE=<název_databáze>
DB_TABLE=<název_tabulky>
DB_USERNAME=<login_do_databáze>
DB_PASSWORD=<heslo_do_databáze>
```

Nahraďte `<adresa_hostitele_databáze>`, `<login_do_databáze>`, `<heslo_do_databáze>`, `<název_databáze>`, `<název_tabulky>` odpovídajícími hodnotami podle vaší databázové konfigurace.

## Spuštění aplikace

Po instalaci požadavků a nastavení `.env` souboru můžete aplikaci spustit pomocí příkazu:

```bash
python main.py
```