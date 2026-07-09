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



COMMODITY_TICKERS = {
    "Gold": "GC=F",
    "Silver": "SI=F",
    "Crude Oil WTI": "CL=F",
    "Copper": "HG=F",
    "Brent Oil": "BZ=F",
    "Natural Gas": "NG=F",
}

CRYPTO_TICKERS = {
    "Bitcoin": "BTC-USD",
    "Ethereum": "ETH-USD",
    "Solana": "SOL-USD",
    "Cardano": "ADA-USD",
    "Ripple": "XRP-USD",
}

CURRENCY_TICKERS = {
    "GBP/USD": "GBPUSD=X",
    "EUR/USD": "EURUSD=X",
    "USD/CHF": "CHF=X",
    "USD/JPY": "JPY=X",
    "DXY": "DX-Y.NYB",
    "USD/INR": "INR=X",
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

# Browser-like User-Agent. Some feeds (e.g. investing.com) return HTTP 403 to
# the default urllib/feedparser agent, especially from datacenter IPs such as
# GitHub Actions runners. Sending a real browser UA avoids those blocks.
NEWS_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# Reliable RSS sources that do not block bots / datacenter IPs. Google News
# search RSS is the most robust fallback and is listed first.
NEWS_FEEDS = [
    {
        "name": "Google News - India Markets",
        "url": (
            "https://news.google.com/rss/search?"
            "q=nifty+sensex+india+stock+market+when:1d&hl=en-IN&gl=IN&ceid=IN:en"
        ),
    },
    {
        "name": "Google News - Global Markets",
        "url": (
            "https://news.google.com/rss/search?"
            "q=stock+market+fed+crude+oil+gold+when:1d&hl=en-US&gl=US&ceid=US:en"
        ),
    },
    {
        "name": "Economic Times Markets",
        "url": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    },
    {
        "name": "LiveMint Markets",
        "url": "https://www.livemint.com/rss/markets",
    },
    {
        "name": "Yahoo Finance",
        "url": "https://finance.yahoo.com/news/rssindex",
    },
]

NEWS_KEYWORDS = [
    "nifty",
    "sensex",
    "india",
    "rbi",
    "fed",
    "inflation",
    "crude",
    "oil",
    "gold",
    "dollar",
    "rupee",
    "usd/inr",
    "nasdaq",
    "dow",
    "china",
    "japan",
    "bank",
    "fii",
    "dii",
    "earnings",
]