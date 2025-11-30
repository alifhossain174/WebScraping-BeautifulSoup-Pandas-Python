# LCSC Web Scraper

A Python web scraper that extracts electronic component data from LCSC (LCS Components) product categories using their JSON API, with automatic pagination and data export to Excel/CSV.

## Features

- **API-Based Scraping**: Uses LCSC's product-list API for reliable, fast data extraction
- **Automatic Pagination**: Automatically detects and fetches all pages in a category
- **Flexible Category Selection**: Scrape any LCSC product category by changing the URL
- **Data Validation**: Ensures product data integrity before export
- **Fallback Descriptions**: Automatically fetches detailed descriptions from product pages if API data is missing
- **Excel & CSV Export**: Saves data to Excel (`.xlsx`) with automatic fallback to CSV
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

## Installation

1. Clone or download this repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

Edit the configuration section at the top of `main.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `BASE_URL` | `"https://www.lcsc.com/category/874.html"` | LCSC category URL to scrape |
| `MAX_PAGES` | `0` | Maximum pages to fetch (0 = all pages, positive int = limit) |
| `OUTPUT_FILE` | `"data.xlsx"` | Output filename for scraped data |
| `TIMEOUT` | `20` | Request timeout in seconds |
| `DELAY` | `1.0` | Delay between requests (seconds) to avoid rate limiting |
| `DEBUG_MODE` | `False` | Enable debug logging |

### Changing the Category

Replace `BASE_URL` with any LCSC category URL:
```python
BASE_URL = "https://www.lcsc.com/category/874.html"  # Single FETs, MOSFETs
# Example alternatives:
# BASE_URL = "https://www.lcsc.com/category/1.html"  # Capacitors
# BASE_URL = "https://www.lcsc.com/category/2.html"  # Resistors
```

## Usage

Run the script:
```bash
python main.py
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

## Output Data

The exported file contains the following columns:

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

## How It Works

1. **Parse Category ID**: Extracts the catalog ID from the LCSC category URL
2. **Fetch from API**: Calls LCSC's product-list API (`wmsc.lcsc.com/ftps/wm/product/query/list`) with pagination
3. **Validate Data**: Checks that each product has required fields (MPN, LCSC code, manufacturer)
4. **Clean Descriptions**: Removes prices, quantity markers, and truncates long text
5. **Fallback Handling**: If API description is empty, fetches from the product detail page
6. **Deduplicate**: Uses MPN + LCSC code as unique key to avoid duplicates
7. **Export**: Saves cleaned data to Excel or CSV

## API Details

The scraper uses LCSC's internal API endpoint:
```
POST https://wmsc.lcsc.com/ftps/wm/product/query/list
```

**Request payload includes:**
- `catalogIdList`: Product category ID
- `currentPage`: Page number (1-indexed)
- `pageSize`: 25 products per page
- Other filters: brand, encapsulation, stock status, etc.

## Tips & Tricks

- **Fetch All Data**: Set `MAX_PAGES = 0` to automatically fetch all pages
- **Limit Scraping**: Set `MAX_PAGES = 5` to fetch only the first 5 pages
- **Slow Down**: Increase `DELAY` to 2.0+ if getting rate-limited
- **Debug Issues**: Set `DEBUG_MODE = True` to see detailed API response info
- **Custom Timeout**: Adjust `TIMEOUT` if requests are failing on slow connections

## Error Handling

The script handles common errors gracefully:
- **Network errors**: Prints error message and skips page
- **Timeout errors**: Logs timeout and continues to next page
- **Invalid JSON**: Handles malformed API responses
- **Missing dependencies**: Provides installation instructions
- **Invalid URLs**: Detects invalid category URLs and exits gracefully

## Limitations

- Limited to LCSC categories (cannot scrape arbitrary websites)
- API page limit: typically 25 products per page
- Respects server rate limits via configurable delays
- Description fallback requires additional requests (slower)

## Troubleshooting

### No data scraped
- Verify `BASE_URL` is a valid LCSC category page
- Check your internet connection
- Try increasing `TIMEOUT` value

### Missing descriptions
- Some products may not have descriptions on LCSC
- Enable `DEBUG_MODE` to see which products are missing data

### Rate limiting
- Increase `DELAY` value (e.g., to 2.0 or higher)
- Reduce `MAX_PAGES` to fetch fewer pages

### Excel export fails
- Ensure `openpyxl` is installed: `pip install openpyxl`
- The script will automatically save to CSV as a fallback

## License

This project is provided as-is for educational and personal use.

## Disclaimer

This scraper respects LCSC's robots.txt and uses reasonable delays between requests. Always check a website's terms of service before scraping. The author is not responsible for misuse of this tool.
