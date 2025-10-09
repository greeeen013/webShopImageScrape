from ShopScraper import *
from ShopSelenium import *

DODAVATELE = {
    # Nová položka - Všechny dodavatele
    "Všechny dodavatele": {"kod": "ALL", "produkt_dotaz_kod": "SivCode", "funkce": None, "paralelně": True},

    # klasickej scrape
    "octo it": {"kod": "348651", "produkt_dotaz_kod": "SivCode", "funkce": octo_get_product_images, "paralelně": True},
    "directdeal/everit": {"kod": "268493", "produkt_dotaz_kod": "SivCode", "funkce": directdeal_get_product_images, "paralelně": True},
    "api": {"kod": "161784", "produkt_dotaz_kod": "SivCode", "funkce": api_get_product_images, "paralelně": True},
    "NetFactory/easynotebooks": {"kod": "351191", "produkt_dotaz_kod": "SivCode", "funkce": easynotebooks_get_product_images, "paralelně": True},
    "Kosatec": {"kod": "165463", "produkt_dotaz_kod": "SivCode", "funkce": kosatec_get_product_images, "paralelně": True},
    "Dcs (nekvalitní)": {"kod": "319004", "produkt_dotaz_kod": "SivCode", "funkce": dcs_get_product_images, "paralelně": True},
    "IncomGroup": {"kod": "169701", "produkt_dotaz_kod": "SivCode2", "funkce": incomgroup_get_product_images, "paralelně": True},
    "Wortmann": {"kod": "190157", "produkt_dotaz_kod": "SivCode", "funkce": wortmann_get_product_images, "paralelně": True},
    "AXRO GmbH": {"kod": "235880", "produkt_dotaz_kod": "SivCode", "funkce": axro_get_product_images, "paralelně": True},


    # selenium
    "Wave (selenium)": {"kod": "115565", "produkt_dotaz_kod": "SivCode", "funkce": wave_get_product_images, "paralelně": False},
    "notebooksbilliger (selenium)": {"kod": "340871", "produkt_dotaz_kod": "SivCode", "funkce": notebooksbilliger_get_product_images, "paralelně": False},
    "fourcom (selenium)": {"kod": "312585", "produkt_dotaz_kod": "SivCode", "funkce": fourcom_get_product_images, "paralelně": False},
    "Komputronik (selenium)": {"kod": "104584", "produkt_dotaz_kod": "SivCode", "funkce": komputronik_get_product_images, "paralelně": False},
    "MICHAELTELECOM AG (selenium)": {"kod": "318724", "produkt_dotaz_kod": "SivCode", "funkce": michaelag_get_product_images, "paralelně": True},
}

IGNORED_SUPPLIERS = ["319004"]