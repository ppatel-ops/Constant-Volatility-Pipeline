import os

# Base URL for NSE Archives
NSE_BASE_URL = "https://nsearchives.nseindia.com/content/fo/"

# Request Headers to mimic a browser (avoids 403 Forbidden)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "application/zip",
    "Referer": "https://www.nseindia.com/"
}

# Risk-free rate assumption (10%)
RISK_FREE_RATE = 0.10

# Directory to save downloaded files (optional caching)
DATA_DIR = "data_cache"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)