import time
import re
from urllib.parse import urlparse
from typing import Optional, List, Dict, Tuple
import json  # <-- NEW

import requests
import pandas as pd
from bs4 import BeautifulSoup

# ---------------- CONFIG ---------------- #

# Optional cap on number of pages to fetch PER CATEGORY.
#   0 or negative => no manual cap; use all pages reported by API.
#   positive int  => min(MAX_PAGES, API_totalPage) pages.
MAX_PAGES = 0

# Category ID range filter (inclusive).
# Only categories with id between CAT_ID_START and CAT_ID_END will be scraped.
CAT_ID_START = 1201
CAT_ID_END = 1400

# Output Excel filename (multi-sheet workbook)
OUTPUT_FILE = "rangeWithSpecs(1201-1400).xlsx"

# Request timeout in seconds
TIMEOUT = 20

# Delay between requests (seconds) between API pages
DELAY = 1.0

# Enable debug mode to print extra info
DEBUG_MODE = False

# LCSC product-list API endpoint (used for pagination)
PRODUCT_LIST_API = "https://wmsc.lcsc.com/ftps/wm/product/query/list"

# Category index page (where we discover all /category/xxx.html links)
CATEGORY_INDEX_URL = "https://www.lcsc.com/products"

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


def build_specs_from_item(item: Dict) -> Dict[str, Optional[str]]:
    """
    Build a full specification dict from the API item:
      - Category / Manufacturer / Package
      - All entries in paramVOList (Type → Description)
    """
    specs: Dict[str, Optional[str]] = {}

    # Category (full English catalog name)
    cat = (item.get("wmCatalogNameEn")
           or item.get("firstWmCatalogNameEn")
           or item.get("secondWmCatalogNameEn")
           or item.get("thirdWmCatalogNameEn"))
    if cat:
        specs["Category"] = cat.strip()

    # Manufacturer
    manu = item.get("brandNameEn")
    if manu:
        specs["Manufacturer"] = manu.strip()

    # Package – there are multiple possible fields; try them in order
    pkg = (
        item.get("encapStandard")
        or item.get("encapEn")
        or item.get("encap")
        or item.get("packageEn")
    )
    if pkg:
        specs["Package"] = pkg.strip()

    # All paramVOList entries (this is where Width, Thickness, Function, etc. live)
    for p in item.get("paramVOList") or []:
        name = (p.get("paramNameEn") or p.get("paramName") or "").strip()
        value = (p.get("paramValueEn") or p.get("paramValue") or "").strip()

        if not name or not value:
            continue

        # Avoid overwriting core keys if they already exist
        if name in specs:
            continue

        specs[name] = value

    return specs


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

        # --- NEW: build full specs dict from API (includes Thickness, Width, etc.) ---
        specs_dict = build_specs_from_item(item)
        specs_json = json.dumps(specs_dict, ensure_ascii=False)

        product = {
            "mpn": mpn,
            "lcsc_code": lcsc_code,
            "manufacturer": manufacturer,
            "description": description,
            "category": category,
            "subcategory": subcategory,
            "childcategory": childcategory,
            "specs_json": specs_json,  # NEW COLUMN
        }

        if validate_product(product):
            products.append(product)

    return products, total_pages


def scrape_lcsc_category(base_url: str, max_pages: int) -> pd.DataFrame:
    """Scrape products from ONE LCSC category via their JSON API."""
    catalog_id = parse_catalog_id_from_url(base_url)
    if catalog_id is None:
        print(f"[!] Could not parse catalog/category ID from URL: {base_url}")
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

    print(f"[i] API for {base_url} reports {total_pages} total pages; fetching {pages_to_fetch} page(s).")

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
            "specs_json",  # NEW
            "page",
        ]
    ]
    return df


