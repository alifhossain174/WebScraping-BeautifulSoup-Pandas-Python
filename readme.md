# LCSC Web Scraper Suite

A comprehensive Python web scraping toolkit for extracting electronic component data from LCSC (LCS Components) product categories using their JSON API, with multiple scripts for different scraping scenarios.

## Features

- **API-Based Scraping**: Uses LCSC's product-list API for reliable, fast data extraction
- **Automatic Pagination**: Automatically detects and fetches all pages in a category
- **Multiple Scraping Modes**: Single category, multiple categories, or category ranges
- **Data Validation**: Ensures product data integrity before export
- **Fallback Descriptions**: Automatically fetches detailed descriptions from product pages if API data is missing
- **Specification Extraction**: Advanced script to extract detailed product specifications
- **Excel & CSV Export**: Saves data to Excel (`.xlsx`) with automatic fallback to CSV
- **Multi-Sheet Workbooks**: Organizes scraped data into separate sheets by category
- **Configurable Limits**: Set maximum pages to scrape or fetch all available data
- **Debug Mode**: Optional debug logging for troubleshooting
- **Error Handling**: Robust request handling with timeouts and retry logic

## Requirements

- Python 3.7+
- See `requirements.txt` for dependencies

### Key Dependencies
- **requests**: HTTP library for API calls
- **beautifulsoup4**: HTML parsing for detail page fallbacks
- **pandas**: Data manipulation and Excel export
- **openpyxl**: Excel file writing

## Scripts Overview

### 1. `single.py` - Scrape Single Category
Scrapes a single LCSC product category by URL.

**Best for**: Extracting data from one specific product category

**Configuration**:
```python
BASE_URL = "https://www.lcsc.com/category/874.html"  # Change to any category
MAX_PAGES = 0  # 0 = all pages, or set a limit (e.g., 5)
OUTPUT_FILE = "data.xlsx"
```

**Run**:
```bash
python single.py
```

---

### 2. `all.py` - Scrape All Categories
Automatically discovers and scrapes all product categories from LCSC.

**Best for**: Creating a complete database of all LCSC products

**Configuration**:
```python
MAX_PAGES = 0  # Maximum pages per category
OUTPUT_FILE = "lcsc_all_categories.xlsx"  # Multi-sheet workbook
```

**Run**:
```bash
python all.py
```

**Output**: One Excel sheet per category

---

### 3. `multiple_v2.py` - Scrape Category Range
Scrapes a range of categories by ID (inclusive).

**Best for**: Scraping specific category segments in batches

**Configuration**:
```python
CATEGORY_ID_START = 1   # Starting category ID (inclusive)
CATEGORY_ID_END = 63    # Ending category ID (inclusive)
MAX_PAGES = 0           # Maximum pages per category
OUTPUT_FILE = "lcsc_all_categories.xlsx"
```

**Run**:
```bash
python multiple_v2.py
```

**Example**: To scrape categories 50-100:
```python
CATEGORY_ID_START = 50
CATEGORY_ID_END = 100
```

---

### 4. `rangeWithSpecs.py` - Scrape Range with Specifications
Scrapes a category range AND extracts detailed product specifications.

**Best for**: Building a comprehensive product database with detailed specs

**Configuration**:
```python
CATEGORY_ID_START = 1   # Starting category ID
CATEGORY_ID_END = 50    # Ending category ID
MAX_PAGES = 0           # Maximum pages per category
OUTPUT_FILE = "rangeWithSpecs.xlsx"
```

**Run**:
```bash
python rangeWithSpecs.py
```

**Additional Output**: Includes specification columns (e.g., voltage, current, frequency) extracted from product detail pages

---

## Installation

1. Clone or download this repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Common Configuration

All scripts share these configurable settings:

| Setting | Default | Description |
|---------|---------|-------------|
| `MAX_PAGES` | `0` | Maximum pages per category (0 = all pages) |
| `OUTPUT_FILE` | Varies | Output filename for scraped data |
| `TIMEOUT` | `20` | Request timeout in seconds |
| `DELAY` | `1.0` | Delay between requests (seconds) to avoid rate limiting |
| `DEBUG_MODE` | `False` | Enable debug logging |

## Usage Examples

### Quick Start - Single Category
```bash
python single.py
# Output: data.xlsx with ~25 products (adjustable via MAX_PAGES)
```

### Complete Catalog
```bash
python all.py
# Output: lcsc_all_categories.xlsx with all categories as separate sheets
```

### Specific Range
```bash
# Edit multiple_v2.py to set CATEGORY_ID_START and CATEGORY_ID_END
python multiple_v2.py
```

### With Specifications
```bash
# Edit rangeWithSpecs.py to set category range
python rangeWithSpecs.py
# Output includes detailed product specifications
```

### Example Output
```
================================================================================
LCSC WEB SCRAPER - USING JSON API (AUTO PAGES + CATEGORY)
================================================================================
Target URL: https://www.lcsc.com/category/874.html
MAX_PAGES cap: 0 (0 = no cap)
Debug mode: False
================================================================================

[+] Fetching page 1 via API for catalog 874
    [*] Page 1: 25 products, 25 new (total so far: 25)
[+] Fetching page 2 via API for catalog 874
    [*] Page 2: 25 products, 25 new (total so far: 50)
...
[+] Scraped 250 unique products.

[+] Statistics:
    - Products with descriptions: 248
    - Products without descriptions: 2
    - Unique manufacturers: 45

[+] Saving to Excel: data.xlsx
[✓] Done! Data saved successfully.
```

