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
    .chart-box { position: relative; width: 100%; height: 380px; border: 1px solid var(--line); border-radius: 14px; background: linear-gradient(180deg, #ffffff, #fbfcfe); padding: 12px 14px 8px; box-shadow: inset 0 0 0 1px rgba(15,23,42,.02); }
    .chart-box.mini { height: 300px; }
    .chart-box.tall { height: 440px; }
    .chart-box canvas { width: 100% !important; height: 100% !important; }
    @media (max-width: 640px) { .chart-box { height: 320px; } .chart-box.mini { height: 270px; } .chart-box.tall { height: 380px; } }
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

/* ---------- First-impression polish ---------- */

/* Animated header gradient + live pulse */
header {
  background: linear-gradient(135deg, #0f172a, #1e3a8a, #0f172a);
  background-size: 200% 200%;
  animation: headerShift 14s ease infinite;
  position: relative;
  overflow: hidden;
}
header::after {
  content: "";
  position: absolute;
  top: -50%; left: -50%;
  width: 200%; height: 200%;
  background: radial-gradient(circle at 30% 20%, rgba(59,130,246,.25), transparent 45%);
  pointer-events: none;
}
@keyframes headerShift {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}
h1 { position: relative; }
.live-dot {
  width: 9px; height: 9px; border-radius: 50%;
  background: #4ade80; display: inline-block;
  box-shadow: 0 0 0 0 rgba(74,222,128,.7);
  animation: livePulse 1.8s infinite;
}
@keyframes livePulse {
  0% { box-shadow: 0 0 0 0 rgba(74,222,128,.7); }
  70% { box-shadow: 0 0 0 10px rgba(74,222,128,0); }
  100% { box-shadow: 0 0 0 0 rgba(74,222,128,0); }
}

/* Hero sentiment banner */
.hero {
  background: var(--card);
  border-radius: 20px;
  padding: 26px;
  margin: 0 0 20px;
  box-shadow: 0 10px 40px rgba(15,23,42,.10);
  border: 1px solid rgba(15,23,42,.05);
  display: grid;
  grid-template-columns: minmax(220px, 280px) 1fr;
  gap: 28px;
  align-items: center;
}
@media (max-width: 720px) { .hero { grid-template-columns: 1fr; text-align: center; } }
.gauge-wrap { display: flex; flex-direction: column; align-items: center; }
.gauge-svg { width: 100%; max-width: 260px; }
.gauge-arc-fg { transition: stroke-dashoffset 1.4s cubic-bezier(.22,1,.36,1); }
.gauge-needle { transform-box: fill-box; transform-origin: bottom center; transition: transform 1.4s cubic-bezier(.34,1.56,.64,1); }
.gauge-score { font-size: 46px; font-weight: 800; letter-spacing: -.03em; line-height: 1; }
.gauge-score-label { font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: .08em; font-weight: 700; }
.hero-bias { display: inline-flex; align-items: center; gap: 10px; font-size: 30px; font-weight: 800; letter-spacing: -.02em; }
.hero-bias .dot { width: 16px; height: 16px; border-radius: 50%; }
.hero-sub { margin-top: 10px; font-size: 16px; line-height: 1.55; color: var(--text); }
.hero-chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.hero-chip { background: #f1f5f9; border: 1px solid var(--line); border-radius: 999px; padding: 7px 12px; font-size: 13px; font-weight: 600; display: inline-flex; gap: 6px; align-items: center; }
.hero-chip b { font-weight: 800; }
.tone-good { color: var(--good); } .tone-bad { color: var(--bad); } .tone-neutral { color: var(--neutral); }

/* Entrance reveal (staggered) */
.reveal { opacity: 0; transform: translateY(16px); }
.reveal.in { opacity: 1; transform: none; transition: opacity .55s ease, transform .55s cubic-bezier(.22,1,.36,1); }

/* Card hover lift + tab transitions */
.card { transition: transform .18s ease, box-shadow .18s ease; }
.card:hover { transform: translateY(-3px); box-shadow: 0 12px 30px rgba(15,23,42,.13); }
.card.meeting-mode:hover, .hero:hover { transform: none; }
.tab-btn { transition: background .18s ease, color .18s ease, transform .12s ease; }
.tab-btn:hover { transform: translateY(-1px); }
.panel.active { animation: panelFade .4s ease; }
@keyframes panelFade { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
.pop { animation: popIn .55s cubic-bezier(.22,1,.36,1) both; }
@keyframes popIn { from { opacity: 0; transform: translateY(18px) scale(.98); } to { opacity: 1; transform: none; } }

@media (prefers-reduced-motion: reduce) {
  *, header, .live-dot { animation: none !important; transition: none !important; }
  .reveal { opacity: 1; transform: none; }
}

  </style>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
</head>
<body>
<header>
  <div class="top-line">
    <div>
      <h1>Interactive Morning Market Brief</h1>
      <div id="generatedAt" class="muted" style="color:#cbd5e1"></div>
    </div>
    <div class="pill"><span class="live-dot"></span><span>Live</span><strong>Pre-market</strong></div>
  </div>
</header>
<main>
  <section id="hero" class="hero reveal"></section>

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
      <div class="card"><h2>Global Snapshot</h2><div class="chart-box mini"><canvas id="globalMiniChart"></canvas></div></div>
      <div class="card"><h2>Sector Snapshot</h2><div class="chart-box mini"><canvas id="sectorMiniChart"></canvas></div></div>
    </div>
    <div class="grid-2">
      <div class="card"><h2>Commodity Snapshot</h2><div class="chart-box mini"><canvas id="commodityMiniChart"></canvas></div></div>
      <div class="card"><h2>Crypto Snapshot</h2><div class="chart-box mini"><canvas id="cryptoMiniChart"></canvas></div></div>
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
      <div class="chart-box"><canvas id="globalChart"></canvas></div>
      <div class="table-wrap" style="margin-top:14px"><table><thead><tr><th>Region</th><th>Index</th><th>Close</th><th>Change</th><th>Change %</th><th>Date</th></tr></thead><tbody id="globalRows"></tbody></table></div>
    </div>
  </section>

  <section id="commodities" class="panel">
    <div class="card">
      <h2>Global Commodities</h2>
      <p class="muted">Gold, Silver, Crude Oil WTI, Copper, Brent Oil, and Natural Gas.</p>
      <div class="controls">
        <select id="commoditySort">
          <option value="change_desc">Change % high to low</option>
          <option value="change_asc">Change % low to high</option>
          <option value="name">Name A to Z</option>
        </select>
      </div>
      <div class="chart-box"><canvas id="commodityChart"></canvas></div>
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
      <div class="chart-box"><canvas id="cryptoChart"></canvas></div>
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
      <div class="chart-box"><canvas id="currencyChart"></canvas></div>
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
      <div class="chart-box tall"><canvas id="sectorChart"></canvas></div>
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
      <div class="chart-box tall"><canvas id="signalChart"></canvas></div>
      <div class="table-wrap" style="margin-top:14px"><table><thead><tr><th>Signal</th><th>Score</th><th>Status</th><th>Reason</th></tr></thead><tbody id="signalRows"></tbody></table></div>
    </div>
    <div id="warningsCard"></div>
  </section>

  <section id="history" class="panel">
    <div class="card">
      <h2>Historical Bias Trend</h2>
      <p class="muted">This chart grows automatically after each successful GitHub Action run.</p>
      <div class="chart-box"><canvas id="historyChart"></canvas></div>
      <div class="table-wrap" style="margin-top:14px"><table><thead><tr><th>Date</th><th>Bias</th><th>Score</th><th>Confidence</th><th>FII Net</th><th>DII Net</th><th>Nifty PCR</th><th>Top Sector</th></tr></thead><tbody id="historyRows"></tbody></table></div>
    </div>
    <div class="card">
  <h2>5-Day Rolling Put-Call Ratio</h2>
  <p class="muted">
    Tracks Nifty and Bank Nifty PCR trend using the last 5 generated reports.
  </p>

  <div id="pcrSummaryGrid" class="pcr-summary-grid"></div>

  <div class="chart-box"><canvas id="pcrRollingChart"></canvas></div>

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

/* ---------- Chart.js powered visualizations ---------- */
const CHARTS = {};
const C = {
  up: '#16a34a', upFill: 'rgba(22,163,74,.82)',
  down: '#dc2626', downFill: 'rgba(220,38,38,.82)',
  flat: '#94a3b8', flatFill: 'rgba(148,163,184,.7)',
  brand: '#2563eb', brand2: '#1d4ed8',
  green: '#16a34a', green2: '#15803d',
  grid: 'rgba(148,163,184,.16)', axis: '#64748b'
};
if (window.Chart) {
  Chart.defaults.font.family = 'Inter, Arial, sans-serif';
  Chart.defaults.font.size = 12;
  Chart.defaults.color = C.axis;
  Chart.defaults.animation = { duration: 700, easing: 'easeOutQuart' };
  Chart.defaults.animations.colors = false;
  const tip = Chart.defaults.plugins.tooltip;
  tip.backgroundColor = 'rgba(15,23,42,.95)';
  tip.padding = 11;
  tip.cornerRadius = 9;
  tip.titleColor = '#fff';
  tip.titleFont = { weight: '700', size: 13 };
  tip.bodyColor = '#e2e8f0';
  tip.boxPadding = 5;
  tip.usePointStyle = true;
}
function barFill(v) {
  const n = Number(v) || 0;
  if (n > 0.02) return C.upFill;
  if (n < -0.02) return C.downFill;
  return C.flatFill;
}
function barEdge(v) {
  const n = Number(v) || 0;
  if (n > 0.02) return C.up;
  if (n < -0.02) return C.down;
  return C.flat;
}
function mountChart(canvasId, config) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !window.Chart) return;
  if (CHARTS[canvasId]) CHARTS[canvasId].destroy();
  CHARTS[canvasId] = new Chart(canvas.getContext('2d'), config);
}
function emptyMessagePlugin(message) {
  return {
    id: 'emptyMessage',
    afterDraw(chart) {
      const has = (chart.data.datasets || []).some(d => (d.data || [])
        .some(v => v !== null && v !== undefined && !Number.isNaN(Number(v))));
      if (has) return;
      const { ctx, chartArea } = chart;
      if (!chartArea) return;
      ctx.save();
      ctx.fillStyle = '#94a3b8';
      ctx.font = '13px Inter, Arial, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(message || 'No data available',
        (chartArea.left + chartArea.right) / 2, (chartArea.top + chartArea.bottom) / 2);
      ctx.restore();
    }
  };
}

function drawBarChart(canvasId, rows, labelKey, valueKey, title) {
  const data = (rows || []).filter(r => r[valueKey] !== null && r[valueKey] !== undefined).slice(0, 16);
  const labels = data.map(r => String(r[labelKey] || '').replace('NIFTY ', ''));
  const values = data.map(r => Number(r[valueKey] || 0));
  const isPct = valueKey === 'change_pct';
  mountChart(canvasId, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: title || 'Value',
        data: values,
        backgroundColor: values.map(barFill),
        borderColor: values.map(barEdge),
        borderWidth: 1.2,
        borderRadius: 5,
        borderSkipped: false,
        maxBarThickness: 30,
        hoverBackgroundColor: values.map(barEdge)
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      layout: { padding: { right: 18, top: 4 } },
      scales: {
        x: {
          grid: { color: C.grid, drawBorder: false },
          border: { display: false },
          ticks: { callback: v => isPct ? v + '%' : v }
        },
        y: { grid: { display: false }, border: { display: false }, ticks: { autoSkip: false, font: { size: 11 } } }
      },
      plugins: {
        legend: { display: false },
        title: { display: !!title, text: title, align: 'start', font: { size: 13, weight: '700' }, color: '#172033', padding: { bottom: 8 } },
        tooltip: {
          callbacks: {
            label(ctx) {
              const r = data[ctx.dataIndex] || {};
              const out = [(isPct ? ctx.parsed.x.toFixed(2) + '%' : ctx.parsed.x.toFixed(2))];
              if (r.close !== undefined && r.close !== null) out.push('Close: ' + num(r.close));
              if (r.change !== undefined && r.change !== null) out.push('Change: ' + num(r.change));
              if (r.status) out.push('Status: ' + r.status);
              return out;
            }
          }
        }
      }
    },
    plugins: [emptyMessagePlugin('No data available')]
  });
}
function drawScoreChart(canvasId, rows) {
  drawBarChart(canvasId, (rows || []).map(r => ({ name: r.name, score: r.score, status: r.status })), 'name', 'score', 'Signal score by component');
}
function drawLineChart(canvasId, history) {
  const data = (history || []).filter(r => r.score !== null && r.score !== undefined).slice(-60);
  const labels = data.map(r => String(r.date || '').slice(5));
  const values = data.map(r => Number(r.score));
  mountChart(canvasId, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Signal score',
        data: values,
        borderColor: C.brand,
        backgroundColor: ctx => {
          const { chartArea, ctx: c } = ctx.chart;
          if (!chartArea) return 'rgba(37,99,235,.12)';
          const g = c.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
          g.addColorStop(0, 'rgba(37,99,235,.28)');
          g.addColorStop(1, 'rgba(37,99,235,.01)');
          return g;
        },
        fill: true,
        tension: 0.34,
        pointRadius: data.length > 30 ? 0 : 3,
        pointHoverRadius: 6,
        pointBackgroundColor: values.map(v => v >= 0 ? C.up : C.down),
        pointBorderColor: '#fff',
        borderWidth: 2.5
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      scales: {
        x: { grid: { display: false }, border: { display: false }, ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } },
        y: { grid: { color: C.grid, drawBorder: false }, border: { display: false }, suggestedMin: -6, suggestedMax: 6 }
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: items => 'Date ' + (data[items[0].dataIndex]?.date || ''),
            label: ctx => 'Score: ' + ctx.parsed.y.toFixed(2)
          }
        }
      }
    },
    plugins: [emptyMessagePlugin('History will appear after multiple daily workflow runs.')]
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
  const data = (rows || []).filter(r => r.nifty_pcr !== null || r.banknifty_pcr !== null).slice(-30);
  const labels = data.map(r => String(r.date || '').slice(5));
  const series = [
    { key: 'nifty_pcr', color: '#2563eb', label: 'Nifty PCR', dash: [] },
    { key: 'nifty_pcr_5d', color: '#60a5fa', label: 'Nifty 5D Avg', dash: [6, 4] },
    { key: 'banknifty_pcr', color: '#16a34a', label: 'Bank Nifty PCR', dash: [] },
    { key: 'banknifty_pcr_5d', color: '#4ade80', label: 'Bank Nifty 5D Avg', dash: [6, 4] },
  ];
  const col = key => data.map(r => {
    const v = r[key];
    return (v === null || v === undefined || Number.isNaN(Number(v))) ? null : Number(v);
  });
  mountChart(canvasId, {
    type: 'line',
    data: {
      labels,
      datasets: series.map(s => ({
        label: s.label,
        data: col(s.key),
        borderColor: s.color,
        backgroundColor: s.color,
        borderDash: s.dash,
        borderWidth: 2,
        tension: 0.3,
        pointRadius: data.length > 20 ? 0 : 2.5,
        pointHoverRadius: 5,
        spanGaps: true,
        fill: false
      }))
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      scales: {
        x: { grid: { display: false }, border: { display: false }, ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } },
        y: { grid: { color: C.grid, drawBorder: false }, border: { display: false }, suggestedMin: 0.5, suggestedMax: 1.5 }
      },
      plugins: {
        legend: { position: 'top', labels: { usePointStyle: true, boxWidth: 8, padding: 14 } },
        tooltip: {
          callbacks: {
            title: items => 'Date ' + (data[items[0].dataIndex]?.date || ''),
            label: ctx => ctx.dataset.label + ': ' + (ctx.parsed.y === null ? 'N/A' : ctx.parsed.y.toFixed(2))
          }
        }
      }
    },
    plugins: [emptyMessagePlugin('PCR rolling chart will appear after multiple workflow runs.')]
  });
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

