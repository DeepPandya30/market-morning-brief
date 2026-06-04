# Market Morning Brief

Fully automated pre-market report generator for Indian market morning meetings.

It fetches:

- Global market indices: Nasdaq, Dow Jones, S&P 500, FTSE, CAC, DAX, Hang Seng, Nikkei
- NSE index snapshot, India VIX, Indian sector indices
- FII/DII institutional flow
- Nifty and Bank Nifty option-chain support, resistance and PCR
- Optional GIFT Nifty if available in fetched index snapshot

It generates:

- `reports/morning_report.md`
- `dashboard/index.html`
- `docs/index.html` for GitHub Pages
- raw and processed JSON data files

## Local Run

### Mac/Linux

```bash
cd market-morning-brief
python -m venv .venv
source .venv/bin/activate
pip install --upgrade -r requirements.txt
python scripts/generate_report.py
open dashboard/index.html
```

### Windows PowerShell

```powershell
cd market-morning-brief
python -m venv .venv
.\.venv\Scripts\activate
pip install --upgrade -r requirements.txt
python scripts\generate_report.py
start dashboard\index.html
```

## GitHub Action

The workflow is already included:

```text
.github/workflows/morning-report.yml
```

It runs Monday to Friday at `03:00 UTC`, which is `08:30 AM IST`.

You can also run it manually from GitHub Actions using `workflow_dispatch`.

## GitHub Pages Hosting

This project writes the dashboard to:

```text
docs/index.html
```

In GitHub:

1. Open repository Settings
2. Go to Pages
3. Source: Deploy from branch
4. Branch: `main`
5. Folder: `/docs`
6. Save

Your report will be hosted as:

```text
https://YOUR_USERNAME.github.io/market-morning-brief/
```

## Important Notes

NSE endpoints can sometimes block requests depending on network, cookies, IP, or request timing. The code is defensive: if one source fails, the report still generates and shows fetch warnings.

This report is for meeting discussion and research only. It is not financial advice.