## Output Data Format

All scripts export data with these common columns:

| Column | Description |
|--------|-------------|
| `mpn` | Manufacturer Part Number |
| `lcsc_code` | LCSC product code (starts with 'C') |
| `manufacturer` | Manufacturer name (English) |
| `description` | Product description (cleaned) |
| `category` | Top-level category (e.g., "Semiconductors") |
| `subcategory` | Second-level category |
| `childcategory` | Third-level category |
| `page` | Page number from which the product was scraped |

**`rangeWithSpecs.py` adds**: Additional specification columns extracted from product detail pages (voltage, current, frequency, etc.)

## How It Works

1. **Parse Categories**: Discovers category IDs from LCSC or uses specified range
2. **Fetch from API**: Calls LCSC's product-list API with pagination
3. **Validate Data**: Checks that each product has required fields (MPN, LCSC code, manufacturer)
4. **Clean Descriptions**: Removes prices, quantity markers, and truncates long text
5. **Fallback Handling**: If API description is empty, fetches from product detail page
6. **Extract Specs** (rangeWithSpecs only): Parses HTML to extract detailed specifications
7. **Deduplicate**: Uses MPN + LCSC code as unique key to avoid duplicates
8. **Export**: Saves cleaned data to Excel or CSV

## Advanced Features

### Specification Extraction (rangeWithSpecs.py)
- Extracts detailed product specifications from detail pages
- Caches detail page fetches to minimize requests
- Parses HTML specification tables
- Adds specification columns to output

### Multi-Sheet Workbooks (all.py & multiple_v2.py)
- Creates separate Excel sheets for each category
- Sheet names derived from category titles
- Better organization for large datasets

### Deduplication
- Uses MPN + LCSC code as unique identifier
- Prevents duplicate entries across multiple scraping runs
- Tracks seen products across all pages

## Tips & Tricks

- **Fetch All Data**: Set `MAX_PAGES = 0` to automatically fetch all pages
- **Limit Scraping**: Set `MAX_PAGES = 5` to fetch only the first 5 pages
- **Slow Down**: Increase `DELAY` to 2.0+ if getting rate-limited
- **Debug Issues**: Set `DEBUG_MODE = True` to see detailed API response info
- **Custom Timeout**: Adjust `TIMEOUT` if requests are failing on slow connections
- **Test First**: Start with `MAX_PAGES = 1` to verify the script works
- **Batch Processing**: Use `multiple_v2.py` with small ranges (e.g., 20 categories at a time)

## API Details

All scripts use LCSC's internal API endpoint:
```
POST https://wmsc.lcsc.com/ftps/wm/product/query/list
```

**Request payload includes:**
- `catalogIdList`: Product category ID(s)
- `currentPage`: Page number (1-indexed)
- `pageSize`: 25 products per page
- Other filters: brand, encapsulation, stock status, etc.

## Error Handling

All scripts handle common errors gracefully:
- **Network errors**: Prints error message and skips page/category
- **Timeout errors**: Logs timeout and continues to next page
- **Invalid JSON**: Handles malformed API responses
- **Missing dependencies**: Provides installation instructions
- **API failures**: Gracefully handles API errors and continues

## Limitations

- Limited to LCSC categories (cannot scrape arbitrary websites)
- API page limit: typically 25 products per page
- Respects server rate limits via configurable delays
- Description/spec fallback requires additional requests (slower)
- Category discovery limited to LCSC's category index

## Performance Considerations

| Script | Speed | Data Volume | Best Use Case |
|--------|-------|-------------|---------------|
| `single.py` | ⚡ Fast | ~25-500 products | Testing, quick scrapes |
| `all.py` | 🐌 Slow | Entire catalog | Complete database |
| `multiple_v2.py` | ⚡⚡ Medium | Batch processing | Segment catalog scraping |
| `rangeWithSpecs.py` | 🐢 Very slow | Detailed specs | In-depth product analysis |

## Troubleshooting

### No data scraped
- Verify URL/category IDs are valid
- Check your internet connection
- Try increasing `TIMEOUT` value to 30+
- Enable `DEBUG_MODE` to see API responses

### Missing descriptions
- Some products may not have descriptions on LCSC
- Enable `DEBUG_MODE` to see which products are missing data
- Try `rangeWithSpecs.py` which fetches from detail pages

### Rate limiting (HTTP 429)
- Increase `DELAY` value (e.g., to 2.0 or higher)
- Reduce `MAX_PAGES` to fetch fewer pages per category
- Try running smaller category ranges with breaks

### Excel export fails
- Ensure `openpyxl` is installed: `pip install openpyxl`
- The script will automatically save to CSV as a fallback
- Check disk space availability

### Slow performance
- Reduce `MAX_PAGES` if fetching many categories
- Increase `DELAY` between categories (adds time but reduces API stress)
- Don't run multiple scripts simultaneously

## Project Structure

```
web-scraping/
├── single.py              # Single category scraper
├── all.py                 # All categories scraper
├── multiple_v2.py         # Category range scraper
├── rangeWithSpecs.py      # Range + specifications scraper
├── requirements.txt       # Python dependencies
├── README.md              # This file
└── *.xlsx                 # Generated output files
```

## License

This project is provided as-is for educational and personal use.

## Disclaimer

This scraper respects LCSC's robots.txt and uses reasonable delays between requests. Always check a website's terms of service before scraping. The author is not responsible for misuse of this tool.
