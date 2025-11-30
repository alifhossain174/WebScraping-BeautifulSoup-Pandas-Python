import time
import re
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

import requests
import pandas as pd
from bs4 import BeautifulSoup

# ---------------- CONFIG ---------------- #

# Any LCSC category URL (you can change this):
BASE_URL = "https://www.lcsc.com/category/874.html"  # Single FETs, MOSFETs

# Maximum number of pages to try
MAX_PAGES = 5  # start small; you can increase later

# Output Excel filename
OUTPUT_FILE = "main.xlsx"

# ---------------------------------------- #
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
}

# Regex:
#  - group 1: MPN (letters/digits/-/.,/)
#  - group 2: LCSC part (C + 4+ digits)
#  - group 3: Manufacturer (word like Infineon, DIODES, AOS, onsemi, etc.)
MPN_LCSC_MANUF_RE = re.compile(
    r"\b([A-Z0-9][A-Z0-9\-.,/]+)\s+"
    r"(C\d{4,})\s+"
    r"(?:Hot|Lightning)?\s*"
    r"([A-Za-z0-9/]+)"
)


def build_page_url(base_url: str, page: int) -> str:
    """
    Builds pagination URLs like:
      page 1 -> base_url
      page 2 -> base_url?page=2
      page 3 -> base_url?page=3
    """
    if page == 1:
        return base_url

    parsed = urlparse(base_url)
    query = parse_qs(parsed.query)
    query["page"] = [str(page)]
    new_query = urlencode(query, doseq=True)
    new_parsed = parsed._replace(query=new_query)
    return urlunparse(new_parsed)


def fetch_html(url: str) -> str:
    print(f"[+] Fetching: {url}")
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def extract_products_from_text(page_text: str):
    """
    Use regex over the *text* of the page to find:
      (MPN, LCSC code, Manufacturer)
    Example pattern on LCSC:
      "BSS138-7-F C40912 Hot DIODES 119,020 In Stock ..."
    """
    matches = MPN_LCSC_MANUF_RE.findall(page_text)
    products = []
    for mpn, lcsc_code, manufacturer in matches:
        products.append(
            {
                "mpn": mpn,
                "lcsc_code": lcsc_code,
                "manufacturer": manufacturer,
            }
        )
    return products


def scrape_lcsc_category(base_url: str, max_pages: int) -> pd.DataFrame:
    seen_keys = set()  # (mpn, lcsc_code)
    all_rows = []

    for page in range(1, max_pages + 1):
        page_url = build_page_url(base_url, page)
        html = fetch_html(page_url)

        # Turn HTML into plain text with BeautifulSoup so regex works on text
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(separator=" ")

        products = extract_products_from_text(text)

        # Filter out products we've already seen (avoid duplicates, including
        # "Other Suppliers" repeated blocks).
        new_count = 0
        for p in products:
            key = (p["mpn"], p["lcsc_code"])
            if key in seen_keys:
                continue
            seen_keys.add(key)
            p["page"] = page  # keep track of which page we found it on
            all_rows.append(p)
            new_count += 1

        print(f"    [*] Page {page}: {len(products)} matches, {new_count} new")

        # If we got zero new products from this page, there may be no more pages.
        if new_count == 0:
            print("    [*] No new products; stopping pagination.")
            break

        # Be polite
        time.sleep(1.0)

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    return df


def main():
    print(f"Scraping LCSC category: {BASE_URL}")
    df = scrape_lcsc_category(BASE_URL, MAX_PAGES)

    if df.empty:
        print(
            "\n[!] No data scraped. "
            "The HTML structure or text pattern may have changed.\n"
            "Try increasing MAX_PAGES, or print part of the page text "
            "to see what's going on."
        )
        return

    print(f"\n[+] Scraped {len(df)} unique products.")
    print(f"[+] Saving to Excel: {OUTPUT_FILE}")
    df.to_excel(OUTPUT_FILE, index=False)
    print("[✓] Done.")


if __name__ == "__main__":
    main()
