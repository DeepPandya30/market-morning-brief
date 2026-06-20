from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

from .utils import money_text, now_ist, number_text, pct_text


def create_report_context(
    data: dict[str, Any],
    score: dict[str, Any],
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    nse = data.get("nse_indices", {})
    sectors = nse.get("sectors", [])
    top_sectors = sectors[:3]
    weak_sectors = list(reversed(sectors[-3:])) if sectors else []
    warnings = data.get("warnings", [])
    return {
        "generated_at": now_ist().strftime("%d %b %Y, %I:%M %p IST"),
        "date": now_ist().strftime("%d %B %Y"),
        "data": data,
        "score": score,
        "history": history or [],
        "top_sectors": top_sectors,
        "weak_sectors": weak_sectors,
        "warnings": warnings,
        "market_view": _market_view(data, score),
        "risk_note": _risk_note(data, score),
    }


def render_markdown(context: dict[str, Any]) -> str:
    data = context["data"]
    score = context["score"]
    nse = data.get("nse_indices", {})
    flow = data.get("fii_dii", {})
    nifty = data.get("option_chains", {}).get("NIFTY", {})
    banknifty = data.get("option_chains", {}).get("BANKNIFTY", {})
    gift = nse.get("gift_nifty")
    vix = nse.get("india_vix")

    lines: list[str] = []
    lines.append(f"# Morning Market Brief - {context['date']}")
    lines.append("")
    lines.append(f"Generated at: **{context['generated_at']}**")
    lines.append("")
    lines.append("## Final View")
    lines.append("")
    lines.append(f"- **Market Bias:** {score['bias']}")
    lines.append(f"- **Score:** {score['score']}")
    lines.append(f"- **Confidence:** {score['confidence']}")
    lines.append(f"- **Meeting View:** {context['market_view']}")
    lines.append("")
    lines.append("## Expected Opening")
    lines.append("")
    if gift:
        lines.append(
            f"- GIFT Nifty: {number_text(gift.get('last'))}, change {number_text(gift.get('change'))} ({pct_text(gift.get('change_pct'))})"
        )
    else:
        lines.append("- GIFT Nifty: Not available from current source. Use available global and NSE signals.")
    lines.append(f"- India VIX: {number_text(vix.get('last') if vix else None)} ({pct_text(vix.get('change_pct') if vix else None)})")
    lines.append("")
    lines.append("## Global Market Cues")
    lines.append("")
    lines.append("| Region | Index | Close | Change % | Date |")
    lines.append("|---|---:|---:|---:|---:|")
    for row in data.get("global_markets", []):
        lines.append(
            f"| {row.get('region')} | {row.get('name')} | {number_text(row.get('close'))} | {pct_text(row.get('change_pct'))} | {row.get('date', '')} |"
        )
    lines.append("")
    lines.extend(_market_group_markdown("Global Commodities", data.get("commodities", []), "Commodity"))
    lines.append("")
    lines.extend(_market_group_markdown("Crypto Currency", data.get("crypto", []), "Coin"))
    lines.append("")
    lines.extend(_market_group_markdown("Currency Market", data.get("currencies", []), "Pair"))
    lines.append("")
    lines.append("## FII / DII Flow")
    lines.append("")
    lines.append(f"- FII net: **{money_text(flow.get('fii_net'))}**")
    lines.append(f"- DII net: **{money_text(flow.get('dii_net'))}**")
    combined = None
    if flow.get("fii_net") is not None or flow.get("dii_net") is not None:
        combined = (flow.get("fii_net") or 0) + (flow.get("dii_net") or 0)
    lines.append(f"- Combined institutional flow: **{money_text(combined)}**")
    lines.append("")
    lines.append("## Open Interest View")
    lines.append("")
    lines.append("| Index | Spot | PCR | Support | Resistance | Source |")
    lines.append("|---|---:|---:|---:|---:|---|")
    lines.append(_option_markdown_row("Nifty", nifty))
    lines.append(_option_markdown_row("Bank Nifty", banknifty))
    lines.append("")
    lines.append("## Sector View")
    lines.append("")
    lines.append("### Strong Sectors")
    for sector in context["top_sectors"]:
        lines.append(f"- {sector.get('name')}: {pct_text(sector.get('change_pct'))}")
    if not context["top_sectors"]:
        lines.append("- Sector data not available.")
    lines.append("")
    lines.append("### Weak Sectors")
    for sector in context["weak_sectors"]:
        lines.append(f"- {sector.get('name')}: {pct_text(sector.get('change_pct'))}")
    if not context["weak_sectors"]:
        lines.append("- Sector data not available.")
    lines.append("")
    lines.append("## Signal Score Breakdown")
    lines.append("")
    lines.append("| Signal | Score | Status | Reason |")
    lines.append("|---|---:|---|---|")
    for item in score.get("components", []):
        lines.append(f"| {item['name']} | {item['score']} | {item['status']} | {item['reason']} |")
    lines.append("")
    lines.append("## Discussion Plan")
    lines.append("")
    lines.append(f"- {context['market_view']}")
    lines.append(f"- {context['risk_note']}")
    lines.append("- Avoid aggressive trades in the first 5–10 minutes if opening gap is large.")
    lines.append("- Confirm direction with Nifty/Bank Nifty holding above support or rejecting near resistance.")
    lines.append("")
    lines.append("## Important Market News")
    lines.append("")
    news_rows = data.get("market_news", [])[:10]
    if news_rows:
        for item in news_rows:
            title = item.get("title") or "Untitled"
            source = item.get("source") or "News"
            link = item.get("link") or ""
            if link:
                lines.append(f"- **{title}** — {source}  ")
                lines.append(f"  {link}")
            else:
                lines.append(f"- **{title}** — {source}")
    else:
        lines.append("- No market news available.")
    lines.append("")
    if context["warnings"]:
        lines.append("## Fetch Warnings")
        lines.append("")
        for warning in context["warnings"]:
            lines.append(f"- {warning}")
        lines.append("")
    lines.append("---")
    lines.append("This report is generated automatically for pre-market discussion. It is not financial advice.")
    return "\n".join(lines)


def render_html(context: dict[str, Any]) -> str:
    
    markdown = render_markdown(context)
    payload = _dashboard_payload(context, markdown)
    payload_json = json.dumps(payload, ensure_ascii=False, default=str).replace("</", "<\\/")
    

    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
  <meta http-equiv="Pragma" content="no-cache">
  <meta http-equiv="Expires" content="0">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Interactive Morning Market Brief</title>
  <style>
    :root {
      --bg: #f5f7fb;
      --card: #ffffff;
      --text: #172033;
      --muted: #667085;
      --line: #e5e7eb;
      --dark: #0f172a;
      --brand: #2563eb;
      --brand-soft: #dbeafe;
      --good: #047857;
      --good-soft: #d1fae5;
      --bad: #b91c1c;
      --bad-soft: #fee2e2;
      --neutral: #92400e;
      --neutral-soft: #fef3c7;
    }
    * { box-sizing: border-box; }
    body { font-family: Inter, Arial, sans-serif; margin: 0; background: var(--bg); color: var(--text); }
    header { background: linear-gradient(135deg, #0f172a, #1e3a8a); color: white; padding: 28px 24px; }
    main { max-width: 1180px; margin: 0 auto; padding: 22px; }
    h1 { margin: 0 0 6px; font-size: 32px; }
    h2 { margin: 0 0 14px; }
    h3 { margin: 0 0 10px; }
    button, select, input { font: inherit; }
    .top-line { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; align-items: center; }
    .pill { display: inline-flex; align-items: center; gap: 8px; border-radius: 999px; padding: 8px 12px; background: rgba(255,255,255,.14); color: white; }
    .tabs { display: flex; gap: 8px; flex-wrap: wrap; margin: 18px 0; position: sticky; top: 0; background: rgba(245,247,251,.96); z-index: 5; padding: 12px 0; backdrop-filter: blur(8px); }
    .tab-btn { border: 1px solid var(--line); background: white; color: var(--text); padding: 10px 14px; border-radius: 999px; cursor: pointer; }
    .tab-btn.active { background: var(--brand); color: white; border-color: var(--brand); }
    .panel { display: none; }
    .panel.active { display: block; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }
    .grid-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }
    .card { background: var(--card); border-radius: 16px; padding: 18px; box-shadow: 0 4px 18px rgba(15,23,42,.08); margin-bottom: 18px; border: 1px solid rgba(15,23,42,.04); }
    .metric { font-size: 30px; font-weight: 800; letter-spacing: -.02em; }
    .muted { color: var(--muted); }
    .small { font-size: 13px; }
    .summary { font-size: 17px; line-height: 1.55; }
    .badge { border-radius: 999px; padding: 5px 9px; display: inline-block; font-weight: 700; font-size: 12px; }
    .badge.good { background: var(--good-soft); color: var(--good); }
    .badge.bad { background: var(--bad-soft); color: var(--bad); }
    .badge.neutral { background: var(--neutral-soft); color: var(--neutral); }
    .badge.info { background: var(--brand-soft); color: var(--brand); }
    .controls { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 12px; align-items: center; }
    .controls input, .controls select { padding: 10px 12px; border: 1px solid var(--line); border-radius: 10px; background: white; min-width: 170px; }
    .action-btn { border: 0; background: var(--dark); color: white; padding: 10px 13px; border-radius: 10px; cursor: pointer; }
    .action-btn.secondary { background: var(--brand); }
    .action-btn.danger { background: #b91c1c; }
    .tts-panel { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; align-items: center; margin-top: 12px; padding: 12px; border: 1px solid var(--line); border-radius: 12px; background: #f8fafc; }
    .tts-panel label { display: flex; flex-direction: column; gap: 6px; font-size: 12px; color: var(--muted); font-weight: 700; }
    .tts-panel select, .tts-panel input { min-width: 0; width: 100%; }
    .table-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 12px; }
    table { width: 100%; border-collapse: collapse; font-size: 14px; background: white; }
    th, td { padding: 10px; border-bottom: 1px solid var(--line); text-align: left; white-space: nowrap; }
    th { background: #f1f5f9; cursor: pointer; user-select: none; position: sticky; top: 0; }
    tr:hover td { background: #f8fafc; }
    pre { white-space: pre-wrap; background: #0b1020; color: #e5e7eb; padding: 16px; border-radius: 12px; overflow-x: auto; line-height: 1.45; }
    canvas { width: 100%; max-height: 360px; border: 1px solid var(--line); border-radius: 12px; background: white; }
    .oi-card { border-left: 5px solid var(--brand); }
    .footer-note { text-align: center; color: var(--muted); padding: 18px 0 34px; }
    @media print {
      .tabs, .controls, .action-btn { display: none !important; }
      .panel { display: block !important; }
      body { background: white; }
      .card { box-shadow: none; border: 1px solid #ddd; }
    }
    .heatmap-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(155px, 1fr));
  gap: 10px;
  margin: 14px 0 18px;
}

.heatmap-cell {
  border-radius: 14px;
  padding: 14px;
  min-height: 92px;
  border: 1px solid rgba(15,23,42,.08);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  cursor: default;
  transition: transform .15s ease, box-shadow .15s ease;
}

.heatmap-cell:hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 20px rgba(15,23,42,.18);
}

.heatmap-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  margin: 4px 0 4px;
  font-size: 12px;
  color: var(--muted);
}

.heatmap-legend .swatch {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.heatmap-legend .box {
  width: 16px;
  height: 16px;
  border-radius: 4px;
  border: 1px solid rgba(15,23,42,.12);
}

.heatmap-cell strong {
  font-size: 14px;
  line-height: 1.25;
}

.heat-value {
  font-size: 22px;
  font-weight: 800;
  margin-top: 8px;
}

.heat-strong-up {
  background: #bbf7d0;
  color: #14532d;
}

.heat-up {
  background: #dcfce7;
  color: #166534;
}

.heat-flat {
  background: #fef3c7;
  color: #92400e;
}

.heat-down {
  background: #fee2e2;
  color: #991b1b;
}

.heat-strong-down {
  background: #fecaca;
  color: #7f1d1d;
}

.pcr-summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.pcr-mini-card {
  background: #f8fafc;
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 14px;
}

.news-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 14px;
}

.news-card {
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 14px;
  background: #ffffff;
}

.news-card a {
  color: var(--brand);
  font-weight: 800;
  text-decoration: none;
}

.news-meta {
  margin-top: 8px;
  font-size: 12px;
  color: var(--muted);
}

.meeting-mode {
  background: linear-gradient(135deg, #0f172a, #1e3a8a);
  color: white;
}

.meeting-mode .muted {
  color: #cbd5e1;
}

.big-plan {
  font-size: 22px;
  line-height: 1.5;
  font-weight: 800;
}


  </style>
</head>
<body>
<header>
  <div class="top-line">
    <div>
      <h1>Interactive Morning Market Brief</h1>
      <div id="generatedAt" class="muted" style="color:#cbd5e1"></div>
    </div>
    <div class="pill"><span>Auto-generated</span><strong>Pre-market</strong></div>
  </div>
</header>
<main>
  <nav class="tabs" aria-label="Dashboard tabs">
    <button class="tab-btn active" data-tab="overview">Overview</button>
    <button class="tab-btn" data-tab="global">Global Markets</button>
    <button class="tab-btn" data-tab="commodities">Commodities</button>
    <button class="tab-btn" data-tab="crypto">Crypto</button>
    <button class="tab-btn" data-tab="currency">Currency</button>
    <button class="tab-btn" data-tab="sectors">Sectors</button>
    <button class="tab-btn" data-tab="signals">Signals</button>
    <button class="tab-btn" data-tab="history">History</button>
    <button class="tab-btn" data-tab="news">News</button>
    <button class="tab-btn" data-tab="report">Full Report</button>
    
  </nav>

  <div class="card meeting-mode">
  <h2>Meeting Mode</h2>
  <div id="todayPlan" class="big-plan"></div>
  <p id="topSignals" class="summary"></p>
  <p id="mainRisk" class="summary muted"></p>
</div>

  <section id="overview" class="panel active">
    <div id="metricGrid" class="grid"></div>
    <div class="card">
      <h2>Meeting Summary</h2>
      <p id="marketView" class="summary"></p>
      <p id="riskNote" class="summary muted"></p>
      <div class="controls">
        <button class="action-btn secondary" id="copySummaryBtn">Copy meeting summary</button>
        <button class="action-btn" id="printBtn">Print / Save PDF</button>
      </div>
      <div class="tts-panel" aria-label="Text to speech controls">
        <label>Voice
          <select id="ttsVoice"><option value="">Default voice</option></select>
        </label>
        <label>Speed
          <select id="ttsRate">
            <option value="0.85">Slow</option>
            <option value="1" selected>Normal</option>
            <option value="1.15">Fast</option>
          </select>
        </label>
        <label>Read mode
          <select id="ttsMode">
            <option value="summary" selected>Meeting summary</option>
            <option value="full">Full report</option>
          </select>
        </label>
        <button class="action-btn secondary" id="speakBtn">Listen</button>
        <button class="action-btn" id="pauseSpeakBtn">Pause / Resume</button>
        <button class="action-btn danger" id="stopSpeakBtn">Stop</button>
      </div>
      <p id="ttsStatus" class="small muted"></p>
    </div>
    <div class="grid-2">
      <div class="card"><h2>Global Snapshot</h2><canvas id="globalMiniChart" height="260"></canvas></div>
      <div class="card"><h2>Sector Snapshot</h2><canvas id="sectorMiniChart" height="260"></canvas></div>
    </div>
    <div class="grid-2">
      <div class="card"><h2>Commodity Snapshot</h2><canvas id="commodityMiniChart" height="260"></canvas></div>
      <div class="card"><h2>Crypto Snapshot</h2><canvas id="cryptoMiniChart" height="260"></canvas></div>
    </div>
    <div class="grid-2" id="oiCards"></div>
  </section>

  <section id="global" class="panel">
    <div class="card">
      <h2>Global Market Cues</h2>
      <div class="controls">
        <select id="globalRegionFilter">
          <option value="All">All regions</option>
          <option value="US">US</option>
          <option value="Europe">Europe</option>
          <option value="Asia">Asia</option>
        </select>
        <select id="globalSort">
          <option value="change_desc">Change % high to low</option>
          <option value="change_asc">Change % low to high</option>
          <option value="name">Name A to Z</option>
        </select>
      </div>
      <canvas id="globalChart" height="320"></canvas>
      <div class="table-wrap" style="margin-top:14px"><table><thead><tr><th>Region</th><th>Index</th><th>Close</th><th>Change</th><th>Change %</th><th>Date</th></tr></thead><tbody id="globalRows"></tbody></table></div>
    </div>
  </section>

  <section id="commodities" class="panel">
    <div class="card">
      <h2>Global Commodities</h2>
      <p class="muted">Gold, Silver, Crude Oil WTI, Copper, and Brent Oil.</p>
      <div class="controls">
        <select id="commoditySort">
          <option value="change_desc">Change % high to low</option>
          <option value="change_asc">Change % low to high</option>
          <option value="name">Name A to Z</option>
        </select>
      </div>
      <canvas id="commodityChart" height="320"></canvas>
      <div class="table-wrap" style="margin-top:14px"><table><thead><tr><th>Commodity</th><th>Ticker</th><th>Close</th><th>Change</th><th>Change %</th><th>Date</th></tr></thead><tbody id="commodityRows"></tbody></table></div>
    </div>
  </section>

  <section id="crypto" class="panel">
    <div class="card">
      <h2>Crypto Currency</h2>
      <p class="muted">Bitcoin, Ethereum, Solana, Cardano, and Ripple.</p>
      <div class="controls">
        <select id="cryptoSort">
          <option value="change_desc">Change % high to low</option>
          <option value="change_asc">Change % low to high</option>
          <option value="name">Name A to Z</option>
        </select>
      </div>
      <canvas id="cryptoChart" height="320"></canvas>
      <div class="table-wrap" style="margin-top:14px"><table><thead><tr><th>Coin</th><th>Ticker</th><th>Close</th><th>Change</th><th>Change %</th><th>Date</th></tr></thead><tbody id="cryptoRows"></tbody></table></div>
    </div>
  </section>

  <section id="currency" class="panel">
    <div class="card">
      <h2>Currency Market</h2>
      <p class="muted">GBP/USD, EUR/USD, USD/CHF, USD/JPY, DXY, and USD/INR.</p>
      <div class="controls">
        <select id="currencySort">
          <option value="change_desc">Change % high to low</option>
          <option value="change_asc">Change % low to high</option>
          <option value="name">Name A to Z</option>
        </select>
      </div>
      <canvas id="currencyChart" height="320"></canvas>
      <div class="table-wrap" style="margin-top:14px"><table><thead><tr><th>Pair / Index</th><th>Ticker</th><th>Close</th><th>Change</th><th>Change %</th><th>Date</th></tr></thead><tbody id="currencyRows"></tbody></table></div>
    </div>
  </section>

  <section id="sectors" class="panel">
    <div class="card">
      <h2>India Sector View</h2>
      <div class="controls">
        <input id="sectorSearch" placeholder="Search sector..." />
        <select id="sectorSentimentFilter">
          <option value="All">All sectors</option>
          <option value="Positive">Positive only</option>
          <option value="Negative">Negative only</option>
        </select>
        <select id="sectorSort">
          <option value="change_desc">Change % high to low</option>
          <option value="change_asc">Change % low to high</option>
          <option value="name">Name A to Z</option>
        </select>
      </div>
      <canvas id="sectorChart" height="360"></canvas>
      <div class="table-wrap" style="margin-top:14px"><table><thead><tr><th>Sector</th><th>Last</th><th>Change</th><th>Change %</th></tr></thead><tbody id="sectorRows"></tbody></table></div>
    </div>
    <h3>Sector Heatmap</h3>
    <div class="heatmap-legend">
      <span class="swatch"><span class="box" style="background:#bbf7d0"></span>Strong up (&ge;1.5%)</span>
      <span class="swatch"><span class="box" style="background:#dcfce7"></span>Up</span>
      <span class="swatch"><span class="box" style="background:#fef3c7"></span>Flat</span>
      <span class="swatch"><span class="box" style="background:#fee2e2"></span>Down</span>
      <span class="swatch"><span class="box" style="background:#fecaca"></span>Strong down (&le;-1.5%)</span>
    </div>
<div id="sectorHeatmap" class="heatmap-grid"></div>
  </section>

  <section id="signals" class="panel">
    <div class="card">
      <h2>Signal Score Breakdown</h2>
      <div class="controls">
        <select id="signalStatusFilter">
          <option value="All">All signals</option>
          <option value="Bullish">Bullish</option>
          <option value="Bearish">Bearish</option>
          <option value="Neutral">Neutral</option>
          <option value="Unavailable">Unavailable</option>
        </select>
      </div>
      <canvas id="signalChart" height="320"></canvas>
      <div class="table-wrap" style="margin-top:14px"><table><thead><tr><th>Signal</th><th>Score</th><th>Status</th><th>Reason</th></tr></thead><tbody id="signalRows"></tbody></table></div>
    </div>
    <div id="warningsCard"></div>
  </section>

  <section id="history" class="panel">
    <div class="card">
      <h2>Historical Bias Trend</h2>
      <p class="muted">This chart grows automatically after each successful GitHub Action run.</p>
      <canvas id="historyChart" height="320"></canvas>
      <div class="table-wrap" style="margin-top:14px"><table><thead><tr><th>Date</th><th>Bias</th><th>Score</th><th>Confidence</th><th>FII Net</th><th>DII Net</th><th>Nifty PCR</th><th>Top Sector</th></tr></thead><tbody id="historyRows"></tbody></table></div>
    </div>
    <div class="card">
  <h2>5-Day Rolling Put-Call Ratio</h2>
  <p class="muted">
    Tracks Nifty and Bank Nifty PCR trend using the last 5 generated reports.
  </p>

  <div id="pcrSummaryGrid" class="pcr-summary-grid"></div>

  <canvas id="pcrRollingChart" height="320"></canvas>

  <div class="table-wrap" style="margin-top:14px">
    <table>
      <thead>
        <tr>
          <th>Date</th>
          <th>Nifty PCR</th>
          <th>Nifty 5D Avg</th>
          <th>Bank Nifty PCR</th>
          <th>Bank Nifty 5D Avg</th>
        </tr>
      </thead>
      <tbody id="pcrRollingRows"></tbody>
    </table>
  </div>
</div>
  </section>

  <section id="news" class="panel">
  <div class="card">
    <h2>Important Market News</h2>
    <p class="muted">
      Latest important market headlines from RSS sources. Use this as context, not as trading advice.
    </p>

    <div class="controls">
      <input id="newsSearch" placeholder="Search news..." />
      <select id="newsSourceFilter">
        <option value="All">All sources</option>
      </select>
    </div>

    <div id="newsGrid" class="news-grid"></div>
  </div>
</section>

  <section id="report" class="panel">
    <div class="card">
      <h2>Full Markdown Report</h2>
      <div class="controls">
        <button class="action-btn secondary" id="copyReportBtn">Copy full report</button>
        <button class="action-btn" id="downloadReportBtn">Download .md</button>
      </div>
      <pre id="markdownReport"></pre>
    </div>
  </section>

  <p class="footer-note">Generated automatically for pre-market discussion. Not financial advice.</p>
</main>
<script id="app-data" type="application/json">__APP_DATA__</script>
<script>
const APP = JSON.parse(document.getElementById('app-data').textContent);
const fmt = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 });

function num(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return 'N/A';
  return fmt.format(Number(value));
}
function pct(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return 'N/A';
  return Number(value).toFixed(2) + '%';
}
function money(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return 'N/A';
  return '₹' + fmt.format(Number(value)) + ' Cr';
}
function badgeClass(status) {
  if (!status) return 'info';
  const s = String(status).toLowerCase();
  if (s.includes('bull') || s.includes('positive') || s.includes('high')) return 'good';
  if (s.includes('bear') || s.includes('negative') || s.includes('low')) return 'bad';
  if (s.includes('neutral') || s.includes('range')) return 'neutral';
  return 'info';
}
function badge(text) {
  return `<span class="badge ${badgeClass(text)}">${text || 'N/A'}</span>`;
}
function signedClass(value) {
  const n = Number(value || 0);
  if (n > 0) return 'good';
  if (n < 0) return 'bad';
  return 'neutral';
}
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[ch]));
}
function filteredSorted(rows, filters) {
  let out = [...rows];
  if (filters.region && filters.region !== 'All') out = out.filter(r => r.region === filters.region);
  if (filters.search) out = out.filter(r => String(r.name || '').toLowerCase().includes(filters.search.toLowerCase()));
  if (filters.sentiment === 'Positive') out = out.filter(r => Number(r.change_pct || 0) > 0);
  if (filters.sentiment === 'Negative') out = out.filter(r => Number(r.change_pct || 0) < 0);
  const sort = filters.sort || 'change_desc';
  out.sort((a, b) => {
    if (sort === 'name') return String(a.name || '').localeCompare(String(b.name || ''));
    const av = Number(a.change_pct ?? -999999);
    const bv = Number(b.change_pct ?? -999999);
    return sort === 'change_asc' ? av - bv : bv - av;
  });
  return out;
}

