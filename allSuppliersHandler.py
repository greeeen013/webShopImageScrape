import asyncio
from ShopScraper import *
from ShopSelenium import *

# Seznam dodavatelů, kteří se mají ignorovat v režimu "Všechny dodavatele"
IGNORED_SUPPLIERS = ["319004"]  # DCS (nekvalitní obrázky)


async def get_all_suppliers_product_images(produkt_info):
    """
    Získá obrázky produktu od všech dostupných dodavatelů
    """
    siv_code = produkt_info['SivCode']
    siv_com_id = produkt_info.get('SivComId', '')  # ZMĚNA: Bezpečné získání SivComId

    # Mapování kódů dodavatelů na funkce
    supplier_functions = {
        "348651": octo_get_product_images,  # octo it
        "268493": directdeal_get_product_images,  # directdeal/everit
        "161784": api_get_product_images,  # api
        "351191": easynotebooks_get_product_images,  # NetFactory/easynotebooks
        "165463": kosatec_get_product_images,  # Kosatec
        "319004": dcs_get_product_images,  # Dcs (nekvalitní) - bude ignorován
        "169701": incomgroup_get_product_images,  # IncomGroup
        "190157": wortmann_get_product_images,  # Wortmann
        "115565": wave_get_product_images,  # Wave (selenium)
        "340871": notebooksbilliger_get_product_images,  # notebooksbilliger (selenium)
        "312585": fourcom_get_product_images,  # fourcom (selenium)
        "104584": komputronik_get_product_images,  # Komputronik (selenium)
    }

    # Pokud má produkt přiřazeného konkrétního dodavatele, použijeme pouze jeho funkci
    if siv_com_id and siv_com_id in supplier_functions and siv_com_id not in IGNORED_SUPPLIERS:
        funkce = supplier_functions[siv_com_id]
        try:
            if asyncio.iscoroutinefunction(funkce):
                return await funkce(siv_code)
            else:
                return funkce(siv_code)
        except Exception as e:
            print(f"[CHYBA] Pro dodavatele {siv_com_id}: {e}")
            return []

    # Pokud není přiřazen konkrétní dodavatel, zkusíme všechny dostupné
    all_urls = []
    for supplier_code, funkce in supplier_functions.items():
        if supplier_code in IGNORED_SUPPLIERS:
            continue

        try:
            if asyncio.iscoroutinefunction(funkce):
                urls = await funkce(siv_code)
            else:
                urls = funkce(siv_code)

            if urls:
                all_urls.extend(urls)
                print(f"[INFO] Nalezeny obrázky od dodavatele {supplier_code}: {len(urls)}")
                break  # Pokud najdeme obrázky u jednoho dodavatele, nezkoušíme další
        except Exception as e:
            print(f"[INFO] Dodavatel {supplier_code} neúspěšný: {e}")
            continue

    return all_urls