function biasTone(bias) {
  const b = String(bias || '').toLowerCase();
  if (b.includes('bull')) return { tone: 'good', color: '#047857' };
  if (b.includes('bear')) return { tone: 'bad', color: '#b91c1c' };
  return { tone: 'neutral', color: '#b45309' };
}

function animateCount(el, to, opts) {
  opts = opts || {};
  const decimals = opts.decimals || 0;
  const prefix = opts.prefix || '';
  const suffix = opts.suffix || '';
  const dur = opts.dur || 1100;
  const start = performance.now();
  const from = 0;
  function frame(now) {
    const t = Math.min(1, (now - start) / dur);
    const eased = 1 - Math.pow(1 - t, 3);
    const val = from + (to - from) * eased;
    el.textContent = prefix + val.toFixed(decimals) + suffix;
    if (t < 1) requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

function renderHero() {
  const el = document.getElementById('hero');
  if (!el) return;

  const score = Number(APP.score.score || 0);
  const bias = APP.score.bias || 'Neutral';
  const conf = APP.score.confidence || '';
  const { tone, color } = biasTone(bias);

  // Map score (clamped -10..+10) to a 180deg semicircle (left=bearish, right=bullish)
  const clamped = Math.max(-10, Math.min(10, score));
  const ratio = (clamped + 10) / 20;            // 0..1
  const angle = -90 + ratio * 180;              // -90..+90 degrees
  const R = 80, CX = 100, CY = 100;
  const circ = Math.PI * R;                     // half-circle length
  const dashOffset = circ * (1 - ratio);

  const nse = APP.data.nse_indices || {};
  const flow = APP.data.fii_dii || {};
  const nifty = (APP.data.option_chains || {}).NIFTY || {};
  const combined = Number(flow.fii_net || 0) + Number(flow.dii_net || 0);

  const chips = [
    ['FII+DII', money(combined), combined >= 0 ? 'tone-good' : 'tone-bad'],
    ['India VIX', pct((nse.india_vix || {}).change_pct), Number((nse.india_vix || {}).change_pct || 0) <= 0 ? 'tone-good' : 'tone-bad'],
    ['Nifty PCR', num(nifty.pcr), ''],
    ['Confidence', conf, ''],
  ];

  el.innerHTML = `
    <div class="gauge-wrap">
      <svg class="gauge-svg" viewBox="0 0 200 120" aria-hidden="true">
        <path d="M20 100 A80 80 0 0 1 180 100" fill="none" stroke="#e5e7eb" stroke-width="16" stroke-linecap="round"/>
        <path class="gauge-arc-fg" d="M20 100 A80 80 0 0 1 180 100" fill="none" stroke="${color}" stroke-width="16" stroke-linecap="round"
              stroke-dasharray="${circ.toFixed(1)}" stroke-dashoffset="${circ.toFixed(1)}"/>
        <g class="gauge-needle" style="transform: rotate(0deg);">
          <line x1="100" y1="100" x2="100" y2="38" stroke="${color}" stroke-width="3.5" stroke-linecap="round"/>
        </g>
        <circle cx="100" cy="100" r="6" fill="${color}"/>
      </svg>
      <div style="text-align:center;margin-top:2px">
        <div class="gauge-score tone-${tone}">0</div>
        <div class="gauge-score-label">Signal score</div>
      </div>
    </div>
    <div>
      <div class="gauge-score-label">Market bias</div>
      <div class="hero-bias"><span class="dot" style="background:${color}"></span><span class="tone-${tone}">${escapeHtml(bias)}</span></div>
      <div class="hero-sub">${escapeHtml(APP.market_view || '')}</div>
      <div class="hero-chips">
        ${chips.map(([k, v, t]) => `<span class="hero-chip">${escapeHtml(k)} <b class="${t}">${v}</b></span>`).join('')}
      </div>
    </div>`;

  // Animate gauge after a tick so transitions fire
  requestAnimationFrame(() => {
    const arc = el.querySelector('.gauge-arc-fg');
    const needle = el.querySelector('.gauge-needle');
    const scoreEl = el.querySelector('.gauge-score');
    if (arc) arc.style.strokeDashoffset = dashOffset.toFixed(1);
    if (needle) needle.style.transform = `rotate(${angle.toFixed(1)}deg)`;
    if (scoreEl) animateCount(scoreEl, score, { decimals: 0 });
  });
}

function playEntrance() {
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const hero = document.getElementById('hero');
  if (hero) requestAnimationFrame(() => hero.classList.add('in'));
  const cards = document.querySelectorAll('#overview .card, .card.meeting-mode');
  cards.forEach((c, i) => {
    c.classList.add('pop');
    c.style.animationDelay = (i * 70) + 'ms';
  });
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
renderHero();
playEntrance();
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