function clearCanvas(canvas) {
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = Math.max(320, Math.floor(rect.width * dpr));
  canvas.height = Math.floor((Number(canvas.getAttribute('height')) || 300) * dpr);
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  return { ctx, w: canvas.width / dpr, h: canvas.height / dpr };
}
function drawBarChart(canvasId, rows, labelKey, valueKey, title) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const { ctx, w, h } = clearCanvas(canvas);
  const data = rows.filter(r => r[valueKey] !== null && r[valueKey] !== undefined).slice(0, 14);
  ctx.font = '12px Arial';
  ctx.fillStyle = '#667085';
  if (!data.length) {
    ctx.fillText('No data available', 16, 32);
    return;
  }
  const padL = 126, padR = 24, padT = 28, padB = 26;
  const innerW = w - padL - padR;
  const barH = Math.max(14, (h - padT - padB) / data.length - 7);
  const maxAbs = Math.max(...data.map(r => Math.abs(Number(r[valueKey] || 0))), 1);
  const zeroX = padL + innerW / 2;
  ctx.strokeStyle = '#e5e7eb';
  ctx.beginPath(); ctx.moveTo(zeroX, padT - 6); ctx.lineTo(zeroX, h - padB + 4); ctx.stroke();
  ctx.fillStyle = '#172033';
  ctx.font = 'bold 13px Arial';
  ctx.fillText(title || '', 12, 18);
  data.forEach((r, i) => {
    const y = padT + i * (barH + 7);
    const value = Number(r[valueKey] || 0);
    const len = Math.abs(value) / maxAbs * (innerW / 2 - 8);
    const x = value >= 0 ? zeroX : zeroX - len;
    ctx.fillStyle = value >= 0 ? '#047857' : '#b91c1c';
    ctx.fillRect(x, y, len, barH);
    ctx.fillStyle = '#172033';
    ctx.font = '12px Arial';
    const label = String(r[labelKey] || '').replace('NIFTY ', '').slice(0, 22);
    ctx.fillText(label, 8, y + barH - 2);
    ctx.fillStyle = '#667085';
    ctx.fillText(value.toFixed(2), value >= 0 ? x + len + 5 : x - 42, y + barH - 2);
  });
}
function drawScoreChart(canvasId, rows) {
  drawBarChart(canvasId, rows.map(r => ({ name: r.name, score: r.score })), 'name', 'score', 'Signal score by component');
}
function drawLineChart(canvasId, history) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const { ctx, w, h } = clearCanvas(canvas);
  const data = (history || []).filter(r => r.score !== null && r.score !== undefined).slice(-45);
  if (data.length < 2) {
    ctx.fillStyle = '#667085';
    ctx.font = '13px Arial';
    ctx.fillText('History will appear after multiple daily workflow runs.', 16, 32);
    return;
  }
  const padL = 44, padR = 18, padT = 26, padB = 42;
  const values = data.map(r => Number(r.score));
  const min = Math.min(-6, ...values);
  const max = Math.max(6, ...values);
  const xStep = (w - padL - padR) / Math.max(data.length - 1, 1);
  const yFor = v => padT + (max - v) / (max - min) * (h - padT - padB);
  ctx.strokeStyle = '#e5e7eb';
  ctx.lineWidth = 1;
  for (let v = Math.ceil(min); v <= Math.floor(max); v += 2) {
    const y = yFor(v);
    ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(w - padR, y); ctx.stroke();
    ctx.fillStyle = '#667085'; ctx.font = '11px Arial'; ctx.fillText(String(v), 10, y + 4);
  }
  ctx.strokeStyle = '#2563eb';
  ctx.lineWidth = 2;
  ctx.beginPath();
  data.forEach((r, i) => {
    const x = padL + i * xStep;
    const y = yFor(Number(r.score));
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();
  data.forEach((r, i) => {
    const x = padL + i * xStep;
    const y = yFor(Number(r.score));
    ctx.fillStyle = Number(r.score) >= 0 ? '#047857' : '#b91c1c';
    ctx.beginPath(); ctx.arc(x, y, 4, 0, Math.PI * 2); ctx.fill();
  });
  ctx.fillStyle = '#667085';
  ctx.font = '11px Arial';
  data.forEach((r, i) => {
    if (i % Math.ceil(data.length / 6) === 0 || i === data.length - 1) {
      const x = padL + i * xStep;
      ctx.save(); ctx.translate(x, h - 18); ctx.rotate(-0.5); ctx.fillText(String(r.date).slice(5), 0, 0); ctx.restore();
    }
  });
}

function renderMetrics() {
  const nse = APP.data.nse_indices || {};
  const flow = APP.data.fii_dii || {};
  const nifty = (APP.data.option_chains || {}).NIFTY || {};
  const bank = (APP.data.option_chains || {}).BANKNIFTY || {};
  const vix = nse.india_vix || {};
  const combined = (Number(flow.fii_net || 0) + Number(flow.dii_net || 0));
  const metrics = [
    ['Market Bias', badge(APP.score.bias), APP.score.confidence + ' confidence'],
    ['Total Score', num(APP.score.score), 'Signal score'],
    ['FII Net', money(flow.fii_net), 'Previous session'],
    ['DII Net', money(flow.dii_net), 'Previous session'],
    ['Combined Flow', money(combined), 'FII + DII'],
    ['India VIX', pct(vix.change_pct), 'Risk indicator'],
    ['Nifty PCR', num(nifty.pcr), `Support ${num(nifty.support)} / Resistance ${num(nifty.resistance)}`],
    ['Bank Nifty PCR', num(bank.pcr), `Support ${num(bank.support)} / Resistance ${num(bank.resistance)}`],
    ['Crude Oil WTI', pct(((APP.data.commodities || []).find(r => r.name === 'Crude Oil WTI') || {}).change_pct), 'Commodity cue'],
    ['Bitcoin', pct(((APP.data.crypto || []).find(r => r.name === 'Bitcoin') || {}).change_pct), 'Risk appetite'],
    ['USD/INR', pct(((APP.data.currencies || []).find(r => r.name === 'USD/INR') || {}).change_pct), 'Currency pressure']
  ];
  document.getElementById('metricGrid').innerHTML = metrics.map(([label, value, note]) => `
    <div class="card"><div class="muted">${label}</div><div class="metric">${value}</div><div class="small muted">${escapeHtml(note)}</div></div>
  `).join('');
}
function renderOICards() {
  const chains = APP.data.option_chains || {};
  const items = ['NIFTY', 'BANKNIFTY'].map(key => chains[key] || { symbol: key });
  document.getElementById('oiCards').innerHTML = items.map(item => `
    <div class="card oi-card">
      <h2>${escapeHtml(item.symbol || '')} Open Interest</h2>
      <div class="grid">
        <div><div class="muted">Spot</div><strong>${num(item.underlying)}</strong></div>
        <div><div class="muted">PCR</div><strong>${num(item.pcr)}</strong></div>
        <div><div class="muted">Support</div><strong>${num(item.support)}</strong></div>
        <div><div class="muted">Resistance</div><strong>${num(item.resistance)}</strong></div>
      </div>
      <p class="small muted">Source: ${escapeHtml(item.source || 'N/A')} | Expiry: ${escapeHtml(item.expiry || 'N/A')}</p>
    </div>`).join('');
}
function renderGlobal() {
  const rows = filteredSorted(APP.data.global_markets || [], {
    region: document.getElementById('globalRegionFilter').value,
    sort: document.getElementById('globalSort').value,
  });
  document.getElementById('globalRows').innerHTML = rows.map(r => `
    <tr><td>${escapeHtml(r.region)}</td><td>${escapeHtml(r.name)}</td><td>${num(r.close)}</td><td>${num(r.change)}</td><td>${badge(pct(r.change_pct))}</td><td>${escapeHtml(r.date || '')}</td></tr>
  `).join('') || '<tr><td colspan="6">No global market data available</td></tr>';
  drawBarChart('globalChart', rows, 'name', 'change_pct', 'Global market change %');
}
function renderAssetGroup(rows, sortValue, tbodyId, chartId, labelTitle) {
  const filtered = filteredSorted(rows || [], { sort: sortValue || 'change_desc' });
  const tbody = document.getElementById(tbodyId);
  if (tbody) {
    tbody.innerHTML = filtered.map(r => `
      <tr><td>${escapeHtml(r.name)}</td><td>${escapeHtml(r.ticker || '')}</td><td>${num(r.close)}</td><td>${num(r.change)}</td><td>${badge(pct(r.change_pct))}</td><td>${escapeHtml(r.date || '')}</td></tr>
    `).join('') || '<tr><td colspan="6">No data available</td></tr>';
  }
  drawBarChart(chartId, filtered, 'name', 'change_pct', labelTitle);
}
function renderCommodities() {
  renderAssetGroup(APP.data.commodities || [], document.getElementById('commoditySort').value, 'commodityRows', 'commodityChart', 'Commodity change %');
}
function renderCrypto() {
  renderAssetGroup(APP.data.crypto || [], document.getElementById('cryptoSort').value, 'cryptoRows', 'cryptoChart', 'Crypto change %');
}
function renderCurrency() {
  renderAssetGroup(APP.data.currencies || [], document.getElementById('currencySort').value, 'currencyRows', 'currencyChart', 'Currency change %');
}

function renderSectors() {
  const rows = filteredSorted((APP.data.nse_indices || {}).sectors || [], {
    search: document.getElementById('sectorSearch').value,
    sentiment: document.getElementById('sectorSentimentFilter').value,
    sort: document.getElementById('sectorSort').value,
  });
  renderSectorHeatmap(rows);
  document.getElementById('sectorRows').innerHTML = rows.map(r => `
    <tr><td>${escapeHtml(r.name)}</td><td>${num(r.last)}</td><td>${num(r.change)}</td><td>${badge(pct(r.change_pct))}</td></tr>
  `).join('') || '<tr><td colspan="4">No sector data available</td></tr>';
  drawBarChart('sectorChart', rows, 'name', 'change_pct', 'Sector change %');
}
function renderSignals() {
  const status = document.getElementById('signalStatusFilter').value;
  const rows = (APP.score.components || []).filter(r => status === 'All' || r.status === status);
  document.getElementById('signalRows').innerHTML = rows.map(r => `
    <tr><td>${escapeHtml(r.name)}</td><td>${num(r.score)}</td><td>${badge(r.status)}</td><td>${escapeHtml(r.reason)}</td></tr>
  `).join('') || '<tr><td colspan="4">No signals available</td></tr>';
  drawScoreChart('signalChart', APP.score.components || []);
}
function renderHistory() {
  const rows = APP.history || [];
  document.getElementById('historyRows').innerHTML = rows.slice().reverse().map(r => `
    <tr><td>${escapeHtml(r.date)}</td><td>${badge(r.bias)}</td><td>${num(r.score)}</td><td>${escapeHtml(r.confidence || '')}</td><td>${money(r.fii_net)}</td><td>${money(r.dii_net)}</td><td>${num(r.nifty_pcr)}</td><td>${escapeHtml(r.top_sector || 'N/A')}</td></tr>
  `).join('') || '<tr><td colspan="8">History will appear after workflow runs.</td></tr>';
  drawLineChart('historyChart', rows);
}
function renderWarnings() {
  const warnings = APP.warnings || [];
  document.getElementById('warningsCard').innerHTML = warnings.length ? `
    <div class="card"><h2>Fetch Warnings</h2><ul>${warnings.map(w => `<li>${escapeHtml(w)}</li>`).join('')}</ul></div>
  ` : '<div class="card"><h2>Fetch Warnings</h2><p class="muted">No warnings in this run.</p></div>';
}
function copyText(text) {
  navigator.clipboard.writeText(text).then(() => alert('Copied'));
}
function downloadText(filename, text) {
  const blob = new Blob([text], { type: 'text/markdown' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click(); URL.revokeObjectURL(url);
}
function renderAll() {
  renderPcrRolling();
populateNewsSources();
renderNews();
renderMeetingMode();
  document.getElementById('generatedAt').textContent = `Generated at ${APP.generated_at}`;
  document.getElementById('marketView').textContent = APP.market_view || '';
  document.getElementById('riskNote').textContent = APP.risk_note || '';
  document.getElementById('markdownReport').textContent = APP.markdown || '';
  renderMetrics(); renderOICards(); renderGlobal(); renderCommodities(); renderCrypto(); renderCurrency(); renderSectors(); renderSignals(); renderHistory(); renderWarnings();
  drawBarChart('globalMiniChart', (APP.data.global_markets || []).slice(0, 8), 'name', 'change_pct', 'Change %');
  drawBarChart('sectorMiniChart', ((APP.data.nse_indices || {}).sectors || []).slice(0, 8), 'name', 'change_pct', 'Change %');
  drawBarChart('commodityMiniChart', (APP.data.commodities || []).slice(0, 8), 'name', 'change_pct', 'Change %');
  drawBarChart('cryptoMiniChart', (APP.data.crypto || []).slice(0, 8), 'name', 'change_pct', 'Change %');
const newsSearch = document.getElementById('newsSearch');

  }

function heatmapClass(value) {
  const n = Number(value || 0);

  if (n >= 1.5) return 'heat-strong-up';
  if (n > 0.25) return 'heat-up';
  if (n <= -1.5) return 'heat-strong-down';
  if (n < -0.25) return 'heat-down';

  return 'heat-flat';
}

function renderSectorHeatmap(rows) {
  const el = document.getElementById('sectorHeatmap');
  if (!el) return;

  const sorted = [...rows].sort((a, b) => Number(b.change_pct || 0) - Number(a.change_pct || 0));

  el.innerHTML = sorted.map(r => `
    <div class="heatmap-cell ${heatmapClass(r.change_pct)}" title="${escapeHtml(r.name || 'N/A')} — ${pct(r.change_pct)} (Last ${num(r.last)}, Chg ${num(r.change)})">
      <strong>${escapeHtml(r.name || 'N/A')}</strong>
      <div class="heat-value">${pct(r.change_pct)}</div>
      <div class="small">Last: ${num(r.last)}</div>
    </div>
  `).join('') || '<p class="muted">No sector heatmap data available.</p>';
}

function average(values) {
  const clean = values
    .map(v => Number(v))
    .filter(v => !Number.isNaN(v));

  if (!clean.length) return null;

  return clean.reduce((a, b) => a + b, 0) / clean.length;
}

function getPcrHistoryRows() {
  const history = Array.isArray(APP.history) ? [...APP.history] : [];

  return history
    .filter(row => row.date)
    .map(row => ({
      date: row.date,
      nifty_pcr: row.nifty_pcr ?? null,
      banknifty_pcr: row.banknifty_pcr ?? null,
    }));
}

function calculateRollingPcr(rows) {
  return rows.map((row, index) => {
    const windowRows = rows.slice(Math.max(0, index - 4), index + 1);

    return {
      ...row,
      nifty_pcr_5d: average(windowRows.map(r => r.nifty_pcr)),
      banknifty_pcr_5d: average(windowRows.map(r => r.banknifty_pcr)),
    };
  });
}

function pcrStatusText(current, rolling) {
  if (current === null || current === undefined || rolling === null || rolling === undefined) {
    return 'Not enough data';
  }

  const diff = Number(current) - Number(rolling);

  if (diff > 0.08) return 'PCR rising';
  if (diff < -0.08) return 'PCR falling';

  return 'PCR stable';
}

function renderPcrRolling() {
  const rows = calculateRollingPcr(getPcrHistoryRows());

  const summaryEl = document.getElementById('pcrSummaryGrid');
  const tableEl = document.getElementById('pcrRollingRows');

  if (!summaryEl || !tableEl) return;

  const latest = rows[rows.length - 1] || {};

  summaryEl.innerHTML = `
    <div class="pcr-mini-card">
      <div class="muted">Nifty PCR</div>
      <div class="metric">${num(latest.nifty_pcr)}</div>
      <div class="small muted">5D Avg: ${num(latest.nifty_pcr_5d)} | ${pcrStatusText(latest.nifty_pcr, latest.nifty_pcr_5d)}</div>
    </div>
    <div class="pcr-mini-card">
      <div class="muted">Bank Nifty PCR</div>
      <div class="metric">${num(latest.banknifty_pcr)}</div>
      <div class="small muted">5D Avg: ${num(latest.banknifty_pcr_5d)} | ${pcrStatusText(latest.banknifty_pcr, latest.banknifty_pcr_5d)}</div>
    </div>
  `;

  tableEl.innerHTML = rows.slice().reverse().map(row => `
    <tr>
      <td>${escapeHtml(row.date)}</td>
      <td>${num(row.nifty_pcr)}</td>
      <td>${num(row.nifty_pcr_5d)}</td>
      <td>${num(row.banknifty_pcr)}</td>
      <td>${num(row.banknifty_pcr_5d)}</td>
    </tr>
  `).join('') || '<tr><td colspan="5">PCR history will appear after workflow runs.</td></tr>';

  drawPcrRollingChart('pcrRollingChart', rows);
}

function drawPcrRollingChart(canvasId, rows) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;

  const { ctx, w, h } = clearCanvas(canvas);

  const data = rows
    .filter(r => r.nifty_pcr !== null || r.banknifty_pcr !== null)
    .slice(-30);

  if (data.length < 2) {
    ctx.fillStyle = '#667085';
    ctx.font = '13px Arial';
    ctx.fillText('PCR rolling chart will appear after multiple workflow runs.', 16, 32);
    return;
  }

  const padL = 50;
  const padR = 20;
  const padT = 28;
  const padB = 42;

  const allValues = data.flatMap(r => [
    r.nifty_pcr,
    r.banknifty_pcr,
    r.nifty_pcr_5d,
    r.banknifty_pcr_5d,
  ]).filter(v => v !== null && v !== undefined && !Number.isNaN(Number(v)));

  const min = Math.min(...allValues, 0.5);
  const max = Math.max(...allValues, 1.5);

  const xStep = (w - padL - padR) / Math.max(data.length - 1, 1);

  const yFor = value => {
    const v = Number(value);
    return padT + (max - v) / (max - min || 1) * (h - padT - padB);
  };

  ctx.strokeStyle = '#e5e7eb';
  ctx.lineWidth = 1;

  for (let i = 0; i <= 5; i++) {
    const val = min + ((max - min) / 5) * i;
    const y = yFor(val);

    ctx.beginPath();
    ctx.moveTo(padL, y);
    ctx.lineTo(w - padR, y);
    ctx.stroke();

    ctx.fillStyle = '#667085';
    ctx.font = '11px Arial';
    ctx.fillText(val.toFixed(2), 8, y + 4);
  }

  function drawLine(key, color, label, dash = []) {
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.setLineDash(dash);
    ctx.beginPath();

    let started = false;

    data.forEach((row, i) => {
      const value = row[key];

      if (value === null || value === undefined || Number.isNaN(Number(value))) {
        return;
      }

      const x = padL + i * xStep;
      const y = yFor(value);

      if (!started) {
        ctx.moveTo(x, y);
        started = true;
      } else {
        ctx.lineTo(x, y);
      }
    });

    ctx.stroke();
    ctx.setLineDash([]);

    ctx.fillStyle = color;
    ctx.font = '12px Arial';
    ctx.fillText(label, padL, 16 + drawLine.labelOffset);
    drawLine.labelOffset += 16;
  }

  drawLine.labelOffset = 0;

  drawLine('nifty_pcr', '#2563eb', 'Nifty PCR');
  drawLine('nifty_pcr_5d', '#1d4ed8', 'Nifty 5D Avg', [5, 4]);
  drawLine('banknifty_pcr', '#16a34a', 'Bank Nifty PCR');
  drawLine('banknifty_pcr_5d', '#15803d', 'Bank Nifty 5D Avg', [5, 4]);
}

function populateNewsSources() {
  const select = document.getElementById('newsSourceFilter');
  if (!select) return;

  const sources = [...new Set((APP.data.market_news || []).map(row => row.source).filter(Boolean))];

  select.innerHTML = '<option value="All">All sources</option>' +
    sources.map(source => `<option value="${escapeHtml(source)}">${escapeHtml(source)}</option>`).join('');
}

function renderNews() {
  const grid = document.getElementById('newsGrid');
  if (!grid) return;

  const searchValue = (document.getElementById('newsSearch')?.value || '').toLowerCase();
  const sourceValue = document.getElementById('newsSourceFilter')?.value || 'All';

  let rows = APP.data.market_news || [];

  if (sourceValue !== 'All') {
    rows = rows.filter(row => row.source === sourceValue);
  }

  if (searchValue) {
    rows = rows.filter(row =>
      String(row.title || '').toLowerCase().includes(searchValue) ||
      String(row.summary || '').toLowerCase().includes(searchValue)
    );
  }

  grid.innerHTML = rows.slice(0, 10).map(row => `
    <div class="news-card">
      <a href="${escapeHtml(row.link || '#')}" target="_blank" rel="noopener noreferrer">
        ${escapeHtml(row.title || 'Untitled')}
      </a>
      <p class="small">${escapeHtml(row.summary || '')}</p>
      <div class="news-meta">
        ${escapeHtml(row.source || 'News')} · ${escapeHtml(row.published || '')}
      </div>
    </div>
  `).join('') || '<p class="muted">No news found.</p>';
}

function renderMeetingMode() {
  const planEl = document.getElementById('todayPlan');
  const topSignalsEl = document.getElementById('topSignals');
  const riskEl = document.getElementById('mainRisk');

  if (!planEl || !topSignalsEl || !riskEl) return;

  const components = APP.score.components || [];
  const topPositive = components.filter(x => Number(x.score || 0) > 0).slice(0, 3);
  const topNegative = components.filter(x => Number(x.score || 0) < 0).slice(0, 3);

  planEl.textContent = `Today’s Plan: ${APP.score.bias}. ${APP.market_view || ''}`;

  topSignalsEl.textContent = `Supportive signals: ${
    topPositive.map(x => x.name).join(', ') || 'None'
  }. Risk signals: ${
    topNegative.map(x => x.name).join(', ') || 'None'
  }.`;

  riskEl.textContent = APP.risk_note || '';
}

document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(btn.dataset.tab).classList.add('active');
    setTimeout(renderAll, 20);
  });
});
['globalRegionFilter','globalSort'].forEach(id => document.getElementById(id).addEventListener('change', renderGlobal));
['commoditySort'].forEach(id => document.getElementById(id).addEventListener('change', renderCommodities));
['cryptoSort'].forEach(id => document.getElementById(id).addEventListener('change', renderCrypto));
['currencySort'].forEach(id => document.getElementById(id).addEventListener('change', renderCurrency));
['sectorSearch','sectorSentimentFilter','sectorSort'].forEach(id => document.getElementById(id).addEventListener(id === 'sectorSearch' ? 'input' : 'change', renderSectors));
document.getElementById('signalStatusFilter').addEventListener('change', renderSignals);
document.getElementById('copySummaryBtn').addEventListener('click', () => copyText(`${APP.score.bias} | Score ${APP.score.score}\n${APP.market_view}\n${APP.risk_note}`));
document.getElementById('copyReportBtn').addEventListener('click', () => copyText(APP.markdown || ''));
document.getElementById('downloadReportBtn').addEventListener('click', () => downloadText('morning_market_brief.md', APP.markdown || ''));
document.getElementById('printBtn').addEventListener('click', () => window.print());

