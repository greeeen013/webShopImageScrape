import requests

def test_multiple_urls(urls):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/114.0.0.0 Safari/537.36"
        )
    }

    for url in urls:
        try:
            response = requests.get(url, headers=headers, timeout=10)
            print(f"{url} -> {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"{url} -> ❌ Error: {type(e).__name__}")

# --- PŘÍKLAD POUŽITÍ ---
if __name__ == "__main__":
    urls_to_test = [
        "https://www.michael-ag.de",
        "https://www.axro.com/en",
        "https://www.wave-distribution.de",
        "https://www.alza.cz/pameti/18842853.htm",
        "https://smicro.cz/pameti-ram",
        "https://shop.api.de/search/352959",
        "https://directdeal.me/search?search=750709000",
        "https://en.fourcom.dk",
        "https://www.octo24.com/result.php?keywords=0830343003075",
        "https://www.easynotebooks.de/search?sSearch=IT0.005.050.675.1",
        "https://www.notebooksbilliger.de/produkte/A%2520455306",
        "https://it-planet.com/de/p/hp-v5c21aaabb-247918.html",
        "https://shop.kosatec.de/Switch-5x-FE-IFP-0503-1xFE-126W-4xPoE/21230357",
        "https://www.incomgroup.pl/produkt/dysk-seagate-barracuda-st2000lm015-2tb-2-5-5400-128mb-sata-iii/",
        "https://www.wortmann.de/de-de/product/distri_ez/5300144/hp-laserjet-pro-mfp-3102-fdn-4in1-multifunktionsdrucker-s-w-laser-a4-legal.aspx",
        "https://www.wave-distribution.de/",
        "https://www.computersalg.dk/i/20731070/brother-p-touch-pt-e560btsp-etikettemaskine-s-h-termo-transfer-rulle-2-4-cm-180-dpi-op-til-30-mm-sek-usb-3-0-bluetooth-5-0",
        "https://b2b.komputronik.eu/product/733692/severin-ek-3163.html",
        "https://www.dcs.dk/en"
    ]

    test_multiple_urls(urls_to_test)
