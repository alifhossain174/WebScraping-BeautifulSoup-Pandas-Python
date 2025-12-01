import time
import re
from urllib.parse import urlparse
from typing import Optional, List, Dict, Tuple

import requests
import pandas as pd
from bs4 import BeautifulSoup

# ---------------- CONFIG ---------------- #

# Any LCSC category URL (you can change this):
BASE_URL = "https://www.lcsc.com/category/874.html"  # Single FETs, MOSFETs

# Optional cap on number of pages to fetch.
#   0 or negative => no manual cap; use all pages reported by API.
#   positive int  => min(MAX_PAGES, API_totalPage) pages.
MAX_PAGES = 0

# Output Excel filename
OUTPUT_FILE = "single.xlsx"

# Request timeout in seconds
TIMEOUT = 20

# Delay between requests (seconds)
DELAY = 1.0

# Enable debug mode to save page samples
DEBUG_MODE = False

# LCSC product-list API endpoint (used for pagination)
PRODUCT_LIST_API = "https://wmsc.lcsc.com/ftps/wm/product/query/list"

# ---------------------------------------- #
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
}

# ------------------------------------------------------------------


def fetch_html(url: str) -> Optional[str]:
    """Fetch HTML from URL with error handling."""
    print(f"[+] Fetching HTML: {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.text
    except requests.Timeout:
        print(f"[!] Timeout while fetching {url}")
        return None
    except requests.RequestException as e:
        print(f"[!] Error fetching {url}: {e}")
        return None


def validate_product(product: Dict[str, str]) -> bool:
    """Validate that product data looks reasonable."""
    if not product.get("mpn") or not product.get("lcsc_code") or not product.get("manufacturer"):
        return False
    
    if not re.match(r"^C\d{4,}$", product["lcsc_code"]):
        return False
    
    if len(product["mpn"]) < 2:
        return False
    
    return True


def clean_description(desc: str) -> str:
    """Clean and normalize description text."""
    if not desc:
        return ""
    
    desc = " ".join(desc.split())
    desc = re.sub(r'\s*\$[\d,.]+.*$', '', desc)
    desc = re.sub(r'\s*US\$[\d,.]+.*$', '', desc)
    desc = re.sub(r'\s+\d+\s*pcs.*$', '', desc)
    
    if len(desc) > 200:
        desc = desc[:200].rsplit(' ', 1)[0] + "..."
    
    return desc.strip()


def fetch_description_from_detail(lcsc_code: str) -> str:
    """
    Fetch the product detail page and extract the 'Description' field text.
    Used as a fallback if the API description is missing.
    """
    if not lcsc_code:
        return ""

    detail_url = f"https://www.lcsc.com/product-detail/{lcsc_code}.html"
    html = fetch_html(detail_url)
    if html is None:
        return ""

    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(separator=" ")

    m = re.search(
        r"Description\s+(.+?)(?:\s+Datasheet|\s+##\s+Products\s+Specifications|\s+Type\s+Description|$)",
        text
    )
    if not m:
        return ""

    desc = m.group(1)
    return clean_description(desc)


def parse_catalog_id_from_url(url: str) -> Optional[int]:
    """
    Extract the numeric catalog/category ID from an LCSC category URL like:
    https://www.lcsc.com/category/874.html
    """
    m = re.search(r"/category/(\d+)\.html", url)
    if not m:
        return None
    return int(m.group(1))


def fetch_products_page_api(
    catalog_id: int, page: int
) -> Tuple[List[Dict[str, str]], Optional[int]]:
    """
    Call LCSC's product-list API for a specific catalog + page and
    return (products, total_pages).
    total_pages is only needed from the first call but is returned every time.
    """
    payload = {
        "keyword": "",
        "catalogIdList": [catalog_id],
        "brandIdList": [],
        "encapValueList": [],
        "isStock": False,
        "isOtherSuppliers": False,
        "isAsianBrand": False,
        "isDeals": False,
        "isEnvironment": False,
        "paramNameValueMap": {},
        "currentPage": page,
        "pageSize": 25,
    }

    print(f"[+] Fetching page {page} via API for catalog {catalog_id}")
    try:
        resp = requests.post(
            PRODUCT_LIST_API,
            headers=HEADERS,
            json=payload,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
    except requests.Timeout:
        print(f"[!] Timeout while fetching API page {page}")
        return [], None
    except requests.RequestException as e:
        print(f"[!] Error fetching API page {page}: {e}")
        return [], None

    try:
        data = resp.json()
    except ValueError:
        print(f"[!] Failed to decode JSON for page {page}")
        return [], None

    result = data.get("result", {}) or {}
    total_pages = result.get("totalPage")
    items = result.get("dataList", []) or []

    if DEBUG_MODE:
        print(f"    [DEBUG] API page {page}: totalPage={total_pages}, items={len(items)}")

    products: List[Dict[str, str]] = []

    for item in items:
        mpn = (item.get("productModel") or "").strip()
        lcsc_code = (item.get("productCode") or "").strip()
        manufacturer = (item.get("brandNameEn") or "").strip()

        # Description from API (preferred)
        desc_api = (
            item.get("productIntroEn")
            or item.get("productNameEn")
            or ""
        )
        desc_api = clean_description(desc_api)

        # Fallback to detail page if API description is empty
        if not desc_api:
            detail_desc = fetch_description_from_detail(lcsc_code)
            description = detail_desc or ""
        else:
            description = desc_api

        # Category hierarchy (top-level, second-level, third-level)
        category = (item.get("firstWmCatalogNameEn") or "").strip()
        subcategory = (item.get("secondWmCatalogNameEn") or "").strip()
        childcategory = (item.get("thirdWmCatalogNameEn") or "").strip()

        product = {
            "mpn": mpn,
            "lcsc_code": lcsc_code,
            "manufacturer": manufacturer,
            "description": description,
            "category": category,
            "subcategory": subcategory,
            "childcategory": childcategory,
        }

        if validate_product(product):
            products.append(product)

    return products, total_pages


def scrape_lcsc_category(base_url: str, max_pages: int) -> pd.DataFrame:
    """Scrape products from LCSC category pages via their JSON API."""
    catalog_id = parse_catalog_id_from_url(base_url)
    if catalog_id is None:
        print("[!] Could not parse catalog/category ID from BASE_URL.")
        return pd.DataFrame()

    seen_keys = set()  # (mpn, lcsc_code)
    all_rows: List[Dict[str, str]] = []
    total_count = 0

    # ---- First page: also read totalPage from API ----
    products_page1, total_pages = fetch_products_page_api(catalog_id, 1)

    if not products_page1:
        print("[!] API returned no products on page 1.")
        return pd.DataFrame()

    if total_pages is None:
        total_pages = 1

    # Determine how many pages to fetch in total
    if max_pages and max_pages > 0:
        pages_to_fetch = min(total_pages, max_pages)
    else:
        pages_to_fetch = total_pages

    print(f"[i] API reports {total_pages} total pages; fetching {pages_to_fetch} page(s).")

    # Process page 1
    page = 1
    new_count = 0
    for p in products_page1:
        key = (p["mpn"], p["lcsc_code"])
        if key in seen_keys:
            continue
        seen_keys.add(key)
        p["page"] = page
        all_rows.append(p)
        new_count += 1
    total_count += new_count
    print(f"    [*] Page {page}: {len(products_page1)} products, {new_count} new (total so far: {total_count})")

    # ---- Remaining pages ----
    for page in range(2, pages_to_fetch + 1):
        products, _ = fetch_products_page_api(catalog_id, page)

        if not products:
            print(f"    [*] Page {page}: 0 products; stopping.")
            break

        new_count = 0
        for p in products:
            key = (p["mpn"], p["lcsc_code"])
            if key in seen_keys:
                continue
            seen_keys.add(key)
            p["page"] = page
            all_rows.append(p)
            new_count += 1

        total_count += new_count
        print(f"    [*] Page {page}: {len(products)} products, {new_count} new (total so far: {total_count})")

        if page < pages_to_fetch:
            time.sleep(DELAY)

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    df = df[
        [
            "mpn",
            "lcsc_code",
            "manufacturer",
            "description",
            "category",
            "subcategory",
            "childcategory",
            "page",
        ]
    ]
    return df


def save_to_excel(df: pd.DataFrame, filename: str) -> bool:
    """Save DataFrame to Excel with error handling."""
    try:
        df.to_excel(filename, index=False)
        return True
    except ImportError:
        print("[!] Error: openpyxl not installed. Install with: pip install openpyxl")
        return False
    except Exception as e:
        print(f"[!] Error saving to Excel: {e}")
        return False


def main():
    print("=" * 80)
    print("LCSC WEB SCRAPER - USING JSON API (AUTO PAGES + CATEGORY)")
    print("=" * 80)
    print(f"Target URL: {BASE_URL}")
    print(f"MAX_PAGES cap: {MAX_PAGES} (0 = no cap)")
    print(f"Debug mode: {DEBUG_MODE}")
    print("=" * 80 + "\n")
    
    df = scrape_lcsc_category(BASE_URL, MAX_PAGES)

    if df.empty:
        print(
            "\n[!] No data scraped. Possible reasons:\n"
            "    - The API parameters changed\n"
            "    - Network/connection issues\n"
            "    - Invalid BASE_URL (no catalog id)\n"
        )
        return

    print(f"\n[+] Scraped {len(df)} unique products.")
    
    print(f"\n[+] Statistics:")
    print(f"    - Products with descriptions: {df['description'].astype(str).str.len().gt(0).sum()}")
    print(f"    - Products without descriptions: {df['description'].astype(str).str.len().eq(0).sum()}")
    print(f"    - Unique manufacturers: {df['manufacturer'].nunique()}")
    
    print(f"\n[+] Preview of first 5 rows:")
    print("=" * 80)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    pd.set_option('display.max_colwidth', 50)
    print(df.head())
    print("=" * 80)
    
    print(f"\n[+] Saving to Excel: {OUTPUT_FILE}")
    
    if save_to_excel(df, OUTPUT_FILE):
        print("[✓] Done! Data saved successfully.")
    else:
        csv_file = OUTPUT_FILE.replace('.xlsx', '.csv')
        print(f"[*] Saving to CSV instead: {csv_file}")
        df.to_csv(csv_file, index=False)
        print("[✓] Done! Data saved to CSV.")
    
    print("\n" + "=" * 80)
    print("TIPS:")
    print("  - MAX_PAGES = 0 → fetch all API pages")
    print("  - Set MAX_PAGES to e.g. 3 if you only want the first 3 pages")
    print("  - You can change BASE_URL to any other LCSC category URL")
    print("=" * 80)


if __name__ == "__main__":
    main()