let availableVoices = [];
let currentUtterance = null;
function stripMarkdown(text) {
  return String(text || '')
    .replace(/```[\\s\\S]*?```/g, ' ')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/[#*_|>-]+/g, ' ')
    .replace(/\\[(.*?)\\]\\(.*?\\)/g, '$1')
    .replace(/\\s+/g, ' ')
    .trim();
}
function getSpeechText() {
  const mode = document.getElementById('ttsMode').value;
  if (mode === 'full') return stripMarkdown(APP.markdown || '');
  return stripMarkdown(`Morning market brief. Market bias is ${APP.score.bias}. Total score is ${APP.score.score}. Confidence is ${APP.score.confidence}. ${APP.market_view || ''} ${APP.risk_note || ''}`);
}
function loadVoices() {
  if (!('speechSynthesis' in window)) return;
  availableVoices = window.speechSynthesis.getVoices() || [];
  const voiceSelect = document.getElementById('ttsVoice');
  const current = voiceSelect.value;
  const preferred = availableVoices
    .map((voice, idx) => ({ voice, idx }))
    .filter(item => /en-IN|en-GB|en-US/i.test(item.voice.lang || '') || /English/i.test(item.voice.name || ''));
  const choices = preferred.length ? preferred : availableVoices.map((voice, idx) => ({ voice, idx }));
  voiceSelect.innerHTML = '<option value="">Default voice</option>' + choices.map(item => `<option value="${item.idx}">${escapeHtml(item.voice.name)} (${escapeHtml(item.voice.lang)})</option>`).join('');
  voiceSelect.value = current || '';
}
function setTtsStatus(message) {
  const el = document.getElementById('ttsStatus');
  if (el) el.textContent = message || '';
}
function speakReport() {
  if (!('speechSynthesis' in window)) {
    setTtsStatus('Text to speech is not supported in this browser. Try Chrome, Edge, or Safari.');
    return;
  }
  window.speechSynthesis.cancel();
  const text = getSpeechText();
  if (!text) {
    setTtsStatus('No text available to read.');
    return;
  }
  currentUtterance = new SpeechSynthesisUtterance(text);
  currentUtterance.rate = Number(document.getElementById('ttsRate').value || 1);
  currentUtterance.pitch = 1;
  const selectedVoiceIndex = document.getElementById('ttsVoice').value;
  if (selectedVoiceIndex !== '' && availableVoices[Number(selectedVoiceIndex)]) {
    currentUtterance.voice = availableVoices[Number(selectedVoiceIndex)];
  }
  currentUtterance.onstart = () => setTtsStatus('Reading report...');
  currentUtterance.onend = () => setTtsStatus('Finished reading.');
  currentUtterance.onerror = () => setTtsStatus('Speech stopped or blocked by browser. Click Listen again.');
  window.speechSynthesis.speak(currentUtterance);
}
function toggleSpeechPause() {
  if (!('speechSynthesis' in window)) return;
  if (window.speechSynthesis.paused) {
    window.speechSynthesis.resume();
    setTtsStatus('Reading report...');
  } else if (window.speechSynthesis.speaking) {
    window.speechSynthesis.pause();
    setTtsStatus('Paused.');
  }
}
function stopSpeech() {
  if (!('speechSynthesis' in window)) return;
  window.speechSynthesis.cancel();
  setTtsStatus('Stopped.');
}
if ('speechSynthesis' in window) {
  loadVoices();
  window.speechSynthesis.onvoiceschanged = loadVoices;
} else {
  setTtsStatus('Text to speech is not supported in this browser.');
}
document.getElementById('speakBtn').addEventListener('click', speakReport);
document.getElementById('pauseSpeakBtn').addEventListener('click', toggleSpeechPause);
document.getElementById('stopSpeakBtn').addEventListener('click', stopSpeech);
window.addEventListener('beforeunload', stopSpeech);
window.addEventListener('resize', () => setTimeout(renderAll, 100));
renderAll();
</script>
</body>
</html>""".replace("__APP_DATA__", payload_json)


def save_outputs(context: dict[str, Any], report_path: Path, dashboard_path: Path, docs_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    docs_path.parent.mkdir(parents=True, exist_ok=True)
    markdown = render_markdown(context)
    html = render_html(context)
    report_path.write_text(markdown, encoding="utf-8")
    dashboard_path.write_text(html, encoding="utf-8")
    docs_path.write_text(html, encoding="utf-8")


def _dashboard_payload(context: dict[str, Any], markdown: str) -> dict[str, Any]:
    return {
        "generated_at": context.get("generated_at"),
        "date": context.get("date"),
        "score": context.get("score", {}),
        "data": context.get("data", {}),
        "history": context.get("history", []),
        "warnings": context.get("warnings", []),
        "market_view": context.get("market_view"),
        "risk_note": context.get("risk_note"),
        "markdown": markdown,
    }


def _market_group_markdown(title: str, rows: list[dict[str, Any]], label: str) -> list[str]:
    lines: list[str] = []
    lines.append(f"## {title}")
    lines.append("")
    lines.append(f"| {label} | Ticker | Close | Change | Change % | Date |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    if not rows:
        lines.append(f"| No {title.lower()} data available |  |  |  |  |  |")
        return lines
    for row in rows:
        lines.append(
            f"| {row.get('name')} | {row.get('ticker', '')} | {number_text(row.get('close'))} | "
            f"{number_text(row.get('change'))} | {pct_text(row.get('change_pct'))} | {row.get('date', '')} |"
        )
    return lines


def _option_markdown_row(label: str, item: dict[str, Any]) -> str:
    return (
        f"| {label} | {number_text(item.get('underlying'))} | "
        f"{number_text(item.get('pcr'))} | {number_text(item.get('support'))} | "
        f"{number_text(item.get('resistance'))} | {item.get('source') or 'N/A'} |"
    )


def _market_view(data: dict[str, Any], score: dict[str, Any]) -> str:
    bias = score.get("bias")
    nifty = data.get("option_chains", {}).get("NIFTY", {})
    support = nifty.get("support")
    resistance = nifty.get("resistance")
    if bias in {"Bullish", "Mild Bullish"}:
        return f"Market setup is {bias}. Prefer buy-on-dip only if Nifty sustains above support near {number_text(support)}."
    if bias in {"Bearish", "Mild Bearish"}:
        return f"Market setup is {bias}. Avoid chasing upside unless Nifty reclaims resistance near {number_text(resistance)}."
    return f"Market setup is range-bound. Watch Nifty support near {number_text(support)} and resistance near {number_text(resistance)}."


def _risk_note(data: dict[str, Any], score: dict[str, Any]) -> str:
    bank = data.get("option_chains", {}).get("BANKNIFTY", {})
    return f"Bank Nifty levels to monitor: support {number_text(bank.get('support'))}, resistance {number_text(bank.get('resistance'))}."
