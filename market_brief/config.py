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

# ---------------------------------------------------------------------------
# Event calendar sector tagging
#
# The NSE event-calendar feed carries no industry field, and NSE's own
# quote/stockIndices endpoints are blocked from datacenter IPs (the same reason
# technicals.py uses yfinance). Sectors are therefore resolved from Yahoo
# Finance company profiles and cached on disk so a symbol is only ever looked
# up once — repeat runs read the cache and make no network calls at all.
SECTOR_CACHE_PATH = PROCESSED_DIR / "sector_map.json"

# Yahoo profiles are one HTTP call per symbol (~1.3s), so a busy results day is
# capped: anything beyond the cap stays "Unclassified" this run and is picked up
# by the next one once the cache has warmed.
SECTOR_LOOKUP_MAX_NEW = 120
SECTOR_LOOKUP_WORKERS = 8

# Yahoo's GICS-style sectors mapped onto the same bucket vocabulary used by
# NIFTY50_CONSTITUENTS, so the Events tab and the Nifty 50 tab speak one
# taxonomy instead of two.
YF_SECTOR_BUCKETS = {
    "Technology": "IT",
    "Financial Services": "Financials",
    "Healthcare": "Healthcare",
    "Consumer Cyclical": "Consumer",
    "Consumer Defensive": "FMCG",
    "Energy": "Energy",
    "Basic Materials": "Materials",
    "Industrials": "Capital Goods",
    "Real Estate": "Realty",
    "Utilities": "Power",
    "Communication Services": "Telecom",
}

# Industry-text overrides applied before the sector mapping above, because
# Yahoo's top-level sector is too coarse for the buckets this dashboard uses
# (drug makers are "Healthcare", car makers are "Consumer Cyclical", steel is
# "Basic Materials"). Matched in order against the lowercased industry name.
YF_INDUSTRY_OVERRIDES = [
    ("Pharma", ("drug", "pharma", "biotech")),
    ("Auto", ("auto", "vehicle", "tyre", "tire")),
    ("Metals", ("steel", "metal", "copper", "aluminum", "aluminium", "gold", "silver", "mining", "coking coal")),
    ("Infrastructure", ("engineering & construction", "infrastructure", "airport", "railroad", "marine shipping")),
    ("Media", ("entertainment", "broadcasting", "publishing", "advertising")),
    ("Power", ("utilities", "power", "renewable")),
    ("Services", ("business services", "consulting", "staffing", "logistics")),
]

SECTOR_UNKNOWN = "Unclassified"

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

# ---------------------------------------------------------------------------
# EIA Weekly Natural Gas Storage Report (WNGSR)
# ---------------------------------------------------------------------------
# Published every Thursday at 10:30 a.m. eastern time (20:00 IST) for the week
# ending the previous Friday. Both endpoints below are the plain-text mirrors
# EIA maintains for automated consumers, so neither needs an API key. The
# human-facing report referenced from the dashboard lives at NG_STORAGE_REPORT_URL.
#
# ir.eia.gov/ngs/wngsr.html returns HTTP 403 to non-browser agents; the .csv and
# .xls mirrors do not, which is why those two are used here.
NG_STORAGE_REPORT_URL = "https://ir.eia.gov/ngs/ngs.html"
NG_STORAGE_LANDING_URL = "https://www.eia.gov/naturalgas/reports.php#/T202"

# Current week only: per-region stocks, net change, and the year-ago / 5-year
# comparisons that the report headlines.
NG_STORAGE_CSV_URL = "https://ir.eia.gov/ngs/wngsr.csv"

# Full weekly history back to Jan 2010, two sheets: end-of-week stocks
# ("html_report_history") and weekly net changes ("weekly_net_changes"). Used
# for the trajectory chart and the 5-year seasonal band.
NG_STORAGE_HISTORY_URL = "https://ir.eia.gov/ngs/ngshistory.xls"

# EIA's five-region structure plus the two South Central sub-regions. Order is
# the order the report prints them in, which the dashboard table preserves.
NG_STORAGE_REGIONS = (
    "East",
    "Midwest",
    "Mountain",
    "Pacific",
    "South Central",
    "Salt",
    "Nonsalt",
    "Total",
)

# South Central is reported both as a total and split into salt-dome and
# non-salt storage. The split rows are indented in the source and are shown as
# child rows in the dashboard rather than as peers.
NG_STORAGE_SUBREGIONS = frozenset({"Salt", "Nonsalt"})

# Weeks of end-of-week stocks kept in the dashboard payload. Three years is
# enough to see the current trajectory against two prior cycles without
# bloating the embedded JSON.
NG_STORAGE_HISTORY_WEEKS = 157

# Years averaged for the seasonal comparison band. EIA itself headlines a
# 5-year average, so the chart uses the same window for consistency.
NG_STORAGE_SEASONAL_YEARS = 5

# Injection season runs April through October; withdrawal season is the rest.
# Used to label whether a build or a draw is the seasonal norm.
NG_INJECTION_MONTHS = frozenset({4, 5, 6, 7, 8, 9, 10})

