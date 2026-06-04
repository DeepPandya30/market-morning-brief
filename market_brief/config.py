from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
REPORTS_DIR = BASE_DIR / "reports"
DASHBOARD_DIR = BASE_DIR / "dashboard"
DOCS_DIR = BASE_DIR / "docs"

TIMEZONE = "Asia/Kolkata"

GLOBAL_MARKET_TICKERS = {
    "Nasdaq": "^IXIC",
    "Dow Jones": "^DJI",
    "S&P 500": "^GSPC",
    "FTSE 100": "^FTSE",
    "CAC 40": "^FCHI",
    "DAX": "^GDAXI",
    "Hang Seng": "^HSI",
    "Nikkei 225": "^N225",
}

US_MARKETS = {"Nasdaq", "Dow Jones", "S&P 500"}
EUROPE_MARKETS = {"FTSE 100", "CAC 40", "DAX"}
ASIA_MARKETS = {"Hang Seng", "Nikkei 225"}

SECTOR_KEYWORDS = {
    "NIFTY AUTO",
    "NIFTY BANK",
    "NIFTY FINANCIAL SERVICES",
    "NIFTY FMCG",
    "NIFTY IT",
    "NIFTY MEDIA",
    "NIFTY METAL",
    "NIFTY PHARMA",
    "NIFTY PSU BANK",
    "NIFTY PRIVATE BANK",
    "NIFTY REALTY",
    "NIFTY HEALTHCARE INDEX",
    "NIFTY CONSUMER DURABLES",
    "NIFTY OIL & GAS",
}

NSE_BASE_URL = "https://www.nseindia.com"

NSE_REFERERS = [
    "https://www.nseindia.com/market-data/live-equity-market",
    "https://www.nseindia.com/market-data/live-market-indices",
    "https://www.nseindia.com/option-chain",
    "https://www.nseindia.com/reports/fii-dii",
]

NSE_ENDPOINTS = {
    "all_indices": f"{NSE_BASE_URL}/api/allIndices",
    "fii_dii": f"{NSE_BASE_URL}/api/fiidiiTradeReact",
    "option_chain_old": f"{NSE_BASE_URL}/api/option-chain-indices?symbol={{symbol}}",
    "option_chain_next": (
        f"{NSE_BASE_URL}/api/NextApi/apiClient/GetQuoteApi"
        "?functionName=getSymbolDerivativesData&symbol={symbol}"
    ),
}

OPTION_CHAIN_REFERERS = {
    "NIFTY": "https://www.nseindia.com/get-quote/optionchain/NIFTY/NIFTY-50",
    "BANKNIFTY": "https://www.nseindia.com/get-quotes/derivatives?symbol=BANKNIFTY",
}
