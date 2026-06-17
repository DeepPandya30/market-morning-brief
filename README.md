# Interactive Morning Market Brief

Fully automated pre-market dashboard for Indian market morning meetings.

The workflow fetches market data, scores signals, generates a meeting-ready report, and publishes an interactive GitHub Pages dashboard.

## What it covers

- GIFT Nifty / NSE index snapshot where available
- FII / DII cash market flow
- Nifty option-chain support, resistance and PCR
- Bank Nifty option-chain support, resistance and PCR
- India VIX
- US markets: Nasdaq, Dow Jones, S&P 500
- Europe markets: FTSE 100, CAC 40, DAX
- Asia markets: Hang Seng, Nikkei 225
- India sector-wise market view
- Global commodities: Gold, Silver, Crude Oil WTI, Copper, Brent Oil
- Crypto currency: Bitcoin, Ethereum, Solana, Cardano, Ripple
- Currency market: GBP/USD, EUR/USD, USD/CHF, USD/JPY, DXY, USD/INR
- Signal score breakdown
- Historical bias trend
- Interactive filters, charts, copy buttons, print/PDF option, and browser text-to-speech

## Local run

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade -r requirements.txt
python scripts/generate_report.py
open docs/index.html
```

For Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install --upgrade -r requirements.txt
python scripts\generate_report.py
start docs\index.html
```

## Output files

```text
reports/morning_report.md
runtime dashboard/index.html
GitHub Pages docs/index.html
data/processed/latest_summary.json
data/processed/history.json
docs/data/latest_summary.json
docs/data/history.json
```

## GitHub Pages

Use GitHub Pages with:

```text
Source: Deploy from a branch
Branch: main
Folder: /docs
```

Dashboard URL:

```text
https://DeepPandya30.github.io/market-morning-brief/
```

## GitHub Action

The workflow runs Monday to Friday at 7:50 AM IST so the dashboard is ready before 8:00 AM.

Cron used:

```yaml
cron: "20 2 * * 1-5"
```

GitHub cron uses UTC, so 02:20 UTC equals 07:50 IST.

## Interactive dashboard features

- Tabs: Overview, Global Markets, Sectors, Signals, History, Full Report
- Global market filter by region
- Sector search and positive/negative filter
- Signal status filter
- Auto-updating score charts
- Historical bias score line chart
- Listen to meeting summary or full report using browser text-to-speech
- Copy meeting summary
- Copy full markdown report
- Download markdown report
- Print / save as PDF

## Important note

This project is for morning discussion and internal market preparation only. It is not financial advice.
