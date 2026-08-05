# 📈 Interactive Morning Market Brief

[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-Live%20Dashboard-blue?logo=github)](https://DeepPandya30.github.io/market-morning-brief/)
![Python](https://img.shields.io/badge/Python-3.10%2B-green?logo=python)
![Automation](https://img.shields.io/badge/Automation-GitHub%20Actions-orange?logo=githubactions)
![Schedule](https://img.shields.io/badge/Runs-Mon--Fri%20pre--market%20IST-purple)
![Status](https://img.shields.io/badge/Purpose-Internal%20Market%20Brief-lightgrey)

A fully automated **pre-market dashboard** for Indian market morning meetings.

This project fetches market data, scores market signals, generates a meeting-ready markdown report, and publishes an interactive GitHub Pages dashboard before the market opens.

> ⚠️ This project is for internal market preparation and discussion only. It is **not financial advice**.

---

## 🔗 Live Dashboard

👉 **Dashboard URL:**  
https://DeepPandya30.github.io/market-morning-brief/

---

## ✨ Key Highlights

- Automated market data collection
- Pre-market signal scoring
- Meeting-ready markdown report
- Interactive GitHub Pages dashboard
- Historical market bias tracking
- Charts, filters, copy buttons, markdown download, PDF print option
- Browser-based text-to-speech for quick morning briefing
- Scheduled GitHub Action run before market open, with delay-tolerant retries

---

## 📌 What This Dashboard Covers

### 🇮🇳 Indian Market View

- GIFT Nifty / NSE index snapshot, where available
- FII / DII cash market flow
- Nifty option-chain support, resistance and PCR
- Bank Nifty option-chain support, resistance and PCR
- India VIX
- India sector-wise market view
- Nifty 50 constituent pivot table: classic pivot levels (S3–R3) with daily, weekly and monthly % change
- Nifty and Bank Nifty moving averages (20 / 50 / 100 / 200 SMA and EMA)
- Index indicator charts: RSI (14), MACD (12,26,9), Bollinger bands (20,2), ATR (14)

### 🌎 Global Markets

- **US Markets:** Nasdaq, Dow Jones, S&P 500
- **Europe Markets:** FTSE 100, CAC 40, DAX
- **Asia Markets:** Hang Seng, Nikkei 225

### 🛢️ Commodities

- Gold
- Silver
- Crude Oil WTI
- Brent Oil
- Copper

### ₿ Crypto Market

- Bitcoin
- Ethereum
- Solana
- Cardano
- Ripple

### 💱 Currency Market

- GBP/USD
- EUR/USD
- USD/CHF
- USD/JPY
- DXY
- USD/INR

### 📊 Signal Analytics

- Overall market bias
- Signal score breakdown
- Bullish / bearish / neutral signal classification
- Historical bias trend
- Meeting summary generation

---

## 🧭 Dashboard Sections

The interactive dashboard is divided into focused tabs:

| Tab | Purpose |
|---|---|
| **Overview** | Quick market summary, bias, score and meeting notes |
| **Global Markets** | US, Europe and Asia market snapshot with region filter |
| **Sectors** | Indian sector-wise market movement with search and filters |
| **Nifty 50** | Constituent pivot table — pivot levels, daily/weekly/monthly % change, RSI, breadth, sector roll-up, CSV export |
| **Technicals** | Nifty and Bank Nifty moving-average ladder plus RSI, MACD and Bollinger charts |
| **Signals** | Detailed signal score breakdown |
| **History** | Historical bias score trend |
| **Full Report** | Complete markdown report for morning discussion |

---

## 🖥️ Interactive Dashboard Features

- Region-wise global market filter
- Sector search
- Positive / negative sector filter
- Signal status filter
- Auto-updating score charts
- Historical bias score line chart
- Copy meeting summary button
- Copy full markdown report button
- Download markdown report
- Print / save as PDF
- Browser text-to-speech:
  - Listen to meeting summary
  - Listen to full market report

---

## ⚙️ How It Works

```mermaid
flowchart TD
    A[GitHub Action Scheduler] --> B[Run Python Report Generator]
    B --> C[Fetch Market Data]
    C --> D[Process Signals]
    D --> E[Generate Market Bias Score]
    E --> F[Create Markdown Report]
    E --> G[Update JSON Data Files]
    F --> H[reports/morning_report.md]
    G --> I[docs/data/latest_summary.json]
    G --> J[docs/data/history.json]
    I --> K[GitHub Pages Dashboard]
    J --> K
```

---

## 🗂️ Project Structure

```text
market-morning-brief/
│
├── .github/
│   └── workflows/
│       └── morning-brief.yml
│
├── data/
│   └── processed/
│       ├── latest_summary.json
│       └── history.json
│
├── docs/
│   ├── index.html
│   └── data/
│       ├── latest_summary.json
│       └── history.json
│
├── reports/
│   └── morning_report.md
│
├── runtime dashboard/
│   └── index.html
│
├── scripts/
│   └── generate_report.py
│
├── requirements.txt
└── README.md
```

---

## 🚀 Local Run

### macOS / Linux

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade -r requirements.txt
python scripts/generate_report.py
open docs/index.html
```

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install --upgrade -r requirements.txt
python scripts\generate_report.py
start docs\index.html
```

---

## 📤 Output Files

After running the script, the following files are generated or updated:

```text
reports/morning_report.md
runtime dashboard/index.html
docs/index.html
data/processed/latest_summary.json
data/processed/history.json
docs/data/latest_summary.json
docs/data/history.json
```

### File Purpose

| File | Purpose |
|---|---|
| `reports/morning_report.md` | Meeting-ready markdown report |
| `docs/index.html` | GitHub Pages dashboard |
| `docs/data/latest_summary.json` | Latest dashboard data |
| `docs/data/history.json` | Historical trend data |
| `data/processed/latest_summary.json` | Local processed latest summary |
| `data/processed/history.json` | Local processed historical summary |

---

## 🌐 GitHub Pages Setup

Use GitHub Pages with the following settings:

```text
Source: Deploy from a branch
Branch: main
Folder: /docs
```

After setup, the dashboard will be available at:

```text
https://DeepPandya30.github.io/market-morning-brief/
```

---

## ⏰ GitHub Action Schedule

The workflow targets **Monday to Friday, 6:45–9:10 AM IST**, so the dashboard is ready before the morning market meeting.

GitHub queues scheduled workflows on a best-effort basis, and this repository has consistently seen them start **2.5 to 6 hours late** — a single `cron` at 02:20 UTC (07:50 IST) was actually firing between 04:50 and 06:20 UTC (10:20–11:50 IST). Changing the cron minute does not fix that.

So the workflow fires **seven schedules** spread from 21:50 UTC to 02:20 UTC, and a gate step decides at *execution* time whether that attempt should do the work:

```text
RUN   if it is a weekday, the clock is between 06:45 and 09:10 IST,
      and no report has been published for today yet
SKIP  otherwise (exits in seconds)
```

The early slots absorb a delayed queue; the later ones cover the queue running on time. The first attempt that lands inside the window publishes the report, and every other attempt that day no-ops. Manual `workflow_dispatch` runs always bypass the gate.

```yaml
- cron: "50 21 * * 0-4"   # 03:20 IST
- cron: "20 22 * * 0-4"   # 03:50 IST
- cron: "20 23 * * 0-4"   # 04:50 IST
- cron: "20 0 * * 1-5"    # 05:50 IST
- cron: "20 1 * * 1-5"    # 06:50 IST
- cron: "50 1 * * 1-5"    # 07:20 IST
- cron: "20 2 * * 1-5"    # 07:50 IST
```

Every run's Actions summary records the RUN/SKIP verdict and the reason, so the daily behaviour is auditable. If GitHub's backlog ever pushes *every* attempt past 09:10 IST, no report is published that day — trigger it manually in that case.

---

## 🧪 Manual GitHub Action Run

You can also trigger the workflow manually from GitHub:

```text
Repository → Actions → Morning Market Brief → Run workflow
```

This is useful when:

- You want to refresh the dashboard manually
- The scheduled workflow did not run
- You made changes to the report generator
- You want to test dashboard updates

---

## 🧾 Example Morning Workflow

1. GitHub Action runs in the 6:45-9:10 AM IST pre-market window.
2. Python script fetches market data.
3. Market signals are scored.
4. Markdown report is generated.
5. JSON files are updated.
6. Dashboard is published through GitHub Pages.
7. Team opens the dashboard before the morning meeting.
8. Summary can be copied, downloaded, printed, or played using text-to-speech.

---

## 🛠️ Troubleshooting

### Dashboard is showing old data

Try the following:

1. Refresh the browser.
2. Open the dashboard in incognito mode.
3. Check whether the latest GitHub Action completed successfully.
4. Confirm that files inside `docs/data/` were updated.
5. Wait a few minutes for GitHub Pages cache to refresh.

### GitHub Action did not run

Check:

- Workflow file exists inside `.github/workflows/`
- Cron syntax is valid
- Repository Actions are enabled
- Branch is set to `main`
- Workflow has permission to commit updated files

### Data is missing for some markets

Some market sources may be unavailable, delayed, rate-limited, or blocked temporarily. The dashboard is designed to continue generating the report with available data.

### Git push rejected

If your local branch is behind GitHub:

```bash
git pull --rebase origin main
git push origin main
```

---

## 🔐 Notes on Data Reliability

Market data availability may depend on:

- Exchange source availability
- Public API limits
- Website blocking or rate limits
- Market holidays
- Delayed global market feeds
- GitHub Actions network availability

The dashboard should be used as a discussion support tool, not as a trading recommendation system.

---

## 📍 Roadmap Ideas

- Add email or Telegram morning notification
- Add confidence score for each signal
- Add separate Nifty and Bank Nifty bias cards
- Add market holiday detection
- Add earnings / event calendar
- Add fear-greed style sentiment meter
- Add heatmap for sectors
- Add CSV export
- Add mobile-first dashboard improvements
- Add auto-generated PDF report

---

## ⚠️ Disclaimer

This project is created for **morning discussion and internal market preparation only**.

It does not provide investment advice, trading advice, buy/sell recommendations, or financial planning guidance. Always verify market data from official and trusted sources before making financial decisions.
