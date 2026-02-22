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
        "parallel": True,
        "search_url_template": None
    },
    
    # --- Requests Scrapers ---
    "octo it": {
        "id": "348651", 
        "code": "348651",
        "product_query_code": "SivCode",
        "scraper_class": OctoScraper,
        "parallel": True,
        "search_url_template": "https://www.octo24.com/result.php?keywords={}"
    },
    "directdeal/everit": {
        "id": "268493",
        "code": "268493",
        "product_query_code": "SivCode",
        "scraper_class": DirectDealScraper,
        "parallel": True,
        "search_url_template": "https://directdeal.me/search?search={}"
    },
    "api": {
        "id": "161784",
        "code": "161784",
        "product_query_code": "SivCode",
        "scraper_class": ApiScraper,
        "parallel": True,
        "search_url_template": "https://shop.api.de/product/details/{}"
    },
    "NetFactory/easynotebooks": {
        "id": "351191",
        "code": "351191",
        "product_query_code": "SivCode",
        "scraper_class": EasyNotebooksScraper,
        "parallel": True,
        "search_url_template": "https://www.easynotebooks.de/search?sSearch={}"
    },
    "Kosatec": {
        "id": "165463",
        "code": "165463",
        "product_query_code": "SivCode",
        "scraper_class": KosatecScraper,
        "parallel": True,
        "search_url_template": "https://shop.kosatec.de/factfinder/result?query={}"
    },
    "Dcs (nekvalitní)": {
        "id": "319004",
        "code": "319004",
        "product_query_code": "SivCode",
        "scraper_class": DcsScraper,
        "parallel": True,
        "search_url_template": "https://www.dcs.dk/en/search?q={}"
    },
    "IncomGroup": {
        "id": "169701",
        "code": "169701",
        "product_query_code": "SivCode2",
        "scraper_class": IncomGroupScraper,
        "parallel": True,
        "search_url_template": "https://www.incomgroup.pl/?s={}&post_type=produkt"
    },
    "Wortmann": {
        "id": "190157",
        "code": "190157",
        "product_query_code": "SivCode",
        "scraper_class": WortmannScraper,
        "parallel": True,
        "search_url_template": "https://www.wortmann.de/de-de/search.aspx?q={}"
    },
    "AXRO GmbH": {
        "id": "235880",
        "code": "235880",
        "product_query_code": "SivCode",
        "scraper_class": AxroScraper,
        "parallel": True,
        "search_url_template": "https://www.axro.com/en/search?search={}"
    },

    # --- Selenium Scrapers ---
    "Wave (selenium)": {
        "id": "115565",
        "code": "115565",
        "product_query_code": "SivCode",
        "scraper_class": WaveScraper,
        "parallel": False,
        "search_url_template": "https://www.wave-distribution.de/listing.xhtml?q={}"
    },
    "notebooksbilliger (selenium)": {
        "id": "340871",
        "code": "340871",
        "product_query_code": "SivCode",
        "scraper_class": NotebooksbilligerScraper,
        "parallel": False,
        "search_url_template": "https://www.notebooksbilliger.de/produkte/{}" 
    },
    "fourcom (selenium)": {
        "id": "312585",
        "code": "312585",
        "product_query_code": "SivCode",
        "scraper_class": FourcomScraper,
        "parallel": False,
        "search_url_template": "https://en.fourcom.dk" # Requires login/search interaction mostly
    },
    "Komputronik (selenium)": {
        "id": "104584",
        "code": "104584",
        "product_query_code": "SivCode",
        "scraper_class": KomputronikScraper,
        "parallel": False,
        "search_url_template": "https://b2b.komputronik.eu/" # Requires login
    },
    "MICHAELTELECOM AG (selenium)": {
        "id": "318724",
        "code": "318724",
        "product_query_code": "SivCode",
        "scraper_class": MichaelAgScraper,
        "parallel": False,
        "search_url_template": "https://www.michael-ag.de/shop/article/details/{}"
    },

    # --- Playwright Scrapers ---
    "ComLine (Playwright)": {
        "id": "173265",
        "code": "173265",
        "product_query_code": "SivCode",
        "scraper_class": ComLineScraper,
        "parallel": False,
        "search_url_template": "https://shop.comline-shop.de/" # Search requires login
    },
    "Cyberport (Playwright)": {
        "id": "177521",
        "code": "177521",
        "product_query_code": "SivCode",
        "scraper_class": CyberportScraper,
        "parallel": False,
        "search_url_template": "https://www.cyberport.de/tools/search-results.html?autosuggest=false&q={}"
    }
}

DEFAULT_IGNORED_SUPPLIERS = ["319004"]
