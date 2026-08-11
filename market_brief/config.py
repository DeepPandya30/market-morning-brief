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

# Yahoo Finance tickers for the two index charts (moving averages + indicators).
INDEX_TECHNICAL_TICKERS = {
    "NIFTY 50": "^NSEI",
    "NIFTY BANK": "^NSEBANK",
}

# Moving averages plotted on the index technical charts and summarised in the
# MA table. Anything longer than the fetched history is reported as N/A.
MA_PERIODS = (20, 50, 100, 200)

# Bars kept in the dashboard payload per index. Enough for a 200-DMA overlay to
# be visible without bloating the embedded JSON.
INDEX_SERIES_BARS = 140

# NIFTY 50 constituents keyed by NSE symbol -> (display name, sector bucket).
# NSE rebalances this index twice a year, so this list needs a manual refresh
# after each reconstitution; fetch_nifty50_pivots() warns for any symbol that
# returns no data so a stale entry shows up in the run log.
NIFTY50_CONSTITUENTS = {
    "ADANIENT": ("Adani Enterprises", "Conglomerate"),
    "ADANIPORTS": ("Adani Ports", "Infrastructure"),
    "APOLLOHOSP": ("Apollo Hospitals", "Healthcare"),
    "ASIANPAINT": ("Asian Paints", "Consumer"),
    "AXISBANK": ("Axis Bank", "Financials"),
    "BAJAJ-AUTO": ("Bajaj Auto", "Auto"),
    "BAJAJFINSV": ("Bajaj Finserv", "Financials"),
    "BAJFINANCE": ("Bajaj Finance", "Financials"),
    "BEL": ("Bharat Electronics", "Capital Goods"),
    "BHARTIARTL": ("Bharti Airtel", "Telecom"),
    "CIPLA": ("Cipla", "Pharma"),
    "COALINDIA": ("Coal India", "Energy"),
    "DRREDDY": ("Dr Reddy's Labs", "Pharma"),
    "EICHERMOT": ("Eicher Motors", "Auto"),
    "ETERNAL": ("Eternal (Zomato)", "Consumer"),
    "GRASIM": ("Grasim Industries", "Materials"),
    "HCLTECH": ("HCL Technologies", "IT"),
    "HDFCBANK": ("HDFC Bank", "Financials"),
    "HDFCLIFE": ("HDFC Life", "Financials"),
    "HINDALCO": ("Hindalco", "Metals"),
    "HINDUNILVR": ("Hindustan Unilever", "FMCG"),
    "ICICIBANK": ("ICICI Bank", "Financials"),
    "INDIGO": ("InterGlobe Aviation", "Services"),
    "INFY": ("Infosys", "IT"),
    "ITC": ("ITC", "FMCG"),
    "JIOFIN": ("Jio Financial", "Financials"),
    "JSWSTEEL": ("JSW Steel", "Metals"),
    "KOTAKBANK": ("Kotak Mahindra Bank", "Financials"),
    "LT": ("Larsen & Toubro", "Capital Goods"),
    "M&M": ("Mahindra & Mahindra", "Auto"),
    "MARUTI": ("Maruti Suzuki", "Auto"),
    "MAXHEALTH": ("Max Healthcare", "Healthcare"),
    "NESTLEIND": ("Nestle India", "FMCG"),
    "NTPC": ("NTPC", "Power"),
    "ONGC": ("ONGC", "Energy"),
    "POWERGRID": ("Power Grid", "Power"),
    "RELIANCE": ("Reliance Industries", "Energy"),
    "SBILIFE": ("SBI Life", "Financials"),
    "SBIN": ("State Bank of India", "Financials"),
    "SHRIRAMFIN": ("Shriram Finance", "Financials"),
    "SUNPHARMA": ("Sun Pharma", "Pharma"),
    "TATACONSUM": ("Tata Consumer", "FMCG"),
    # Tata Motors demerged; the passenger-vehicle entity (TMPV) is the index member.
    "TMPV": ("Tata Motors Passenger Vehicles", "Auto"),
    "TATASTEEL": ("Tata Steel", "Metals"),
    "TCS": ("Tata Consultancy Services", "IT"),
    "TECHM": ("Tech Mahindra", "IT"),
    "TITAN": ("Titan Company", "Consumer"),
    "TRENT": ("Trent", "Consumer"),
    "ULTRACEMCO": ("UltraTech Cement", "Materials"),
    "WIPRO": ("Wipro", "IT"),
}

# Trading sessions used for the rolling % change columns in the pivot table.
LOOKBACK_SESSIONS = {"week": 5, "month": 21}

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
    # Corporate filings event calendar. Dates are DD-MM-YYYY; passing the same
    # value for from/to returns exactly one day of board meetings.
    "event_calendar": (
        f"{NSE_BASE_URL}/api/event-calendar"
        "?index=equities&from_date={from_date}&to_date={to_date}"
    ),
    # Unfiltered feed, used as a fallback when the ranged query fails. It returns
    # the whole forward window, so callers must filter by date themselves.
    "event_calendar_all": f"{NSE_BASE_URL}/api/event-calendar",
}

EVENT_CALENDAR_REFERER = f"{NSE_BASE_URL}/companies-listing/corporate-filings-event-calendar"

# Coarse buckets used to group and colour-code event calendar rows. Matched in
# order against the NSE "purpose" text, so specific patterns come first and
# anything unmatched falls through to "Other".
EVENT_CATEGORY_KEYWORDS = [
    ("Results", ("financial result", "quarterly result", "audited result", "results")),
    ("Dividend", ("dividend",)),
    ("Buyback", ("buy back", "buyback")),
    ("Bonus / Split", ("bonus", "stock split", "sub-division", "split")),
    ("Fund Raising", ("fund raising", "raising of funds", "preferential", "rights issue", "debenture")),
    ("M&A / Restructuring", ("amalgamation", "merger", "demerger", "acquisition", "scheme of arrangement")),
]

# Rows shown in the markdown report before it truncates. The dashboard Events
# tab always carries the full list; the report stays readable (and listenable).
EVENT_MARKDOWN_LIMIT = 25

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