# Cache written after every successful fetch. A failed EIA fetch falls back to
# this file so one bad morning cannot blank the dashboard section.
NG_STORAGE_CACHE_NAME = "natural_gas_storage.json"

# Side-car published next to the dashboard. The Thursday-evening workflow
# rewrites only this file, so the gas section refreshes without regenerating
# the whole morning brief.
NG_STORAGE_SIDECAR_NAME = "natural_gas.json"

# ---------------------------------------------------------------------------
# EIA Weekly Petroleum Status Report (WPSR)
# ---------------------------------------------------------------------------
# Released every Wednesday: the data tables at 10:30 a.m. eastern and the
# Highlights write-up at 1:00 p.m. eastern (23:00 IST on the same Wednesday,
# 22:30 IST while the US is on daylight time). When Monday is a federal
# holiday the whole release slips one day to Thursday.
#
# That is hours after the 07:50 IST morning brief has published, so — exactly
# like the natural gas report — the daily pipeline renders the most recent
# available release and a separate Wednesday-evening job refreshes only this
# section once the new week is out.
PETROLEUM_LANDING_URL = "https://www.eia.gov/petroleum/supply/weekly/"
PETROLEUM_HIGHLIGHTS_URL = "https://www.eia.gov/petroleum/supply/weekly/pdf/highlights.pdf"

# Table 9 (U.S. and PAD District Weekly Estimates) is the one file that carries
# every number the Highlights leads with — stocks, production, refinery runs,
# trade and demand — so a single download covers the whole section. Columns are
# week, prior week, year ago, two years ago, then the two four-week averages.
PETROLEUM_TABLE_URL = "https://ir.eia.gov/wpsr/table9.csv"

# The file is Windows-encoded: en-dashes in the "no data" cells are 0x96, which
# is not valid UTF-8, so decoding has to fall back rather than replace.
PETROLEUM_ENCODINGS = ("utf-8-sig", "cp1252")

# Stock levels shown in the dashboard table, in report order. Keyed by the
# (section, row) pair Table 9 uses, because names such as "Commercial" appear
# under both Stocks and Imports.
PETROLEUM_STOCK_ROWS = (
    ("crude_commercial", "Stocks (Million Barrels)", "Commercial", "Crude Oil (commercial, ex-SPR)"),
    ("cushing", "Stocks (Million Barrels)", "Cushing, Oklahoma", "Cushing, Oklahoma (WTI delivery)"),
    ("crude_total", "Stocks (Million Barrels)", "Crude Oil (including SPR)", "Crude Oil (including SPR)"),
    ("spr", "Stocks (Million Barrels)", "SPR", "Strategic Petroleum Reserve"),
    ("gasoline", "Stocks (Million Barrels)", "Total Motor Gasoline", "Total Motor Gasoline"),
    ("distillate", "Stocks (Million Barrels)", "Distillate Fuel Oil", "Distillate Fuel Oil"),
    ("jet_fuel", "Stocks (Million Barrels)", "Kerosene-Type Jet Fuel", "Kerosene-Type Jet Fuel"),
    ("propane", "Stocks (Million Barrels)", "Propane/Propylene", "Propane / Propylene"),
    ("total_ex_spr", "Stocks (Million Barrels)", "Total Stocks (Excluding SPR)", "Total Stocks (excluding SPR)"),
)

# Supply, refining, trade and demand rows. Everything here is thousand barrels
# per day except refinery utilisation, which is a percentage.
PETROLEUM_ACTIVITY_ROWS = (
    ("production", "Crude Oil Production", "Domestic Production", "US Crude Production", "kb/d"),
    ("refinery_utilization", "Refiner Inputs and Utilization", "Percent Utilization", "Refinery Utilisation", "%"),
    ("refinery_inputs", "Refiner Inputs and Utilization", "Crude Oil Inputs", "Refinery Crude Inputs", "kb/d"),
    ("crude_imports", "Imports", "Total Crude Oil Incl SPR", "Crude Imports", "kb/d"),
    ("crude_exports", "Exports", "Crude Oil", "Crude Exports", "kb/d"),
    ("crude_net_imports", "Net Imports (Incl SPR)", "Crude Oil", "Crude Net Imports", "kb/d"),
    ("products_supplied", "Product Supplied", "Total Product Supplied", "Total Products Supplied", "kb/d"),
    ("gasoline_demand", "Product Supplied", "Finished Motor Gasoline", "Gasoline Demand", "kb/d"),
    ("distillate_demand", "Product Supplied", "Distillate Fuel Oil", "Distillate Demand", "kb/d"),
)

# A build this size or larger is treated as a directional move rather than
# noise. EIA's own weekly crude prints swing a few hundred thousand barrels on
# survey timing alone, so anything under a million barrels reads as flat.
PETROLEUM_BUILD_THRESHOLD_MMBBL = 1.0

# Cache written after every successful fetch; a failed fetch falls back to it.
PETROLEUM_CACHE_NAME = "petroleum_status.json"

# Side-car the Wednesday-evening workflow rewrites on its own.
PETROLEUM_SIDECAR_NAME = "petroleum.json"