def get_all_category_urls() -> List[Tuple[int, str, str]]:
    """
    Discover all distinct /category/XXXX.html links from the main products page.
    Returns a list of tuples: (category_id, full_url, link_text_name)
    """
    html = fetch_html(CATEGORY_INDEX_URL)
    if not html:
        print("[!] Could not fetch category index page.")
        return []

    soup = BeautifulSoup(html, "lxml")
    categories: Dict[int, Tuple[int, str, str]] = {}

    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = re.search(r"/category/(\d+)\.html", href)
        if not m:
            continue
        cat_id = int(m.group(1))

        # Apply ID range filter here
        if cat_id < CAT_ID_START or cat_id > CAT_ID_END:
            continue

        # Get visible text as category name
        name = (a.get_text(strip=True) or "").strip()
        if not name:
            continue

        # Skip generic "View All" menu items to avoid duplicates
        if "View All" in name:
            continue

        if href.startswith("http"):
            full_url = href
        else:
            full_url = "https://www.lcsc.com" + href

        # Only keep the first meaningful name per category ID
        if cat_id not in categories:
            categories[cat_id] = (cat_id, full_url, name)

    cat_list = list(categories.values())
    print(f"[i] Discovered {len(cat_list)} category URLs in ID range [{CAT_ID_START}, {CAT_ID_END}] from {CATEGORY_INDEX_URL}")
    return cat_list


def make_excel_sheet_name(raw_name: str, fallback: str, used: set) -> str:
    """
    Sanitize and deduplicate names to be valid Excel sheet names.
    """
    name = (raw_name or fallback or "Sheet").strip()
    # Replace invalid characters: \ / * ? : [ ]
    name = re.sub(r'[\\/*?:\[\]]', "_", name)
    # Excel sheet name limit: 31 chars
    if len(name) > 31:
        name = name[:31]

    base = name
    suffix = 1
    while name in used:
        trimmed = base[:28]
        name = f"{trimmed}_{suffix}"
        suffix += 1

    used.add(name)
    return name


def main():
    print("=" * 80)
    print("LCSC WEB SCRAPER - ALL CATEGORIES → MULTI-SHEET EXCEL (WITH SPECS JSON)")
    print("=" * 80)
    print(f"MAX_PAGES cap per category: {MAX_PAGES} (0 = no cap)")
    print(f"Category ID range: [{CAT_ID_START}, {CAT_ID_END}]")
    print(f"Debug mode: {DEBUG_MODE}")
    print("=" * 80 + "\n")

    # Discover all categories from the site (within ID range)
    cat_list = get_all_category_urls()
    if not cat_list:
        print("[!] No categories discovered; aborting.")
        return

    print(f"[i] Will scrape {len(cat_list)} categories.\n")

    total_products_all = 0
    used_sheet_names = set()

    try:
        with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
            for idx, (cat_id, base_url, cat_name) in enumerate(cat_list, start=1):
                print("\n" + "-" * 80)
                print(f"[{idx}/{len(cat_list)}] Category ID {cat_id}: {cat_name}")
                print(f"    URL: {base_url}")

                df = scrape_lcsc_category(base_url, MAX_PAGES)

                if df.empty:
                    print(f"    [!] No products for this category (or API error). Skipping sheet.")
                    continue

                # Prefer childcategory name for sheet, then subcategory, then category, else menu name
                sheet_base = ""
                try:
                    if "childcategory" in df.columns and df["childcategory"].notna().any():
                        sheet_base = str(df["childcategory"].dropna().iloc[0])
                    elif "subcategory" in df.columns and df["subcategory"].notna().any():
                        sheet_base = str(df["subcategory"].dropna().iloc[0])
                    elif "category" in df.columns and df["category"].notna().any():
                        sheet_base = str(df["category"].dropna().iloc[0])
                except Exception:
                    sheet_base = ""

                if not sheet_base:
                    sheet_base = cat_name

                sheet_name = make_excel_sheet_name(sheet_base, f"cat_{cat_id}", used_sheet_names)
                print(f"    [i] Writing {len(df)} products to sheet: '{sheet_name}'")

                df.to_excel(writer, sheet_name=sheet_name, index=False)
                total_products_all += len(df)

        print("\n" + "=" * 80)
        print(f"[✓] Finished scraping all categories.")
        print(f"[+] Total products scraped across all categories: {total_products_all}")
        print(f"[+] Output Excel file: {OUTPUT_FILE}")
        print("=" * 80)

    except ImportError:
        print("[!] Error: openpyxl not installed. Install with: pip install openpyxl")
    except Exception as e:
        print(f"[!] Error while writing Excel file: {e}")


if __name__ == "__main__":
    main()
