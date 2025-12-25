from scrapers import (
    OctoScraper, DirectDealScraper, ApiScraper, EasyNotebooksScraper, KosatecScraper, DcsScraper, 
    IncomGroupScraper, WortmannScraper, AxroScraper,
    NotebooksbilligerScraper, FourcomScraper, KomputronikScraper, WaveScraper, MichaelAgScraper,
    ComLineScraper, CyberportScraper
)

# SUPPLIERS_CONFIG maps friendly names to configuration.
# Key format: "Friendly Name"
# Values:
#   id/code: The SivComId used in MSSQL.
#   product_query_code: The column to check (SivCode or SivCode2).
#   scraper_class: The class to instantiate for scraping.
#   parallel: Boolean for parallel execution allowed.

SUPPLIERS_CONFIG = {
    "Všechny dodavatele": {
        "id": "ALL",
        "code": "ALL",
        "product_query_code": "SivCode",
        "scraper_class": None,
        "parallel": True
    },
    
    # --- Requests Scrapers ---
    "octo it": {
        "id": "348651", 
        "code": "348651",
        "product_query_code": "SivCode",
        "scraper_class": OctoScraper,
        "parallel": True
    },
    "directdeal/everit": {
        "id": "268493",
        "code": "268493",
        "product_query_code": "SivCode",
        "scraper_class": DirectDealScraper,
        "parallel": True
    },
    "api": {
        "id": "161784",
        "code": "161784",
        "product_query_code": "SivCode",
        "scraper_class": ApiScraper,
        "parallel": True
    },
    "NetFactory/easynotebooks": {
        "id": "351191",
        "code": "351191",
        "product_query_code": "SivCode",
        "scraper_class": EasyNotebooksScraper,
        "parallel": True
    },
    "Kosatec": {
        "id": "165463",
        "code": "165463",
        "product_query_code": "SivCode",
        "scraper_class": KosatecScraper,
        "parallel": True
    },
    "Dcs (nekvalitní)": {
        "id": "319004",
        "code": "319004",
        "product_query_code": "SivCode",
        "scraper_class": DcsScraper,
        "parallel": True
    },
    "IncomGroup": {
        "id": "169701",
        "code": "169701",
        "product_query_code": "SivCode2",
        "scraper_class": IncomGroupScraper,
        "parallel": True
    },
    "Wortmann": {
        "id": "190157",
        "code": "190157",
        "product_query_code": "SivCode",
        "scraper_class": WortmannScraper,
        "parallel": True
    },
    "AXRO GmbH": {
        "id": "235880",
        "code": "235880",
        "product_query_code": "SivCode",
        "scraper_class": AxroScraper,
        "parallel": True
    },

    # --- Selenium Scrapers ---
    "Wave (selenium)": {
        "id": "115565",
        "code": "115565",
        "product_query_code": "SivCode",
        "scraper_class": WaveScraper,
        "parallel": False
    },
    "notebooksbilliger (selenium)": {
        "id": "340871",
        "code": "340871",
        "product_query_code": "SivCode",
        "scraper_class": NotebooksbilligerScraper,
        "parallel": False
    },
    "fourcom (selenium)": {
        "id": "312585",
        "code": "312585",
        "product_query_code": "SivCode",
        "scraper_class": FourcomScraper,
        "parallel": False
    },
    "Komputronik (selenium)": {
        "id": "104584",
        "code": "104584",
        "product_query_code": "SivCode",
        "scraper_class": KomputronikScraper,
        "parallel": False
    },
    "MICHAELTELECOM AG (selenium)": {
        "id": "318724",
        "code": "318724",
        "product_query_code": "SivCode",
        "scraper_class": MichaelAgScraper,
        "parallel": False
    },

    # --- Playwright Scrapers ---
    "ComLine (Playwright)": {
        "id": "173265",
        "code": "173265",
        "product_query_code": "SivCode",
        "scraper_class": ComLineScraper,
        "parallel": False
    },
    "Cyberport (Playwright)": {
        "id": "177521",
        "code": "177521",
        "product_query_code": "SivCode",
        "scraper_class": CyberportScraper,
        "parallel": False
    }
}

DEFAULT_IGNORED_SUPPLIERS = ["319004"]
