import time
import re
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from typing import Optional, List, Dict

import requests
import pandas as pd
from bs4 import BeautifulSoup

# ---------------- CONFIG ---------------- #

# Any LCSC category URL (you can change this):
BASE_URL = "https://www.lcsc.com/category/874.html"  # Single FETs, MOSFETs

# Maximum number of pages to try
MAX_PAGES = 5  # start small; you can increase later

# Output Excel filename
OUTPUT_FILE = "claude.xlsx"

# Request timeout in seconds
TIMEOUT = 20

# Delay between requests (seconds)
DELAY = 1.0

# Enable debug mode to save page samples
DEBUG_MODE = False

# ---------------------------------------- #
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
}

# Enhanced regex to capture description
# Pattern: MPN LCSC_CODE [Hot/Lightning] MANUFACTURER [Stock info] DESCRIPTION
MPN_LCSC_MANUF_RE = re.compile(
    r"\b([A-Z0-9][A-Z0-9\-.,/]+)\s+"     # MPN
    r"(C\d{4,})\s+"                       # LCSC code
    r"(?:Hot|Lightning)?\s*"              # Optional labels
    r"([A-Za-z0-9/]+)\s+"                 # Manufacturer
    r"(?:[\d,]+\s+(?:In\s+)?Stock\s+)?"   # Optional stock info
    r"([^|$\n]+?)?"                       # Description (non-greedy until delimiter)
    r"(?:\s+\$|\s+US\$|\s+\||$)",         # Stop at price, pipe, or end
    re.MULTILINE
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


def fetch_html(url: str) -> Optional[str]:
    """Fetch HTML from URL with error handling."""
    print(f"[+] Fetching: {url}")
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
    # Check essential fields are non-empty
    if not product.get("mpn") or not product.get("lcsc_code") or not product.get("manufacturer"):
        return False
    
    # Check LCSC code format (C followed by 4+ digits)
    if not re.match(r"^C\d{4,}$", product["lcsc_code"]):
        return False
    
    # Check MPN isn't suspiciously short
    if len(product["mpn"]) < 2:
        return False
    
    return True


def clean_description(desc: str) -> str:
    """Clean and normalize description text."""
    if not desc:
        return ""
    
    # Remove excessive whitespace
    desc = " ".join(desc.split())
    
    # Remove common noise patterns
    desc = re.sub(r'\s*\$[\d,.]+.*$', '', desc)  # Remove price info
    desc = re.sub(r'\s*US\$[\d,.]+.*$', '', desc)
    desc = re.sub(r'\s+\d+\s*pcs.*$', '', desc)  # Remove piece count
    
    # Truncate if too long (likely captured extra text)
    if len(desc) > 200:
        desc = desc[:200].rsplit(' ', 1)[0] + "..."
    
    return desc.strip()


def extract_products_from_text(page_text: str, page_num: int = 0) -> List[Dict[str, str]]:
    """
    Use regex over the *text* of the page to find:
      (MPN, LCSC code, Manufacturer, Description)
    Returns only validated products.
    """
    matches = MPN_LCSC_MANUF_RE.findall(page_text)
    products = []
    
    if DEBUG_MODE and page_num == 1:
        print(f"\n[DEBUG] Found {len(matches)} regex matches on page {page_num}")
        if matches:
            print("[DEBUG] First match sample:")
            print(f"  MPN: {matches[0][0]}")
            print(f"  LCSC: {matches[0][1]}")
            print(f"  Manufacturer: {matches[0][2]}")
            print(f"  Raw description: {matches[0][3][:100] if len(matches[0]) > 3 else 'N/A'}")
    
    for match in matches:
        mpn = match[0] if len(match) > 0 else ""
        lcsc_code = match[1] if len(match) > 1 else ""
        manufacturer = match[2] if len(match) > 2 else ""
        raw_description = match[3] if len(match) > 3 else ""
        
        description = clean_description(raw_description)
        
        product = {
            "mpn": mpn.strip(),
            "lcsc_code": lcsc_code.strip(),
            "manufacturer": manufacturer.strip(),
            "description": description,
        }
        
        if validate_product(product):
            products.append(product)
    
    return products


def scrape_lcsc_category(base_url: str, max_pages: int) -> pd.DataFrame:
    """Scrape products from LCSC category pages."""
    seen_keys = set()  # (mpn, lcsc_code)
    all_rows = []
    consecutive_empty = 0

    for page in range(1, max_pages + 1):
        page_url = build_page_url(base_url, page)
        html = fetch_html(page_url)
        
        if html is None:
            print(f"    [!] Skipping page {page} due to fetch error")
            consecutive_empty += 1
            if consecutive_empty >= 2:
                print("    [!] Multiple consecutive failures; stopping.")
                break
            continue
        
        consecutive_empty = 0  # Reset counter on successful fetch

        # Turn HTML into plain text with BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(separator=" ")
        
        # Debug: Save first page text for inspection
        if DEBUG_MODE and page == 1:
            with open("lcsc_page1_text.txt", "w", encoding="utf-8") as f:
                f.write(text)
            print("[DEBUG] Saved first page text to lcsc_page1_text.txt")

        products = extract_products_from_text(text, page)

        # Filter out duplicates
        new_count = 0
        for p in products:
            key = (p["mpn"], p["lcsc_code"])
            if key in seen_keys:
                continue
            seen_keys.add(key)
            p["page"] = page
            all_rows.append(p)
            new_count += 1

        print(f"    [*] Page {page}: {len(products)} matches, {new_count} new")

        # If we got zero new products, there may be no more pages
        if new_count == 0:
            print("    [*] No new products; stopping pagination.")
            break

        # Be polite - delay between requests
        if page < max_pages:  # Don't delay after last page
            time.sleep(DELAY)

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    # Reorder columns for better readability
    df = df[["mpn", "lcsc_code", "manufacturer", "description", "page"]]
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
    print("LCSC WEB SCRAPER - WITH DESCRIPTION EXTRACTION")
    print("=" * 80)
    print(f"Target URL: {BASE_URL}")
    print(f"Max pages: {MAX_PAGES}")
    print(f"Debug mode: {DEBUG_MODE}")
    print("=" * 80 + "\n")
    
    df = scrape_lcsc_category(BASE_URL, MAX_PAGES)

    if df.empty:
        print(
            "\n[!] No data scraped. Possible reasons:\n"
            "    - The HTML structure or text pattern may have changed\n"
            "    - Network/connection issues\n"
            "    - Invalid BASE_URL\n"
            "    - Regex pattern doesn't match current page format\n\n"
            "TROUBLESHOOTING:\n"
            "    1. Set DEBUG_MODE = True at the top of the script\n"
            "    2. Run again to save page text for inspection\n"
            "    3. Check lcsc_page1_text.txt to see actual page format\n"
            "    4. Adjust regex pattern accordingly"
        )
        return

    print(f"\n[+] Scraped {len(df)} unique products.")
    
    # Show statistics
    print(f"\n[+] Statistics:")
    print(f"    - Products with descriptions: {df['description'].notna().sum()}")
    print(f"    - Products without descriptions: {df['description'].isna().sum() + (df['description'] == '').sum()}")
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
        # Fallback to CSV
        csv_file = OUTPUT_FILE.replace('.xlsx', '.csv')
        print(f"[*] Saving to CSV instead: {csv_file}")
        df.to_csv(csv_file, index=False)
        print("[✓] Done! Data saved to CSV.")
    
    print("\n" + "=" * 80)
    print("TIPS:")
    print("  - If descriptions are missing, set DEBUG_MODE = True and re-run")
    print("  - Check lcsc_page1_text.txt to see the actual page text format")
    print("  - Adjust the regex pattern if needed based on the text format")
    print("=" * 80)


if __name__ == "__main__":
    main()