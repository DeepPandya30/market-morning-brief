from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

from .config import EVENT_MARKDOWN_LIMIT
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
    lines.extend(_natural_gas_markdown(data.get("natural_gas", {})))
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
    lines.extend(_index_technicals_markdown(data.get("index_technicals", {})))
    lines.append("")
    lines.extend(_nifty50_markdown(data.get("nifty50", {})))
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
    lines.extend(_event_calendar_markdown(data.get("event_calendar", {})))
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
  <title>Market Morning Brief — Pre-Market Cockpit</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {
      /* Dark-first trader cockpit palette */
      --bg: #0B0F19;
      --bg-grad: radial-gradient(1200px 600px at 12% -8%, rgba(37,99,235,.14), transparent 60%), radial-gradient(1000px 500px at 100% 0%, rgba(34,197,94,.06), transparent 55%), #0B0F19;
      --card: #111827;
      --elev: rgba(255,255,255,.045);
      --elev-strong: rgba(255,255,255,.08);
      --input-bg: #0e1526;
      --text: #F9FAFB;
      --muted: #9CA3AF;
      --line: #1F2937;
      --dark: #0B0F19;
      --brand: #2563EB;
      --brand-soft: rgba(37,99,235,.16);
      --good: #22C55E;
      --good-soft: rgba(34,197,94,.15);
      --bad: #EF4444;
      --bad-soft: rgba(239,68,68,.15);
      --neutral: #F59E0B;
      --neutral-soft: rgba(245,158,11,.15);
      --shadow: 0 8px 30px rgba(0,0,0,.45);
      --radius: 16px;
    }
    :root[data-theme="light"] {
      --bg: #f5f7fb;
      --bg-grad: radial-gradient(1200px 600px at 12% -8%, rgba(37,99,235,.10), transparent 60%), #f5f7fb;
      --card: #ffffff;
      --elev: #f1f5f9;
      --elev-strong: #e2e8f0;
      --input-bg: #ffffff;
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
      --shadow: 0 8px 26px rgba(15,23,42,.10);
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
  border-left: 5px solid var(--line);
  border-radius: 14px;
  padding: 14px;
  transition: border-color .3s ease, background .3s ease;
}
.pcr-mini-card.pcr-bullish {
  background: var(--good-soft);
  border-color: var(--good);
  border-left-color: var(--good);
}
.pcr-mini-card.pcr-bearish {
  background: var(--bad-soft);
  border-color: var(--bad);
  border-left-color: var(--bad);
}
.pcr-mini-card.pcr-neutral {
  background: #fffbeb;
  border-color: #f59e0b;
  border-left-color: #f59e0b;
}
.pcr-mini-card .metric { transition: color .3s ease; }
.pcr-mini-card.pcr-bullish .metric { color: var(--good); }
.pcr-mini-card.pcr-bearish .metric { color: var(--bad); }
.pcr-mini-card.pcr-neutral .metric { color: #b45309; }
.pcr-status { font-weight: 700; }
.pcr-mini-card.pcr-bullish .pcr-status { color: var(--good); }
.pcr-mini-card.pcr-bearish .pcr-status { color: var(--bad); }
.pcr-mini-card.pcr-neutral .pcr-status { color: #b45309; }

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

/* Corporate event calendar */
.event-catbar { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }
.event-chip { border: 1px solid var(--line); border-radius: 999px; padding: 6px 12px;
  font-size: 12.5px; font-weight: 700; color: var(--muted); background: var(--elev); }
.event-chip b { color: var(--text); margin-left: 4px; }
.event-purpose { display: inline-block; padding: 3px 10px; border-radius: 999px;
  font-size: 12px; font-weight: 700; background: var(--elev-strong); color: var(--muted); white-space: nowrap; }
.event-purpose.cat-results { background: var(--brand-soft); color: var(--brand); }
.event-purpose.cat-dividend { background: var(--good-soft); color: var(--good); }
.event-purpose.cat-buyback { background: var(--good-soft); color: var(--good); }
.event-purpose.cat-bonus { background: var(--neutral-soft); color: var(--neutral); }
.event-purpose.cat-fund { background: var(--neutral-soft); color: var(--neutral); }
.event-purpose.cat-ma { background: var(--bad-soft); color: var(--bad); }
.n50-tag { display: inline-block; margin-left: 7px; padding: 2px 7px; border-radius: 999px;
  font-size: 10px; font-weight: 800; letter-spacing: .05em; background: var(--brand-soft); color: var(--brand); }
tr.is-n50 { background: var(--brand-soft); }
tr.is-n50 td:first-child { font-weight: 800; }
.event-desc { color: var(--muted); font-size: 12.5px; line-height: 1.45; max-width: 560px; }

/* Natural gas storage --------------------------------------------------- */
.gas-signal { display: flex; flex-wrap: wrap; align-items: baseline; gap: 10px;
  border: 1px solid var(--line); border-left: 5px solid var(--line);
  border-radius: 12px; padding: 12px 16px; margin-bottom: 14px; background: var(--elev); }
.gas-signal.tone-good { border-left-color: var(--good); background: var(--good-soft); }
.gas-signal.tone-bad { border-left-color: var(--bad); background: var(--bad-soft); }
.gas-signal.tone-neutral { border-left-color: var(--neutral); background: var(--neutral-soft); }
.gas-signal-label { font-weight: 800; font-size: 15px; }
.gas-signal.tone-good .gas-signal-label { color: var(--good); }
.gas-signal.tone-bad .gas-signal-label { color: var(--bad); }
.gas-signal.tone-neutral .gas-signal-label { color: var(--neutral); }
.gas-signal-note { color: var(--muted); font-size: 13px; line-height: 1.5; }
.gas-meta { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }
.gas-meta span { border: 1px solid var(--line); border-radius: 999px; padding: 6px 12px;
  font-size: 12.5px; font-weight: 700; color: var(--muted); background: var(--elev); }
.gas-meta span b { color: var(--text); margin-left: 5px; }
.gas-meta a { color: var(--brand); text-decoration: none; font-weight: 700; }
/* Salt / Nonsalt are splits of South Central, not peers of it. */
tr.gas-sub td:first-child { padding-left: 26px; color: var(--muted); font-weight: 600; }
tr.gas-total { background: var(--elev); }
tr.gas-total td { font-weight: 800; border-top: 2px solid var(--line); }

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

    /* ===================================================================
       COCKPIT REDESIGN — dark-first overrides + new components
       =================================================================== */
    body { background: var(--bg-grad); background-attachment: fixed; color: var(--text); -webkit-font-smoothing: antialiased; }
    main { max-width: 1600px; padding: 22px 26px 60px; }
    h1 { font-size: 24px; letter-spacing: -.01em; }
    .section-title { font-size: 20px; margin: 26px 2px 12px; display: flex; align-items: center; gap: 9px; }
    .card { background: var(--card); border: 1px solid var(--line); box-shadow: var(--shadow); border-radius: var(--radius); padding: 20px; }
    .card-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 14px; }
    .card-head h2 { margin: 0; font-size: 18px; }
    .metric { color: var(--text); }
    .muted { color: var(--muted); }

    /* Sticky glass nav */
    .navbar { position: sticky; top: 0; z-index: 40; display: flex; align-items: center; gap: 16px;
      padding: 12px 26px; background: rgba(11,15,25,.72); backdrop-filter: blur(14px) saturate(140%);
      border-bottom: 1px solid var(--line); }
    :root[data-theme="light"] .navbar { background: rgba(255,255,255,.78); }
    .nav-brand { display: flex; align-items: center; gap: 11px; font-weight: 800; font-size: 16px; letter-spacing: -.01em; white-space: nowrap; }
    .nav-logo { width: 30px; height: 30px; border-radius: 9px; display: grid; place-items: center;
      background: linear-gradient(135deg, var(--brand), #1e40af); color: #fff; font-size: 16px; box-shadow: 0 3px 12px rgba(37,99,235,.5); }
    .nav-brand small { display: block; font-size: 11px; font-weight: 600; color: var(--muted); }
    .nav-spacer { flex: 1; }
    .nav-search { position: relative; flex: 0 1 320px; }
    .nav-search input { width: 100%; padding: 9px 12px 9px 34px; border-radius: 10px; border: 1px solid var(--line);
      background: var(--input-bg); color: var(--text); font-size: 14px; }
    .nav-search input:focus { outline: none; border-color: var(--brand); box-shadow: 0 0 0 3px var(--brand-soft); }
    .nav-search .si { position: absolute; left: 11px; top: 50%; transform: translateY(-50%); color: var(--muted); font-size: 13px; }
    .nav-search kbd { position: absolute; right: 8px; top: 50%; transform: translateY(-50%); font-size: 11px; color: var(--muted);
      border: 1px solid var(--line); border-radius: 6px; padding: 1px 6px; background: var(--elev); }
    .nav-clock { text-align: right; line-height: 1.25; white-space: nowrap; }
    .nav-clock b { font-variant-numeric: tabular-nums; font-size: 15px; }
    .nav-clock small { display: block; color: var(--muted); font-size: 11px; }
    .icon-btn { border: 1px solid var(--line); background: var(--elev); color: var(--text); width: 38px; height: 38px;
      border-radius: 10px; cursor: pointer; font-size: 15px; display: grid; place-items: center; transition: all .18s ease; }
    .icon-btn:hover { background: var(--elev-strong); transform: translateY(-1px); }
    .nav-live { display: inline-flex; align-items: center; gap: 7px; font-size: 12px; font-weight: 700; color: var(--good);
      border: 1px solid var(--good-soft); background: var(--good-soft); padding: 6px 11px; border-radius: 999px; }

    /* Section nav (former tabs) */
    .tabs { background: rgba(11,15,25,.85); border: 1px solid var(--line); border-radius: 14px; padding: 8px; top: 66px;
      backdrop-filter: blur(10px); gap: 6px; }
    :root[data-theme="light"] .tabs { background: rgba(255,255,255,.9); }
    .tab-btn { background: transparent; border: 1px solid transparent; color: var(--muted); font-weight: 600; padding: 8px 14px; }
    .tab-btn:hover { color: var(--text); background: var(--elev); }
    .tab-btn.active { background: var(--brand); color: #fff; border-color: var(--brand); box-shadow: 0 4px 14px rgba(37,99,235,.4); }

    /* Inputs / buttons / tables (dark) */
    .controls input, .controls select { background: var(--input-bg); color: var(--text); border-color: var(--line); }
    .controls input:focus, .controls select:focus { outline: none; border-color: var(--brand); box-shadow: 0 0 0 3px var(--brand-soft); }
    .action-btn { background: var(--elev); border: 1px solid var(--line); color: var(--text); font-weight: 600; transition: all .18s ease; }
    .action-btn:hover { background: var(--elev-strong); transform: translateY(-1px); }
    .action-btn.secondary { background: var(--brand); border-color: var(--brand); color: #fff; }
    .action-btn.danger { background: var(--bad); border-color: var(--bad); color: #fff; }
    .table-wrap { border-color: var(--line); }
    table { background: transparent; color: var(--text); }
    th { background: var(--elev); color: var(--muted); border-color: var(--line); font-weight: 700; }
    td { border-color: var(--line); }
    tr:hover td { background: var(--elev); }
    .chart-box { background: var(--input-bg); border-color: var(--line); box-shadow: inset 0 0 0 1px rgba(255,255,255,.02); }
    .tts-panel { background: var(--elev); border-color: var(--line); }
    .news-card { background: var(--input-bg); border-color: var(--line); }
    .pcr-mini-card { background: var(--elev); }
    .hero-chip { background: var(--elev); border-color: var(--line); color: var(--text); }
    .oi-card { background: var(--input-bg); }
    pre { background: #060911; }

    /* Hero stat tiles */
    .hero-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 14px; margin: 0 0 20px; }
    .stat-tile { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 16px 18px; box-shadow: var(--shadow); position: relative; overflow: hidden; }
    .stat-tile::before { content: ""; position: absolute; inset: 0 auto 0 0; width: 4px; background: var(--tint, var(--brand)); }
    .stat-tile .st-label { font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; font-weight: 700; }
    .stat-tile .st-value { font-size: 30px; font-weight: 800; letter-spacing: -.02em; margin-top: 4px; line-height: 1.05; }
    .stat-tile .st-sub { font-size: 12.5px; color: var(--muted); margin-top: 4px; }
    .st-good { --tint: var(--good); } .st-bad { --tint: var(--bad); } .st-neutral { --tint: var(--neutral); } .st-brand { --tint: var(--brand); }
    .st-good .st-value { color: var(--good); } .st-bad .st-value { color: var(--bad); } .st-neutral .st-value { color: var(--neutral); }

    /* AI summary */
    .ai-card { background: linear-gradient(135deg, rgba(37,99,235,.10), var(--card) 55%); border-color: rgba(37,99,235,.3); }
    .summary-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
    .summary-list li { display: flex; gap: 11px; align-items: flex-start; font-size: 15.5px; line-height: 1.45; }
    .summary-list li .dot { flex: 0 0 auto; width: 8px; height: 8px; border-radius: 50%; margin-top: 8px; background: var(--brand); }

    /* Checklist + progress */
    .progress { height: 8px; border-radius: 999px; background: var(--elev); overflow: hidden; margin-bottom: 14px; }
    .progress span { display: block; height: 100%; width: 0; border-radius: 999px; background: linear-gradient(90deg, var(--brand), var(--good)); transition: width .5s cubic-bezier(.22,1,.36,1); }
    .chip-strong { font-weight: 800; font-size: 14px; color: var(--good); }
    .checklist { display: grid; gap: 8px; }
    .check-item { display: flex; align-items: center; gap: 11px; padding: 9px 11px; border: 1px solid var(--line); border-radius: 10px; cursor: pointer; transition: all .16s ease; user-select: none; }
    .check-item:hover { background: var(--elev); }
    .check-item.done { background: var(--good-soft); border-color: var(--good); }
    .check-box { width: 18px; height: 18px; border-radius: 6px; border: 2px solid var(--muted); display: grid; place-items: center; font-size: 12px; color: #fff; flex: 0 0 auto; }
    .check-item.done .check-box { background: var(--good); border-color: var(--good); }
    .check-item.done .check-label { text-decoration: line-through; color: var(--muted); }
    .check-label { font-size: 14.5px; }

    /* Alerts */
    .alerts { display: grid; gap: 9px; }
    .alert { display: flex; gap: 11px; align-items: flex-start; padding: 11px 13px; border-radius: 11px; border: 1px solid var(--line); background: var(--elev); font-size: 14px; }
    .alert .ic { font-size: 16px; line-height: 1.2; }
    .alert.warn { border-color: var(--neutral); background: var(--neutral-soft); }
    .alert.bad { border-color: var(--bad); background: var(--bad-soft); }
    .alert.good { border-color: var(--good); background: var(--good-soft); }
    .alert b { font-weight: 700; }

    /* Levels */
    .levels-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }
    .level-card { background: var(--card); border: 1px solid var(--line); border-radius: var(--radius); padding: 18px; box-shadow: var(--shadow); }
    .level-card h3 { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 12px; }
    .level-card .spot { font-size: 13px; color: var(--muted); font-weight: 600; }
    .level-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .level-box { border-radius: 12px; padding: 12px 14px; border: 1px solid var(--line); }
    .level-box.res { background: var(--bad-soft); border-color: rgba(239,68,68,.35); }
    .level-box.sup { background: var(--good-soft); border-color: rgba(34,197,94,.35); }
    .level-box .lk { font-size: 11px; text-transform: uppercase; letter-spacing: .06em; font-weight: 700; }
    .level-box.res .lk { color: var(--bad); } .level-box.sup .lk { color: var(--good); }
    .level-box .lv { font-size: 22px; font-weight: 800; letter-spacing: -.02em; margin-top: 3px; }
    .level-meta { margin-top: 12px; font-size: 12.5px; color: var(--muted); display: flex; justify-content: space-between; gap: 10px; }

    /* Indicators */
    .indicator-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 14px; }
    .ind-card { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 15px 16px; box-shadow: var(--shadow); transition: transform .16s ease, box-shadow .16s ease; }
    .ind-card:hover { transform: translateY(-3px); box-shadow: 0 12px 30px rgba(0,0,0,.5); }
    .ind-top { display: flex; align-items: center; justify-content: space-between; }
    .ind-name { font-size: 13px; color: var(--muted); font-weight: 700; }
    .ind-arrow { font-size: 15px; font-weight: 800; }
    .ind-value { font-size: 26px; font-weight: 800; letter-spacing: -.02em; margin: 6px 0 2px; }
    .ind-interp { font-size: 12.5px; font-weight: 700; }
    .ind-interp.good { color: var(--good); } .ind-interp.bad { color: var(--bad); } .ind-interp.neutral { color: var(--neutral); }

    /* FII/DII flow */
    .flow-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 16px; }
    .flow-card { background: var(--card); border: 1px solid var(--line); border-radius: var(--radius); padding: 18px; box-shadow: var(--shadow); }
    .flow-card .fh { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; font-weight: 700; }
    .flow-row { display: flex; justify-content: space-between; padding: 7px 0; border-top: 1px solid var(--line); font-size: 14px; }
    .flow-row:first-of-type { border-top: 0; }
    .flow-row b { font-variant-numeric: tabular-nums; }

    /* Timeline */
    .timeline { display: flex; flex-wrap: wrap; gap: 8px; align-items: stretch; }
    .tl-step { flex: 1 1 150px; min-width: 140px; background: var(--elev); border: 1px solid var(--line); border-radius: 12px; padding: 12px 14px; position: relative; }
    .tl-step .tl-t { font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: var(--muted); font-weight: 700; }
    .tl-step .tl-v { font-size: 17px; font-weight: 800; margin-top: 4px; }
    .tl-step .tl-s { font-size: 12px; color: var(--muted); margin-top: 2px; }
    .tl-step.pred { background: var(--brand-soft); border-color: var(--brand); }
    .tl-arrow { display: grid; place-items: center; color: var(--muted); font-size: 18px; }
    @media (max-width: 760px) { .tl-arrow { transform: rotate(90deg); } .timeline { flex-direction: column; } }

    .footer-note { border-top: 1px solid var(--line); margin-top: 30px; padding-top: 22px; }
    .site-footer { display: flex; flex-wrap: wrap; gap: 18px; justify-content: space-between; color: var(--muted); font-size: 13px; padding: 22px 2px 0; border-top: 1px solid var(--line); margin-top: 30px; }
    .site-footer a { color: var(--brand); text-decoration: none; }
    .site-footer .fcol { display: grid; gap: 4px; }

    /* Nifty 50 pivot table */
    .pivot-wrap { max-height: 640px; overflow: auto; }
    .pivot-table td, .pivot-table th { padding: 9px 11px; font-size: 13.5px; }
    .pivot-table th { position: sticky; top: 0; z-index: 2; }
    .pivot-table td.num, .pivot-table th.num { text-align: right; font-variant-numeric: tabular-nums; }
    .pivot-table .sym { font-weight: 700; }
    .pivot-table .sym small { display: block; font-weight: 500; color: var(--muted); font-size: 11.5px; }
    .pivot-table .lvl { color: var(--muted); }
    .pivot-table tbody tr.grp-head td { background: var(--elev); font-weight: 800; text-transform: uppercase;
      letter-spacing: .05em; font-size: 12px; color: var(--muted); }
    .cell-up { color: var(--good); font-weight: 700; background: color-mix(in srgb, var(--good) 9%, transparent); }
    .cell-down { color: var(--bad); font-weight: 700; background: color-mix(in srgb, var(--bad) 9%, transparent); }
    .cell-flat { color: var(--muted); font-weight: 600; }
    .zone-tag { font-size: 11.5px; font-weight: 700; border-radius: 999px; padding: 3px 8px; border: 1px solid var(--line);
      background: var(--elev); white-space: nowrap; }
    .zone-tag.up { color: var(--good); border-color: var(--good-soft); background: var(--good-soft); }
    .zone-tag.down { color: var(--bad); border-color: var(--bad-soft); background: var(--bad-soft); }
    .breadth-bar { display: flex; height: 10px; border-radius: 999px; overflow: hidden; margin: 4px 0 12px; background: var(--elev); }
    .breadth-bar i { display: block; height: 100%; }
    .breadth-bar .adv { background: var(--good); }
    .breadth-bar .dec { background: var(--bad); }
    .breadth-bar .unc { background: var(--neutral); }

    /* Index technicals */
    .tech-head { display: flex; flex-wrap: wrap; gap: 18px; align-items: baseline; margin-bottom: 6px; }
    .tech-head .tv { font-size: 34px; font-weight: 800; letter-spacing: -.02em; }
    .ind-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 14px; margin-top: 4px; }
    .ind-tile { background: var(--elev); border: 1px solid var(--line); border-radius: 13px; padding: 14px 16px; }
    .ind-tile .it-name { font-size: 12px; text-transform: uppercase; letter-spacing: .05em; color: var(--muted); font-weight: 700; }
    .ind-tile .it-val { font-size: 25px; font-weight: 800; margin: 5px 0 3px; letter-spacing: -.02em; }
    .ind-tile .it-note { font-size: 12px; color: var(--muted); line-height: 1.4; }
    .ma-ladder { display: grid; gap: 8px; margin-top: 4px; }
    .ma-row { display: grid; grid-template-columns: 74px 1fr auto; gap: 12px; align-items: center; padding: 9px 12px;
      border: 1px solid var(--line); border-radius: 11px; background: var(--elev); }
    .ma-row b { font-variant-numeric: tabular-nums; }
    .ma-track { position: relative; height: 8px; border-radius: 999px; background: var(--input-bg); overflow: hidden; }
    .ma-track i { position: absolute; top: 0; bottom: 0; border-radius: 999px; }
    .ma-track i.up { background: var(--good); left: 50%; }
    .ma-track i.down { background: var(--bad); right: 50%; }

    @media (max-width: 720px) {
      .navbar { flex-wrap: wrap; padding: 10px 16px; }
      .nav-search { order: 3; flex: 1 0 100%; }
      main { padding: 16px 14px 50px; }
      .ma-row { grid-template-columns: 62px 1fr auto; }
    }
  </style>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
</head>
<body>
<nav class="navbar" aria-label="Primary">
  <div class="nav-brand">
    <span class="nav-logo">📈</span>
    <span>Market Morning Brief<small id="generatedAt">Pre-market cockpit</small></span>
  </div>
  <span class="nav-live"><span class="live-dot"></span>Live · Pre-market</span>
  <div class="nav-spacer"></div>
  <div class="nav-search">
    <span class="si">🔎</span>
    <input id="globalSearch" type="search" placeholder="Search stocks, sectors, indicators..." aria-label="Search dashboard">
    <kbd>Ctrl K</kbd>
  </div>
  <div class="nav-clock">
    <b id="navClock">--:--:--</b>
    <small id="navUpdated">Updated —</small>
  </div>
  <button class="icon-btn" id="themeToggle" title="Toggle theme (T)" aria-label="Toggle theme">🌙</button>
  <button class="icon-btn" id="refreshBtn" title="Refresh (R)" aria-label="Refresh">↻</button>
</nav>
<main>
  <div id="heroStats" class="hero-stats reveal"></div>
  <section id="hero" class="hero reveal"></section>

  <nav class="tabs" aria-label="Dashboard tabs">
    <button class="tab-btn active" data-tab="overview">Overview</button>
    <button class="tab-btn" data-tab="global">Global Markets</button>
    <button class="tab-btn" data-tab="commodities">Commodities</button>
    <button class="tab-btn" data-tab="natgas">Natural Gas</button>
    <button class="tab-btn" data-tab="crypto">Crypto</button>
    <button class="tab-btn" data-tab="currency">Currency</button>
    <button class="tab-btn" data-tab="sectors">Sectors</button>
    <button class="tab-btn" data-tab="nifty50">Nifty 50</button>
    <button class="tab-btn" data-tab="technicals">Technicals</button>
    <button class="tab-btn" data-tab="signals">Signals</button>
    <button class="tab-btn" data-tab="history">History</button>
    <button class="tab-btn" data-tab="news">News</button>
    <button class="tab-btn" data-tab="events">Events</button>
    <button class="tab-btn" data-tab="report">Full Report</button>
    
  </nav>

  <section id="overview" class="panel active">
    <div class="card ai-card">
      <div class="card-head"><h2>🧠 AI Morning Summary</h2><span class="badge info">Auto-generated</span></div>
      <ul id="aiSummary" class="summary-list"></ul>
    </div>

    <h3 class="section-title">📌 Important Levels</h3>
    <div id="levelsGrid" class="levels-grid"></div>

    <h3 class="section-title">📊 Market Indicators</h3>
    <div id="indicatorGrid" class="indicator-grid"></div>

    <h3 class="section-title">🏦 FII / DII Activity <span class="muted" style="font-size:13px;font-weight:500">· provisional, last completed session (₹ Cr)</span></h3>
    <div id="flowCards" class="flow-grid"></div>

    <div class="card" style="margin-top:18px">
      <div class="card-head"><h2>🕒 Market Timeline</h2></div>
      <div id="marketTimeline" class="timeline"></div>
    </div>

    <h3 class="section-title">✅ Pre-Market Prep</h3>
    <div class="grid-2">
      <div class="card">
        <div class="card-head"><h2>Trading Checklist</h2><span id="checklistPct" class="chip-strong">0%</span></div>
        <div class="progress"><span id="checklistProgress"></span></div>
        <div id="checklist" class="checklist"></div>
      </div>
      <div class="card">
        <div class="card-head"><h2>🚨 Alerts</h2></div>
        <div id="alertsPanel" class="alerts"></div>
      </div>
    </div>

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

  <section id="natgas" class="panel">
    <div class="card">
      <div class="card-head">
        <h2>US Natural Gas Storage</h2>
        <span id="gasWeekBadge" class="badge info">—</span>
      </div>
      <p class="muted">
        EIA Weekly Natural Gas Storage Report — working gas in underground
        storage across the Lower 48. Published every Thursday at 10:30 a.m.
        eastern time (08:00 PM IST) for the week ending the previous Friday, so
        this section updates once a week, not daily.
      </p>

      <div id="gasStats" class="hero-stats" style="margin-bottom:14px"></div>
      <div id="gasSignal" class="gas-signal"></div>

      <div class="gas-meta" id="gasMeta"></div>

      <div class="controls">
        <label>Chart
          <select id="gasChartMode">
            <option value="seasonal">Seasonal vs 5-year band</option>
            <option value="trajectory">Storage trajectory (3 years)</option>
            <option value="netchange">Weekly net change</option>
          </select>
        </label>
        <label>Regions
          <select id="gasRegionScope">
            <option value="all">All regions</option>
            <option value="main">Main regions only</option>
          </select>
        </label>
        <button class="action-btn secondary" id="gasCsv">Download CSV</button>
      </div>

      <div class="chart-box"><canvas id="gasChart"></canvas></div>

      <div class="table-wrap" style="margin-top:14px">
        <table>
          <thead>
            <tr>
              <th>Region</th>
              <th>Stocks (Bcf)</th>
              <th>Prior Week</th>
              <th>Net Change</th>
              <th>vs Year Ago</th>
              <th>vs 5-Yr Avg</th>
            </tr>
          </thead>
          <tbody id="gasRows"></tbody>
        </table>
      </div>

      <div class="chart-box" style="margin-top:18px"><canvas id="gasRegionChart"></canvas></div>

      <p id="gasFootnote" class="small muted" style="margin-top:10px"></p>
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

  <section id="nifty50" class="panel">
    <div class="card">
      <div class="card-head">
        <h2>📋 Nifty 50 Pivot Table</h2>
        <span id="nifty50AsOf" class="badge info">—</span>
      </div>
      <p class="small muted" style="margin:0 0 10px">Classic floor-trader pivots from the last completed session, with NSE % change across daily, weekly (5 sessions) and monthly (21 sessions) horizons.</p>
      <div id="nifty50Breadth" class="hero-stats" style="margin-bottom:14px"></div>
      <div class="breadth-bar" id="nifty50BreadthBar"></div>
      <div class="controls">
        <input id="nifty50Search" placeholder="Search stock or symbol..." />
        <select id="nifty50Sector">
          <option value="All">All sectors</option>
        </select>
        <select id="nifty50Sort">
          <option value="change_pct_desc">Daily % high to low</option>
          <option value="change_pct_asc">Daily % low to high</option>
          <option value="week_pct_desc">Weekly % high to low</option>
          <option value="month_pct_desc">Monthly % high to low</option>
          <option value="vs_pivot_pct_desc">Distance from pivot</option>
          <option value="rsi_desc">RSI high to low</option>
          <option value="name">Name A to Z</option>
        </select>
        <select id="nifty50View">
          <option value="flat">Flat list</option>
          <option value="grouped">Group by sector</option>
        </select>
        <select id="nifty50Zone">
          <option value="All">All pivot zones</option>
          <option value="above">Above pivot</option>
          <option value="below">Below pivot</option>
        </select>
        <button class="action-btn secondary" id="nifty50Csv">Download CSV</button>
      </div>
      <div class="table-wrap pivot-wrap">
        <table class="pivot-table">
          <thead>
            <tr>
              <th>Stock</th>
              <th class="num">LTP</th>
              <th class="num">Daily %</th>
              <th class="num">Weekly %</th>
              <th class="num">Monthly %</th>
              <th class="num">S2</th>
              <th class="num">S1</th>
              <th class="num">Pivot</th>
              <th class="num">R1</th>
              <th class="num">R2</th>
              <th class="num">vs Pivot</th>
              <th class="num">RSI</th>
              <th>Zone</th>
            </tr>
          </thead>
          <tbody id="nifty50Rows"></tbody>
        </table>
      </div>
    </div>
    <div class="grid-2">
      <div class="card">
        <div class="card-head"><h2>Sector Roll-Up</h2><span class="badge info">Average % change</span></div>
        <div class="chart-box"><canvas id="nifty50SectorChart"></canvas></div>
      </div>
      <div class="card">
        <div class="card-head"><h2>Multi-Timeframe Leaders</h2><span class="badge info">Top 12 by daily move</span></div>
        <div class="chart-box"><canvas id="nifty50TimeframeChart"></canvas></div>
      </div>
    </div>
  </section>

  <section id="technicals" class="panel">
    <div class="card">
      <div class="card-head">
        <h2>📈 Index Moving Averages &amp; Indicators</h2>
        <span id="technicalAsOf" class="badge info">—</span>
      </div>
      <div class="controls">
        <select id="technicalIndex"></select>
        <select id="technicalMaOverlay">
          <option value="sma">Simple moving averages</option>
          <option value="bollinger">Bollinger bands (20,2)</option>
        </select>
      </div>
      <div class="tech-head" id="technicalHead"></div>
      <div class="ind-grid" id="technicalIndicators"></div>
    </div>

    <div class="card">
      <div class="card-head"><h2>Price vs Moving Averages</h2><span id="technicalTrend" class="badge info">—</span></div>
      <div class="chart-box tall"><canvas id="maChart"></canvas></div>
      <div class="ma-ladder" id="maLadder" style="margin-top:14px"></div>
    </div>

    <div class="grid-2">
      <div class="card">
        <div class="card-head"><h2>RSI (14)</h2><span class="badge info">70 / 30 bands</span></div>
        <div class="chart-box mini"><canvas id="rsiChart"></canvas></div>
      </div>
      <div class="card">
        <div class="card-head"><h2>MACD (12, 26, 9)</h2><span class="badge info">Line, signal, histogram</span></div>
        <div class="chart-box mini"><canvas id="macdChart"></canvas></div>
      </div>
    </div>

    <div class="card">
      <div class="card-head"><h2>Index Pivot Levels</h2><span class="badge info">Last completed session</span></div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Index</th><th class="num">Close</th><th class="num">S3</th><th class="num">S2</th><th class="num">S1</th><th class="num">Pivot</th><th class="num">R1</th><th class="num">R2</th><th class="num">R3</th><th>Trend</th></tr></thead>
          <tbody id="indexPivotRows"></tbody>
        </table>
      </div>
    </div>
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
  <h2 id="pcrHeading">5-Day Rolling Put-Call Ratio</h2>
  <p class="muted">
    Tracks Nifty and Bank Nifty PCR trend across the last generated reports.
    Card colour shows momentum vs the rolling average — green rising, red falling, amber stable.
  </p>

  <div class="controls">
    <label>Rolling window
      <select id="pcrWindow">
        <option value="5" selected>5 days</option>
        <option value="10">10 days</option>
        <option value="15">15 days</option>
        <option value="20">20 days</option>
      </select>
    </label>
  </div>

  <div id="pcrSummaryGrid" class="pcr-summary-grid"></div>

  <div class="chart-box"><canvas id="pcrRollingChart"></canvas></div>

  <div class="table-wrap" style="margin-top:14px">
    <table>
      <thead>
        <tr>
          <th>Date</th>
          <th>Nifty PCR</th>
          <th id="pcrNiftyAvgHead">Nifty 5D Avg</th>
          <th>Bank Nifty PCR</th>
          <th id="pcrBankAvgHead">Bank Nifty 5D Avg</th>
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

  <section id="events" class="panel">
    <div class="card">
      <div class="card-head">
        <h2>🗓️ Corporate Event Calendar</h2>
        <span id="eventDateBadge" class="badge info">—</span>
      </div>
      <p class="muted">
        NSE board meetings and corporate actions listed for this one date only.
        Nifty 50 constituents are flagged and sorted to the top — those are the
        results that can move the index at the open.
      </p>

      <div id="eventStats" class="hero-stats" style="margin-bottom:14px"></div>
      <div id="eventCategoryBar" class="event-catbar"></div>

      <div class="controls">
        <input id="eventSearch" placeholder="Search company, symbol or purpose..." />
        <select id="eventCategory"><option value="All">All categories</option></select>
        <select id="eventScope">
          <option value="all">All companies</option>
          <option value="nifty50">Nifty 50 only</option>
        </select>
        <button class="action-btn secondary" id="eventCsv">Download CSV</button>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr><th>Symbol</th><th>Company</th><th>Purpose</th><th>Details</th></tr>
          </thead>
          <tbody id="eventRows"></tbody>
        </table>
      </div>
      <p id="eventCount" class="small muted" style="margin-top:10px"></p>
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

  <footer class="site-footer">
    <div class="fcol">
      <strong style="color:var(--text)">Market Morning Brief</strong>
      <span>Pre-market decision cockpit · Not financial advice</span>
    </div>
    <div class="fcol">
      <span>Data: NSE · Yahoo Finance · RSS feeds</span>
      <span id="footerUpdated">Last update —</span>
    </div>
    <div class="fcol">
      <a href="https://github.com/DeepPandya30/market-morning-brief" target="_blank" rel="noopener">GitHub ↗</a>
      <a href="mailto:dk15pandya@gmail.com">Feedback</a>
      <span>v2.0 · Cockpit UI</span>
    </div>
  </footer>
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
        title: { display: !!title, text: title, align: 'start', font: { size: 13, weight: '700' }, color: '#94a3b8', padding: { bottom: 8 } },
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
/* ---------- Nifty 50 pivot table ---------- */
function nifty50Data() {
  return APP.data.nifty50 || { rows: [], sectors: [], breadth: {} };
}
function cellClass(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return 'cell-flat';
  if (n > 0.05) return 'cell-up';
  if (n < -0.05) return 'cell-down';
  return 'cell-flat';
}
function pctCell(value) {
  return `<td class="num ${cellClass(value)}">${pct(value)}</td>`;
}
function zoneTag(row) {
  const vs = Number(row.vs_pivot_pct);
  const cls = Number.isFinite(vs) ? (vs >= 0 ? 'up' : 'down') : '';
  return `<span class="zone-tag ${cls}">${escapeHtml(row.zone || 'N/A')}</span>`;
}
function populateNifty50Sectors() {
  const select = document.getElementById('nifty50Sector');
  if (!select || select.dataset.filled) return;
  const sectors = [...new Set(nifty50Data().rows.map(r => r.sector).filter(Boolean))].sort();
  select.insertAdjacentHTML('beforeend', sectors.map(s => `<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`).join(''));
  select.dataset.filled = '1';
}
function nifty50Filtered() {
  const search = (document.getElementById('nifty50Search')?.value || '').trim().toLowerCase();
  const sector = document.getElementById('nifty50Sector')?.value || 'All';
  const zone = document.getElementById('nifty50Zone')?.value || 'All';
  const sort = document.getElementById('nifty50Sort')?.value || 'change_pct_desc';

  let rows = nifty50Data().rows.slice();
  if (search) rows = rows.filter(r => `${r.symbol} ${r.name}`.toLowerCase().includes(search));
  if (sector !== 'All') rows = rows.filter(r => r.sector === sector);
  if (zone === 'above') rows = rows.filter(r => Number(r.vs_pivot_pct) >= 0);
  if (zone === 'below') rows = rows.filter(r => Number(r.vs_pivot_pct) < 0);

  if (sort === 'name') {
    rows.sort((a, b) => String(a.name || '').localeCompare(String(b.name || '')));
  } else {
    const key = sort.replace(/_(asc|desc)$/, '');
    const dir = sort.endsWith('_asc') ? 1 : -1;
    rows.sort((a, b) => {
      const av = Number.isFinite(Number(a[key])) ? Number(a[key]) : -999999;
      const bv = Number.isFinite(Number(b[key])) ? Number(b[key]) : -999999;
      return (av - bv) * dir;
    });
  }
  return rows;
}
function nifty50RowHtml(row) {
  return `<tr>
    <td class="sym">${escapeHtml(row.symbol || '')}<small>${escapeHtml(row.name || '')}</small></td>
    <td class="num">${num(row.close)}</td>
    ${pctCell(row.change_pct)}${pctCell(row.week_pct)}${pctCell(row.month_pct)}
    <td class="num lvl">${num(row.s2)}</td>
    <td class="num lvl">${num(row.s1)}</td>
    <td class="num"><strong>${num(row.pivot)}</strong></td>
    <td class="num lvl">${num(row.r1)}</td>
    <td class="num lvl">${num(row.r2)}</td>
    ${pctCell(row.vs_pivot_pct)}
    <td class="num">${row.rsi === null || row.rsi === undefined ? 'N/A' : Number(row.rsi).toFixed(1)}</td>
    <td>${zoneTag(row)}</td>
  </tr>`;
}
function renderNifty50() {
  populateNifty50Sectors();
  const tbody = document.getElementById('nifty50Rows');
  if (!tbody) return;
  const rows = nifty50Filtered();
  const grouped = (document.getElementById('nifty50View')?.value || 'flat') === 'grouped';

  let html = '';
  if (!rows.length) {
    html = '<tr><td colspan="13">No Nifty 50 constituent data available. Check fetch warnings.</td></tr>';
  } else if (grouped) {
    const buckets = {};
    rows.forEach(r => { (buckets[r.sector || 'Other'] = buckets[r.sector || 'Other'] || []).push(r); });
    html = Object.keys(buckets).sort().map(sector => {
      const members = buckets[sector];
      const avg = members.reduce((a, r) => a + (Number(r.change_pct) || 0), 0) / members.length;
      return `<tr class="grp-head"><td colspan="13">${escapeHtml(sector)} · ${members.length} stocks · avg ${pct(avg)}</td></tr>`
        + members.map(nifty50RowHtml).join('');
    }).join('');
  } else {
    html = rows.map(nifty50RowHtml).join('');
  }
  tbody.innerHTML = html;

  const asOf = document.getElementById('nifty50AsOf');
  if (asOf) asOf.textContent = nifty50Data().as_of ? `As of ${nifty50Data().as_of}` : 'No data';
  renderNifty50Breadth();
  drawSectorRollupChart();
  drawTimeframeChart(rows);
}
function renderNifty50Breadth() {
  const breadth = nifty50Data().breadth || {};
  const host = document.getElementById('nifty50Breadth');
  if (!host) return;
  const tiles = [
    ['Advancing', breadth.advancing ?? 'N/A', 'st-good', 'Stocks closing higher'],
    ['Declining', breadth.declining ?? 'N/A', 'st-bad', 'Stocks closing lower'],
    ['Above Pivot', breadth.above_pivot ?? 'N/A', 'st-brand', 'Spot at or above daily pivot'],
    ['Avg Daily', pct(breadth.avg_change_pct), signedTile(breadth.avg_change_pct), 'Index-wide average'],
    ['Avg Weekly', pct(breadth.avg_week_pct), signedTile(breadth.avg_week_pct), 'Last 5 sessions'],
    ['Avg Monthly', pct(breadth.avg_month_pct), signedTile(breadth.avg_month_pct), 'Last 21 sessions'],
  ];
  host.innerHTML = tiles.map(([label, value, cls, sub]) => `
    <div class="stat-tile ${cls}">
      <div class="st-label">${label}</div>
      <div class="st-value">${value}</div>
      <div class="st-sub">${escapeHtml(sub)}</div>
    </div>`).join('');

  const bar = document.getElementById('nifty50BreadthBar');
  if (bar) {
    const adv = Number(breadth.advancing || 0);
    const dec = Number(breadth.declining || 0);
    const unc = Number(breadth.unchanged || 0);
    const total = adv + dec + unc || 1;
    bar.innerHTML = `<i class="adv" style="width:${(adv / total) * 100}%"></i>`
      + `<i class="unc" style="width:${(unc / total) * 100}%"></i>`
      + `<i class="dec" style="width:${(dec / total) * 100}%"></i>`;
    bar.title = `${adv} advancing · ${unc} unchanged · ${dec} declining`;
  }
}
function signedTile(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return 'st-neutral';
  return n > 0 ? 'st-good' : n < 0 ? 'st-bad' : 'st-neutral';
}
function downloadNifty50Csv() {
  const cols = ['symbol', 'name', 'sector', 'close', 'change_pct', 'week_pct', 'month_pct', 's3', 's2', 's1', 'pivot', 'r1', 'r2', 'r3', 'vs_pivot_pct', 'rsi', 'zone'];
  const rows = nifty50Filtered();
  const lines = [cols.join(',')].concat(rows.map(r => cols.map(c => {
    const v = r[c];
    return typeof v === 'string' && v.includes(',') ? `"${v}"` : (v ?? '');
  }).join(',')));
  downloadText(`nifty50_pivots_${nifty50Data().as_of || 'latest'}.csv`, lines.join('\\n'));
}
function drawSectorRollupChart() {
  const sectors = (nifty50Data().sectors || []).map(s => ({ name: s.sector, change_pct: s.change_pct, close: s.count }));
  drawBarChart('nifty50SectorChart', sectors, 'name', 'change_pct', 'Average change % by sector');
}
function drawTimeframeChart(rows) {
  const data = (rows || []).slice(0, 12);
  mountChart('nifty50TimeframeChart', {
    type: 'bar',
    data: {
      labels: data.map(r => r.symbol),
      datasets: [
        { label: 'Daily %', data: data.map(r => r.change_pct), backgroundColor: 'rgba(37,99,235,.85)', borderRadius: 4, maxBarThickness: 14 },
        { label: 'Weekly %', data: data.map(r => r.week_pct), backgroundColor: 'rgba(139,92,246,.8)', borderRadius: 4, maxBarThickness: 14 },
        { label: 'Monthly %', data: data.map(r => r.month_pct), backgroundColor: 'rgba(6,182,212,.75)', borderRadius: 4, maxBarThickness: 14 },
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      scales: {
        x: { grid: { display: false }, border: { display: false }, ticks: { font: { size: 10 }, maxRotation: 60, minRotation: 45 } },
        y: { grid: { color: C.grid }, border: { display: false }, ticks: { callback: v => v + '%' } }
      },
      plugins: {
        legend: { display: true, position: 'top', labels: { usePointStyle: true, boxWidth: 8, font: { size: 11 } } },
        tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y === null ? 'N/A' : ctx.parsed.y.toFixed(2) + '%'}` } }
      }
    },
    plugins: [emptyMessagePlugin('No constituent data available')]
  });
}

/* ---------- Index moving averages and indicators ---------- */
const MA_COLORS = { 20: '#f59e0b', 50: '#8b5cf6', 100: '#06b6d4', 200: '#ef4444' };
function techData() { return APP.data.index_technicals || {}; }
function populateTechnicalIndexes() {
  const select = document.getElementById('technicalIndex');
  if (!select || select.dataset.filled) return;
  const keys = Object.keys(techData());
  select.innerHTML = keys.length
    ? keys.map(k => `<option value="${escapeHtml(k)}">${escapeHtml(k)}</option>`).join('')
    : '<option value="">No index data</option>';
  select.dataset.filled = '1';
}
function currentTechnical() {
  const key = document.getElementById('technicalIndex')?.value;
  const all = techData();
  return all[key] || all[Object.keys(all)[0]] || null;
}
function renderTechnicals() {
  populateTechnicalIndexes();
  const snap = currentTechnical();
  const head = document.getElementById('technicalHead');
  const tiles = document.getElementById('technicalIndicators');
  const ladder = document.getElementById('maLadder');
  const asOf = document.getElementById('technicalAsOf');
  const trend = document.getElementById('technicalTrend');

  if (!snap) {
    if (head) head.innerHTML = '<span class="muted">Index technical data unavailable in this run.</span>';
    if (tiles) tiles.innerHTML = '';
    if (ladder) ladder.innerHTML = '';
    renderIndexPivots();
    return;
  }

  if (asOf) asOf.textContent = `As of ${snap.date || 'N/A'}`;
  if (trend) {
    trend.textContent = snap.trend?.label || 'N/A';
    trend.className = 'badge ' + badgeClass(snap.trend?.label);
  }
  if (head) {
    head.innerHTML = `
      <div>
        <div class="muted small">${escapeHtml(snap.label || '')} · ${escapeHtml(snap.ticker || '')}</div>
        <div class="tv">${num(snap.close)}</div>
      </div>
      <span class="hero-chip">Daily <b class="${signedClass(snap.change_pct) === 'good' ? 'tone-good' : signedClass(snap.change_pct) === 'bad' ? 'tone-bad' : 'tone-neutral'}">${pct(snap.change_pct)}</b></span>
      <span class="hero-chip">Weekly <b>${pct(snap.week_pct)}</b></span>
      <span class="hero-chip">Monthly <b>${pct(snap.month_pct)}</b></span>
      <span class="hero-chip">52w range <b>${num(snap.year_low)} – ${num(snap.year_high)}</b></span>
      <span class="hero-chip">${escapeHtml(snap.trend?.note || '')}</span>`;
  }
  if (tiles) {
    tiles.innerHTML = (snap.indicators || []).map(ind => `
      <div class="ind-tile">
        <div class="it-name">${escapeHtml(ind.name)}</div>
        <div class="it-val">${num(ind.value)}</div>
        <div>${badge(ind.status)}</div>
        <div class="it-note" style="margin-top:6px">${escapeHtml(ind.note || '')}</div>
      </div>`).join('');
  }
  if (ladder) {
    ladder.innerHTML = (snap.moving_averages || []).map(ma => {
      const dist = Number(ma.distance_pct);
      const width = Number.isFinite(dist) ? Math.min(Math.abs(dist) * 6, 50) : 0;
      const dir = dist >= 0 ? 'up' : 'down';
      return `
      <div class="ma-row">
        <b>${ma.period} DMA</b>
        <div>
          <div class="small muted">SMA ${num(ma.sma)} · EMA ${num(ma.ema)}</div>
          <div class="ma-track"><i class="${dir}" style="width:${width}%"></i></div>
        </div>
        <span class="badge ${dist >= 0 ? 'good' : 'bad'}">${ma.position} ${pct(ma.distance_pct)}</span>
      </div>`;
    }).join('') || '<p class="muted">Not enough history for moving averages.</p>';
  }

  const overlay = document.getElementById('technicalMaOverlay')?.value || 'sma';
  drawMaChart(snap, overlay);
  drawRsiChart(snap);
  drawMacdChart(snap);
  renderIndexPivots();
}
function renderIndexPivots() {
  const tbody = document.getElementById('indexPivotRows');
  if (!tbody) return;
  const entries = Object.values(techData());
  tbody.innerHTML = entries.map(snap => {
    const lv = snap.levels || {};
    return `<tr>
      <td>${escapeHtml(snap.label || '')}</td>
      <td class="num">${num(snap.close)}</td>
      <td class="num lvl">${num(lv.s3)}</td>
      <td class="num lvl">${num(lv.s2)}</td>
      <td class="num lvl">${num(lv.s1)}</td>
      <td class="num"><strong>${num(lv.pivot)}</strong></td>
      <td class="num lvl">${num(lv.r1)}</td>
      <td class="num lvl">${num(lv.r2)}</td>
      <td class="num lvl">${num(lv.r3)}</td>
      <td>${badge(snap.trend?.label)}</td>
    </tr>`;
  }).join('') || '<tr><td colspan="10">No index technical data available.</td></tr>';
}
function seriesLabels(series) {
  return series.map(p => String(p.date || '').slice(5));
}
function drawMaChart(snap, overlay) {
  const series = snap.series || [];
  const labels = seriesLabels(series);
  const datasets = [{
    label: 'Close',
    data: series.map(p => p.close),
    borderColor: C.brand,
    backgroundColor: ctx => {
      const { chartArea, ctx: c } = ctx.chart;
      if (!chartArea) return 'rgba(37,99,235,.10)';
      const g = c.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
      g.addColorStop(0, 'rgba(37,99,235,.26)');
      g.addColorStop(1, 'rgba(37,99,235,.01)');
      return g;
    },
    fill: true,
    borderWidth: 2.4,
    tension: 0.2,
    pointRadius: 0,
    pointHoverRadius: 5,
    order: 5
  }];

  if (overlay === 'bollinger') {
    datasets.push(
      { label: 'Upper band', data: series.map(p => p.bb_upper), borderColor: 'rgba(148,163,184,.85)', borderWidth: 1.4, borderDash: [5, 4], pointRadius: 0, fill: false, tension: 0.2 },
      { label: 'Lower band', data: series.map(p => p.bb_lower), borderColor: 'rgba(148,163,184,.85)', borderWidth: 1.4, borderDash: [5, 4], pointRadius: 0, fill: '-1', backgroundColor: 'rgba(148,163,184,.10)', tension: 0.2 }
    );
  } else {
    Object.keys(MA_COLORS).forEach(period => {
      const key = 'sma' + period;
      if (!series.some(p => p[key] !== null && p[key] !== undefined)) return;
      datasets.push({
        label: `${period} DMA`,
        data: series.map(p => p[key]),
        borderColor: MA_COLORS[period],
        borderWidth: 1.7,
        pointRadius: 0,
        pointHoverRadius: 4,
        fill: false,
        tension: 0.2,
        spanGaps: true
      });
    });
  }

  mountChart('maChart', {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      scales: {
        x: { grid: { display: false }, border: { display: false }, ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 10 } },
        y: { grid: { color: C.grid }, border: { display: false }, ticks: { callback: v => num(v) } }
      },
      plugins: {
        legend: { display: true, position: 'top', labels: { usePointStyle: true, boxWidth: 8, font: { size: 11 } } },
        tooltip: {
          callbacks: {
            title: items => 'Date ' + (series[items[0].dataIndex]?.date || ''),
            label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y === null ? 'N/A' : num(ctx.parsed.y)}`
          }
        }
      }
    },
    plugins: [emptyMessagePlugin('No price history available')]
  });
}
function drawRsiChart(snap) {
  const series = snap.series || [];
  mountChart('rsiChart', {
    type: 'line',
    data: {
      labels: seriesLabels(series),
      datasets: [{
        label: 'RSI (14)',
        data: series.map(p => p.rsi),
        borderColor: '#8b5cf6',
        backgroundColor: 'rgba(139,92,246,.12)',
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 5,
        fill: true,
        tension: 0.25,
        spanGaps: true
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      scales: {
        x: { grid: { display: false }, border: { display: false }, ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } },
        y: { min: 0, max: 100, grid: { color: C.grid }, border: { display: false }, ticks: { stepSize: 25 } }
      },
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { title: items => 'Date ' + (series[items[0].dataIndex]?.date || '') } }
      }
    },
    plugins: [emptyMessagePlugin('No RSI data available'), rsiBandsPlugin()]
  });
}
function rsiBandsPlugin() {
  return {
    id: 'rsiBands',
    beforeDatasetsDraw(chart) {
      const { ctx, chartArea, scales } = chart;
      if (!chartArea || !scales.y) return;
      ctx.save();
      ctx.fillStyle = 'rgba(220,38,38,.10)';
      const top = scales.y.getPixelForValue(100);
      const seventy = scales.y.getPixelForValue(70);
      ctx.fillRect(chartArea.left, top, chartArea.right - chartArea.left, seventy - top);
      ctx.fillStyle = 'rgba(22,163,74,.10)';
      const thirty = scales.y.getPixelForValue(30);
      const bottom = scales.y.getPixelForValue(0);
      ctx.fillRect(chartArea.left, thirty, chartArea.right - chartArea.left, bottom - thirty);
      ctx.restore();
    }
  };
}
function drawMacdChart(snap) {
  const series = snap.series || [];
  mountChart('macdChart', {
    data: {
      labels: seriesLabels(series),
      datasets: [
        {
          type: 'bar',
          label: 'Histogram',
          data: series.map(p => p.hist),
          backgroundColor: series.map(p => (Number(p.hist) >= 0 ? 'rgba(22,163,74,.55)' : 'rgba(220,38,38,.55)')),
          borderWidth: 0,
          maxBarThickness: 6,
          order: 3
        },
        { type: 'line', label: 'MACD', data: series.map(p => p.macd), borderColor: C.brand, borderWidth: 2, pointRadius: 0, fill: false, tension: 0.2, order: 1 },
        { type: 'line', label: 'Signal', data: series.map(p => p.signal), borderColor: '#f59e0b', borderWidth: 1.6, pointRadius: 0, fill: false, tension: 0.2, order: 2 }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      scales: {
        x: { grid: { display: false }, border: { display: false }, ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } },
        y: { grid: { color: C.grid }, border: { display: false } }
      },
      plugins: {
        legend: { display: true, position: 'top', labels: { usePointStyle: true, boxWidth: 8, font: { size: 11 } } },
        tooltip: { callbacks: { title: items => 'Date ' + (series[items[0].dataIndex]?.date || '') } }
      }
    },
    plugins: [emptyMessagePlugin('No MACD data available')]
  });
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
populateEventCategories();
renderEventCalendar();
renderNaturalGas();
renderMeetingMode();
  const brandSub = document.getElementById('generatedAt');
  if (brandSub) brandSub.textContent = APP.generated_at ? `Updated ${APP.generated_at}` : 'Pre-market cockpit';
  const navUpd = document.getElementById('navUpdated');
  if (navUpd) navUpd.textContent = APP.generated_at ? `Updated ${APP.generated_at}` : 'Updated —';
  const footUpd = document.getElementById('footerUpdated');
  if (footUpd) footUpd.textContent = APP.generated_at ? `Last update ${APP.generated_at}` : 'Last update —';
  document.getElementById('marketView').textContent = APP.market_view || '';
  document.getElementById('riskNote').textContent = APP.risk_note || '';
  document.getElementById('markdownReport').textContent = APP.markdown || '';
  renderOICards(); renderGlobal(); renderCommodities(); renderCrypto(); renderCurrency(); renderSectors(); renderNifty50(); renderTechnicals(); renderSignals(); renderHistory(); renderWarnings();
  renderHeroStats(); renderAiSummary(); renderChecklist(); renderAlerts(); renderLevels(); renderIndicators(); renderFlow(); renderTimeline();
  drawBarChart('globalMiniChart', (APP.data.global_markets || []).slice(0, 8), 'name', 'change_pct', 'Change %');
  drawBarChart('sectorMiniChart', ((APP.data.nse_indices || {}).sectors || []).slice(0, 8), 'name', 'change_pct', 'Change %');
  drawBarChart('commodityMiniChart', (APP.data.commodities || []).slice(0, 8), 'name', 'change_pct', 'Change %');
  drawBarChart('cryptoMiniChart', (APP.data.crypto || []).slice(0, 8), 'name', 'change_pct', 'Change %');
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

function getPcrWindowSize() {
  const select = document.getElementById('pcrWindow');
  const size = select ? parseInt(select.value, 10) : 5;
  return Number.isFinite(size) && size > 0 ? size : 5;
}

function calculateRollingPcr(rows, windowSize) {
  const span = Number.isFinite(windowSize) && windowSize > 0 ? windowSize : 5;
  return rows.map((row, index) => {
    const windowRows = rows.slice(Math.max(0, index - (span - 1)), index + 1);

    return {
      ...row,
      nifty_pcr_avg: average(windowRows.map(r => r.nifty_pcr)),
      banknifty_pcr_avg: average(windowRows.map(r => r.banknifty_pcr)),
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

function pcrSentimentClass(current, rolling) {
  if (current === null || current === undefined || rolling === null || rolling === undefined) {
    return '';
  }

  const diff = Number(current) - Number(rolling);

  if (diff > 0.08) return 'pcr-bullish';
  if (diff < -0.08) return 'pcr-bearish';

  return 'pcr-neutral';
}

function renderPcrRolling() {
  const windowSize = getPcrWindowSize();
  const rows = calculateRollingPcr(getPcrHistoryRows(), windowSize);

  const summaryEl = document.getElementById('pcrSummaryGrid');
  const tableEl = document.getElementById('pcrRollingRows');

  if (!summaryEl || !tableEl) return;

  const heading = document.getElementById('pcrHeading');
  if (heading) heading.textContent = `${windowSize}-Day Rolling Put-Call Ratio`;

  const niftyHead = document.getElementById('pcrNiftyAvgHead');
  if (niftyHead) niftyHead.textContent = `Nifty ${windowSize}D Avg`;
  const bankHead = document.getElementById('pcrBankAvgHead');
  if (bankHead) bankHead.textContent = `Bank Nifty ${windowSize}D Avg`;

  const latest = rows[rows.length - 1] || {};

  summaryEl.innerHTML = `
    <div class="pcr-mini-card ${pcrSentimentClass(latest.nifty_pcr, latest.nifty_pcr_avg)}">
      <div class="muted">Nifty PCR</div>
      <div class="metric">${num(latest.nifty_pcr)}</div>
      <div class="small muted">${windowSize}D Avg: ${num(latest.nifty_pcr_avg)} | <span class="pcr-status">${pcrStatusText(latest.nifty_pcr, latest.nifty_pcr_avg)}</span></div>
    </div>
    <div class="pcr-mini-card ${pcrSentimentClass(latest.banknifty_pcr, latest.banknifty_pcr_avg)}">
      <div class="muted">Bank Nifty PCR</div>
      <div class="metric">${num(latest.banknifty_pcr)}</div>
      <div class="small muted">${windowSize}D Avg: ${num(latest.banknifty_pcr_avg)} | <span class="pcr-status">${pcrStatusText(latest.banknifty_pcr, latest.banknifty_pcr_avg)}</span></div>
    </div>
  `;

  tableEl.innerHTML = rows.slice().reverse().map(row => `
    <tr>
      <td>${escapeHtml(row.date)}</td>
      <td>${num(row.nifty_pcr)}</td>
      <td>${num(row.nifty_pcr_avg)}</td>
      <td>${num(row.banknifty_pcr)}</td>
      <td>${num(row.banknifty_pcr_avg)}</td>
    </tr>
  `).join('') || '<tr><td colspan="5">PCR history will appear after workflow runs.</td></tr>';

  drawPcrRollingChart('pcrRollingChart', rows);
}

function drawPcrRollingChart(canvasId, rows) {
  const data = (rows || []).filter(r => r.nifty_pcr !== null || r.banknifty_pcr !== null).slice(-30);
  const labels = data.map(r => String(r.date || '').slice(5));
  const series = [
    { key: 'nifty_pcr', color: '#2563eb', label: 'Nifty PCR', dash: [] },
    { key: 'nifty_pcr_avg', color: '#60a5fa', label: 'Nifty Avg', dash: [6, 4] },
    { key: 'banknifty_pcr', color: '#16a34a', label: 'Bank Nifty PCR', dash: [] },
    { key: 'banknifty_pcr_avg', color: '#4ade80', label: 'Bank Nifty Avg', dash: [6, 4] },
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

function eventData() {
  return APP.data.event_calendar || {};
}
function eventCategoryClass(category) {
  const c = String(category || '').toLowerCase();
  if (c.includes('result')) return 'cat-results';
  if (c.includes('dividend')) return 'cat-dividend';
  if (c.includes('buyback')) return 'cat-buyback';
  if (c.includes('bonus') || c.includes('split')) return 'cat-bonus';
  if (c.includes('fund')) return 'cat-fund';
  if (c.includes('m&a') || c.includes('restructur')) return 'cat-ma';
  return '';
}
function populateEventCategories() {
  const select = document.getElementById('eventCategory');
  if (!select) return;
  const current = select.value || 'All';
  const cats = (eventData().category_counts || []).map(row => row.name);
  select.innerHTML = '<option value="All">All categories</option>'
    + cats.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('');
  select.value = cats.includes(current) ? current : 'All';
}
function eventsFiltered() {
  const search = (document.getElementById('eventSearch')?.value || '').toLowerCase().trim();
  const category = document.getElementById('eventCategory')?.value || 'All';
  const scope = document.getElementById('eventScope')?.value || 'all';

  let rows = eventData().events || [];
  if (scope === 'nifty50') rows = rows.filter(row => row.is_nifty50);
  if (category !== 'All') rows = rows.filter(row => row.category === category);
  if (search) {
    rows = rows.filter(row =>
      String(row.symbol || '').toLowerCase().includes(search) ||
      String(row.company || '').toLowerCase().includes(search) ||
      String(row.purpose || '').toLowerCase().includes(search) ||
      String(row.description || '').toLowerCase().includes(search)
    );
  }
  return rows;
}
function renderEventCalendar() {
  const body = document.getElementById('eventRows');
  if (!body) return;

  const cal = eventData();
  const badge = document.getElementById('eventDateBadge');
  if (badge) {
    badge.textContent = cal.date_label
      ? `${cal.date_label}${cal.weekday ? ' · ' + cal.weekday : ''}`
      : 'Date unavailable';
  }

  const stats = document.getElementById('eventStats');
  if (stats) {
    const top = (cal.category_counts || [])[0] || {};
    const tiles = [
      ['Announcements', cal.total ?? 0, 'st-brand', `Companies reporting on ${cal.date_label || 'this date'}`],
      ['Nifty 50 Names', cal.nifty50_count ?? 0, (cal.nifty50_count ? 'st-good' : 'st-neutral'), 'Index constituents in focus'],
      ['Top Category', top.count ?? 0, 'st-neutral', top.name ? escapeHtml(top.name) : 'No events listed'],
    ];
    stats.innerHTML = tiles.map(([label, value, cls, sub]) => `
      <div class="stat-tile ${cls}">
        <div class="st-label">${label}</div>
        <div class="st-value">${value}</div>
        <div class="st-sub">${sub}</div>
      </div>`).join('');
  }

  const bar = document.getElementById('eventCategoryBar');
  if (bar) {
    bar.innerHTML = (cal.category_counts || []).map(row =>
      `<span class="event-chip">${escapeHtml(row.name)}<b>${row.count}</b></span>`
    ).join('');
  }

  const rows = eventsFiltered();
  body.innerHTML = rows.map(row => `
    <tr class="${row.is_nifty50 ? 'is-n50' : ''}">
      <td>${escapeHtml(row.symbol || '-')}${row.is_nifty50 ? '<span class="n50-tag">N50</span>' : ''}</td>
      <td>${escapeHtml(row.company || '-')}</td>
      <td><span class="event-purpose ${eventCategoryClass(row.category)}">${escapeHtml(row.purpose || '-')}</span></td>
      <td><div class="event-desc">${escapeHtml(row.description || '')}</div></td>
    </tr>`).join('')
    || `<tr><td colspan="4" class="muted">No events match these filters${cal.total ? '' : ' — nothing is listed for this date (holiday, weekend, or not yet filed)'}.</td></tr>`;

  const count = document.getElementById('eventCount');
  if (count) {
    count.textContent = cal.total
      ? `Showing ${rows.length} of ${cal.total} announcements for ${cal.date_label || 'the selected date'}.`
      : `No announcements listed for ${cal.date_label || 'the selected date'}.`;
  }
}
function downloadEventCsv() {
  const cols = ['symbol', 'company', 'purpose', 'category', 'description', 'is_nifty50'];
  const rows = eventsFiltered();
  const lines = [cols.join(',')].concat(rows.map(r => cols.map(c => {
    const v = r[c];
    const text = v === null || v === undefined ? '' : String(v);
    return /[",\\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  }).join(',')));
  downloadText(`nse_event_calendar_${eventData().date || 'latest'}.csv`, lines.join('\\n'));
}

/* ---------- EIA weekly natural gas storage ---------- */

// The gas report lands Thursday 20:00 IST, hours after the morning brief was
// generated and its payload frozen. A separate weekly job republishes
// data/natural_gas.json, so the page prefers that side-car when it can reach
// it and falls back to the embedded payload otherwise (offline / file://).
let GAS_OVERRIDE = null;

function gasData() {
  return GAS_OVERRIDE || APP.data.natural_gas || {};
}
function gasRegions() {
  const scope = document.getElementById('gasRegionScope')?.value || 'all';
  const rows = gasData().regions || [];
  return scope === 'main' ? rows.filter(r => !r.is_subregion) : rows;
}
function gasBcf(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return 'N/A';
  return fmt.format(Number(value)) + ' Bcf';
}
function gasSignedBcf(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return 'N/A';
  const n = Number(value);
  return (n > 0 ? '+' : '') + fmt.format(n) + ' Bcf';
}

function renderNaturalGas() {
  const body = document.getElementById('gasRows');
  if (!body) return;

  const gas = gasData();
  const total = gas.total || {};
  const stats = gas.stats || {};
  const signal = gas.signal || {};

  const badgeEl = document.getElementById('gasWeekBadge');
  if (badgeEl) {
    badgeEl.textContent = gas.week_ending_label
      ? `Week ending ${gas.week_ending_label}`
      : 'Report unavailable';
    badgeEl.className = 'badge ' + (gas.week_ending_label ? 'info' : 'neutral');
  }

  const statsEl = document.getElementById('gasStats');
  if (statsEl) {
    const change = total.net_change;
    const changeWord = change === null || change === undefined
      ? 'No change reported'
      : (Number(change) >= 0 ? 'Injection into storage' : 'Withdrawal from storage');
    // A surplus to the 5-year average is bearish for gas prices, so the tone
    // on these tiles is deliberately inverted relative to a price change.
    const surplus = Number(total.five_year_pct ?? 0);
    const tiles = [
      ['Working Gas, Lower 48', gasBcf(total.stocks), 'st-brand',
        gas.week_ending_label ? `Week ending ${escapeHtml(gas.week_ending_label)}` : 'Latest EIA print'],
      ['Weekly Net Change', gasSignedBcf(change),
        change === null || change === undefined ? 'st-neutral' : (Number(change) >= 0 ? 'st-good' : 'st-bad'),
        changeWord],
      ['vs 5-Year Average', pct(total.five_year_pct),
        surplus > 0 ? 'st-bad' : (surplus < 0 ? 'st-good' : 'st-neutral'),
        surplus > 0 ? 'Surplus — bearish for gas' : (surplus < 0 ? 'Deficit — bullish for gas' : 'In line with the norm')],
      ['vs Year Ago', pct(total.year_ago_pct),
        Number(total.year_ago_pct ?? 0) > 0 ? 'st-bad' : (Number(total.year_ago_pct ?? 0) < 0 ? 'st-good' : 'st-neutral'),
        stats.period_high ? `3-yr range ${fmt.format(stats.period_low)}–${fmt.format(stats.period_high)} Bcf` : 'Same week last year'],
    ];
    statsEl.innerHTML = tiles.map(([label, value, cls, sub]) => `
      <div class="stat-tile ${cls}">
        <div class="st-label">${label}</div>
        <div class="st-value">${value}</div>
        <div class="st-sub">${sub}</div>
      </div>`).join('');
  }

  const signalEl = document.getElementById('gasSignal');
  if (signalEl) {
    signalEl.className = 'gas-signal tone-' + (signal.tone || 'neutral');
    signalEl.innerHTML = signal.label
      ? `<span class="gas-signal-label">${escapeHtml(signal.label)}</span>
         <span class="gas-signal-note">${escapeHtml(signal.note || '')}</span>`
      : '<span class="gas-signal-note">Storage read unavailable for this week.</span>';
  }

  const metaEl = document.getElementById('gasMeta');
  if (metaEl) {
    const chips = [];
    if (gas.released_label) chips.push(`Released<b>${escapeHtml(gas.released_label)}</b>`);
    if (gas.season) chips.push(`Season<b>${escapeHtml(gas.season)}</b>`);
    if (gas.change_vs_norm !== null && gas.change_vs_norm !== undefined) {
      const d = Number(gas.change_vs_norm);
      chips.push(`vs 5-yr norm this week<b>${(d > 0 ? '+' : '') + fmt.format(d)} Bcf</b>`);
    }
    if (gas.next_release_ist_label) {
      const days = gas.days_to_next_release;
      const when = days === 0 ? 'today' : (days === 1 ? 'tomorrow' : (days > 1 ? `in ${days} days` : 'overdue'));
      chips.push(`Next release<b>${escapeHtml(gas.next_release_ist_label)} (${when})</b>`);
    }
    if (gas.from_cache) chips.push('Source<b>cached — live EIA fetch failed</b>');
    metaEl.innerHTML = chips.map(c => `<span>${c}</span>`).join('')
      + `<span><a href="${escapeHtml(gas.report_url || 'https://ir.eia.gov/ngs/ngs.html')}" target="_blank" rel="noopener">Official EIA report ↗</a></span>`;
  }

  const rows = gasRegions();
  body.innerHTML = rows.map(row => {
    const cls = row.is_total ? 'gas-total' : (row.is_subregion ? 'gas-sub' : '');
    return `
    <tr class="${cls}">
      <td>${escapeHtml(row.name || '-')}</td>
      <td>${gasBcf(row.stocks)}</td>
      <td>${gasBcf(row.prior_stocks)}</td>
      <td class="${signedClass(row.net_change)}">${gasSignedBcf(row.net_change)}</td>
      <td class="${signedClass(row.year_ago_pct)}">${pct(row.year_ago_pct)}</td>
      <td class="${signedClass(row.five_year_pct)}">${pct(row.five_year_pct)}</td>
    </tr>`;
  }).join('')
    || '<tr><td colspan="6" class="muted">EIA storage report not available — the next Thursday release will populate this table.</td></tr>';

  const foot = document.getElementById('gasFootnote');
  if (foot) {
    foot.textContent = gas.week_ending_label
      ? `Source: US Energy Information Administration, Weekly Natural Gas Storage Report. `
        + `Salt and Nonsalt are sub-regions of South Central and are already counted in its total. `
        + `Figures for week ending ${gas.week_ending_label}.`
      : 'Source: US Energy Information Administration, Weekly Natural Gas Storage Report.';
  }

  drawGasChart();
  drawGasRegionChart();
}

function drawGasChart() {
  const mode = document.getElementById('gasChartMode')?.value || 'seasonal';
  const gas = gasData();

  if (mode === 'seasonal') {
    const s = gas.seasonal || {};
    // The band is drawn as a min series plus a stacked-looking max fill, so the
    // 5-year envelope reads as shaded area rather than two stray lines.
    mountChart('gasChart', {
      type: 'line',
      data: {
        labels: s.labels || [],
        datasets: [
          { label: '5-yr max', data: s.max || [], borderColor: 'rgba(148,163,184,.35)', borderWidth: 1,
            pointRadius: 0, fill: '+1', backgroundColor: 'rgba(148,163,184,.14)' },
          { label: '5-yr min', data: s.min || [], borderColor: 'rgba(148,163,184,.35)', borderWidth: 1,
            pointRadius: 0, fill: false },
          { label: s.average_label || '5-yr average', data: s.average || [], borderColor: C.flat,
            borderWidth: 2, borderDash: [6, 4], pointRadius: 0, fill: false, tension: .25 },
          { label: String(s.year_ago_year || 'Last year'), data: s.year_ago || [], borderColor: C.brand2,
            borderWidth: 1.6, pointRadius: 0, fill: false, tension: .25 },
          { label: String(s.current_year || 'This year'), data: s.current || [], borderColor: C.up,
            borderWidth: 3, pointRadius: 0, fill: false, tension: .25, spanGaps: false },
        ]
      },
      options: gasChartOptions('Working gas in storage by week of year (Bcf)', 'Bcf'),
      plugins: [emptyMessagePlugin('Seasonal comparison needs the EIA history workbook.')]
    });
    return;
  }

  const history = gas.history || [];
  if (mode === 'netchange') {
    const values = history.map(r => r.net_change);
    mountChart('gasChart', {
      type: 'bar',
      data: {
        labels: history.map(r => String(r.week_ending || '')),
        datasets: [{
          label: 'Weekly net change (Bcf)',
          data: values,
          backgroundColor: values.map(barFill),
          borderColor: values.map(barEdge),
          borderWidth: 1,
          maxBarThickness: 8
        }]
      },
      options: gasChartOptions('Weekly net change — builds above zero, draws below (Bcf)', 'Bcf'),
      plugins: [emptyMessagePlugin('Net change history needs the EIA history workbook.')]
    });
    return;
  }

  mountChart('gasChart', {
    type: 'line',
    data: {
      labels: history.map(r => String(r.week_ending || '')),
      datasets: [{
        label: 'Working gas, Lower 48 (Bcf)',
        data: history.map(r => r.total),
        borderColor: C.brand,
        backgroundColor: 'rgba(37,99,235,.12)',
        borderWidth: 2.2,
        pointRadius: 0,
        fill: true,
        tension: .25
      }]
    },
    options: gasChartOptions('Working gas in underground storage, Lower 48 (Bcf)', 'Bcf'),
    plugins: [emptyMessagePlugin('Storage history needs the EIA history workbook.')]
  });
}

function gasChartOptions(title, unit) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    scales: {
      x: { grid: { display: false }, border: { display: false },
        ticks: { autoSkip: true, maxTicksLimit: 14, maxRotation: 0, font: { size: 11 } } },
      y: { grid: { color: C.grid, drawBorder: false }, border: { display: false },
        ticks: { callback: v => fmt.format(v) } }
    },
    plugins: {
      legend: { display: true, position: 'bottom', labels: { usePointStyle: true, boxWidth: 8, padding: 14, font: { size: 11 } } },
      title: { display: true, text: title, align: 'start', font: { size: 13, weight: '700' }, color: '#94a3b8', padding: { bottom: 10 } },
      tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${fmt.format(ctx.parsed.y)} ${unit}` } }
    }
  };
}

function drawGasRegionChart() {
  const rows = gasRegions().filter(r => !r.is_total && r.five_year_pct !== null && r.five_year_pct !== undefined);
  drawBarChart('gasRegionChart', rows.map(r => ({
    name: r.name,
    change_pct: r.five_year_pct,
    close: r.stocks,
    change: r.net_change,
    status: Number(r.five_year_pct) > 0 ? 'Surplus to 5-yr average' : 'Deficit to 5-yr average'
  })), 'name', 'change_pct', 'Regional stocks vs 5-year average (%)');
}

function downloadGasCsv() {
  const gas = gasData();
  const cols = ['name', 'stocks', 'prior_stocks', 'net_change', 'implied_flow',
    'year_ago_stocks', 'year_ago_pct', 'five_year_stocks', 'five_year_pct'];
  const lines = [cols.join(',')].concat((gas.regions || []).map(r => cols.map(c => {
    const v = r[c];
    const text = v === null || v === undefined ? '' : String(v);
    return /[",\\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  }).join(',')));
  downloadText(`eia_natural_gas_storage_${gas.week_ending || 'latest'}.csv`, lines.join('\\n'));
}

// Pulls the side-car written by the Thursday-evening workflow. Any failure is
// silent by design: the embedded payload is already rendered and is valid, just
// possibly a few hours behind.
function refreshNaturalGasSidecar() {
  if (!window.fetch || location.protocol === 'file:') return;
  fetch('data/natural_gas.json', { cache: 'no-store' })
    .then(res => (res.ok ? res.json() : null))
    .then(data => {
      if (!data || !data.week_ending) return;
      const current = APP.data.natural_gas || {};
      // Only take over when the side-car is genuinely a newer week.
      if (current.week_ending && data.week_ending <= current.week_ending) return;
      GAS_OVERRIDE = data;
      renderNaturalGas();
    })
    .catch(() => {});
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
        <path d="M20 100 A80 80 0 0 1 180 100" fill="none" stroke="rgba(148,163,184,.25)" stroke-width="16" stroke-linecap="round"/>
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
  document.querySelectorAll('.reveal').forEach(el => requestAnimationFrame(() => el.classList.add('in')));
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

/* ================= Cockpit decision-layer renderers ================= */
function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
function sum(arr) { return arr.reduce((a, b) => a + (Number(b) || 0), 0); }
function arrow(v) {
  const n = Number(v || 0);
  if (n > 0.02) return { s: '▲', cls: 'good' };
  if (n < -0.02) return { s: '▼', cls: 'bad' };
  return { s: '▬', cls: 'neutral' };
}
function morningScore() {
  const s = clamp(Number(APP.score.score || 0), -10, 10);
  return Math.round((s + 10) / 20 * 100);
}
function bullishProb() {
  const s = Number(APP.score.score || 0);
  return clamp(Math.round(50 + s * 4.5), 3, 97);
}
function volatilityInfo() {
  const vix = (APP.data.nse_indices || {}).india_vix || {};
  const v = Number(vix.last);
  if (!Number.isFinite(v)) return { label: 'N/A', tone: 'neutral', sub: 'India VIX unavailable' };
  if (v < 13) return { label: 'Low', tone: 'good', sub: 'Calm — trend trades favoured' };
  if (v < 16) return { label: 'Medium', tone: 'neutral', sub: 'Normal intraday range' };
  if (v < 20) return { label: 'Elevated', tone: 'bad', sub: 'Wider swings likely' };
  return { label: 'High', tone: 'bad', sub: 'Risk-off, size down' };
}

function renderHeroStats() {
  const el = document.getElementById('heroStats');
  if (!el) return;
  const bias = APP.score.bias || 'Neutral';
  const bt = biasTone(bias);
  const vol = volatilityInfo();
  const prob = bullishProb();
  const tiles = [
    { label: 'Morning Score', value: morningScore() + '<span style="font-size:16px;color:var(--muted)">/100</span>', sub: 'Composite signal strength', cls: 'st-brand' },
    { label: 'Bullish Probability', value: prob + '%', sub: prob >= 55 ? 'Odds favour upside' : prob <= 45 ? 'Odds favour downside' : 'Balanced setup', cls: prob >= 55 ? 'st-good' : prob <= 45 ? 'st-bad' : 'st-neutral' },
    { label: 'Volatility', value: vol.label, sub: vol.sub, cls: 'st-' + vol.tone },
    { label: 'Market Sentiment', value: escapeHtml(bias), sub: (APP.score.confidence || '') + ' confidence', cls: 'st-' + bt.tone },
    { label: 'Confidence', value: escapeHtml(APP.score.confidence || 'N/A'), sub: 'Signal agreement', cls: 'st-brand' },
  ];
  el.innerHTML = tiles.map(t => `
    <div class="stat-tile ${t.cls}">
      <div class="st-label">${t.label}</div>
      <div class="st-value">${t.value}</div>
      <div class="st-sub">${t.sub}</div>
    </div>`).join('');
}

function regionAvg(region) {
  const rows = (APP.data.global_markets || []).filter(r => r.region === region && r.change_pct !== null && r.change_pct !== undefined);
  if (!rows.length) return null;
  return sum(rows.map(r => r.change_pct)) / rows.length;
}
function findAsset(list, name) { return (list || []).find(r => r.name === name) || {}; }

function renderAiSummary() {
  const el = document.getElementById('aiSummary');
  if (!el) return;
  const nse = APP.data.nse_indices || {};
  const sectors = nse.sectors || [];
  const flow = APP.data.fii_dii || {};
  const nifty = (APP.data.option_chains || {}).NIFTY || {};
  const vix = nse.india_vix || {};
  const bias = APP.score.bias || 'Neutral';
  const bt = biasTone(bias);
  const bullets = [];
  bullets.push({ tone: bt.color, text: `Market bias is <b>${escapeHtml(bias)}</b> (${escapeHtml(APP.score.confidence || 'N/A')} confidence, score ${morningScore()}/100).` });
  const us = regionAvg('US'), asia = regionAvg('Asia');
  if (us !== null) bullets.push({ tone: us >= 0 ? '#22C55E' : '#EF4444', text: `US markets closed ${us >= 0 ? 'higher' : 'lower'} (${pct(us)} avg) — ${us >= 0 ? 'supportive' : 'a drag'} for the open.` });
  if (asia !== null) bullets.push({ tone: asia >= 0 ? '#22C55E' : '#EF4444', text: `Asian peers are ${asia >= 0 ? 'green' : 'red'} (${pct(asia)} avg) this morning.` });
  const sorted = [...sectors].sort((a, b) => Number(b.change_pct || 0) - Number(a.change_pct || 0));
  if (sorted.length) {
    const top = sorted[0];
    bullets.push({ tone: '#22C55E', text: `<b>${escapeHtml(top.name)}</b> leads sectors (${pct(top.change_pct)}); watch for follow-through.` });
  }
  const combined = Number(flow.fii_net || 0) + Number(flow.dii_net || 0);
  bullets.push({ tone: combined >= 0 ? '#22C55E' : '#EF4444', text: `Institutional flow is net ${combined >= 0 ? 'positive' : 'negative'} (FII ${money(flow.fii_net)}, DII ${money(flow.dii_net)}).` });
  const pcrv = Number(nifty.pcr);
  if (Number.isFinite(pcrv)) bullets.push({ tone: '#2563EB', text: `Nifty PCR at <b>${num(nifty.pcr)}</b> — ${pcrv < 0.8 ? 'cautious/oversold' : pcrv > 1.1 ? 'complacent/overbought' : 'balanced'}; support ${num(nifty.support)}, resistance ${num(nifty.resistance)}.` });
  const news = (APP.data.market_news || [])[0];
  if (news && news.title) bullets.push({ tone: '#F59E0B', text: `Top headline: ${escapeHtml(news.title)}` });
  el.innerHTML = bullets.slice(0, 5).map(b => `
    <li><span class="dot" style="background:${b.tone}"></span><span>${b.text}</span></li>`).join('');
}

const CHECKLIST_ITEMS = ['Global Markets', 'India VIX', 'FII / DII', 'Option Chain', 'PCR', 'Support / Resistance', 'Major News', 'Sector Performance'];
function checklistKey() { return 'mmb_check_' + (APP.date || 'today'); }
function loadChecklist() { try { return new Set(JSON.parse(localStorage.getItem(checklistKey()) || '[]')); } catch (e) { return new Set(); } }
function saveChecklist(set) { try { localStorage.setItem(checklistKey(), JSON.stringify([...set])); } catch (e) {} }
function updateChecklistProgress(set) {
  const pct = Math.round(set.size / CHECKLIST_ITEMS.length * 100);
  const bar = document.getElementById('checklistProgress');
  const lbl = document.getElementById('checklistPct');
  if (bar) bar.style.width = pct + '%';
  if (lbl) lbl.textContent = pct + '% Complete';
}
function renderChecklist() {
  const el = document.getElementById('checklist');
  if (!el) return;
  const done = loadChecklist();
  el.innerHTML = CHECKLIST_ITEMS.map(name => `
    <div class="check-item ${done.has(name) ? 'done' : ''}" role="checkbox" tabindex="0" aria-checked="${done.has(name)}" data-item="${escapeHtml(name)}">
      <span class="check-box">${done.has(name) ? '✓' : ''}</span>
      <span class="check-label">${escapeHtml(name)}</span>
    </div>`).join('');
  updateChecklistProgress(done);
  const toggle = node => {
    const set = loadChecklist();
    const name = node.dataset.item;
    if (set.has(name)) set.delete(name); else set.add(name);
    saveChecklist(set);
    node.classList.toggle('done', set.has(name));
    node.setAttribute('aria-checked', set.has(name));
    node.querySelector('.check-box').textContent = set.has(name) ? '✓' : '';
    updateChecklistProgress(set);
  };
  el.querySelectorAll('.check-item').forEach(node => {
    node.addEventListener('click', () => toggle(node));
    node.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(node); } });
  });
}

function renderAlerts() {
  const el = document.getElementById('alertsPanel');
  if (!el) return;
  const nse = APP.data.nse_indices || {};
  const vix = nse.india_vix || {};
  const flow = APP.data.fii_dii || {};
  const nifty = (APP.data.option_chains || {}).NIFTY || {};
  const crude = findAsset(APP.data.commodities, 'Crude Oil WTI').close ? findAsset(APP.data.commodities, 'Crude Oil WTI') : findAsset(APP.data.commodities, 'Brent Oil');
  const dxy = findAsset(APP.data.currencies, 'DXY');
  const alerts = [];
  const vixLast = Number(vix.last), vixChg = Number(vix.change_pct);
  if (Number.isFinite(vixLast) && vixLast >= 18) alerts.push({ cls: 'bad', ic: '⚠️', text: `<b>India VIX ${num(vix.last)}</b> — elevated volatility, trade smaller size.` });
  else if (Number.isFinite(vixChg) && vixChg >= 5) alerts.push({ cls: 'warn', ic: '⚠️', text: `<b>India VIX rising ${pct(vix.change_pct)}</b> — expect wider swings.` });
  const pcrv = Number(nifty.pcr);
  if (Number.isFinite(pcrv) && pcrv < 0.7) alerts.push({ cls: 'warn', ic: '📉', text: `<b>Nifty PCR ${num(nifty.pcr)}</b> — below 0.70, caution / possible oversold bounce.` });
  else if (Number.isFinite(pcrv) && pcrv > 1.3) alerts.push({ cls: 'warn', ic: '📈', text: `<b>Nifty PCR ${num(nifty.pcr)}</b> — above 1.30, market may be complacent.` });
  if (Number(flow.fii_net || 0) < -1000) alerts.push({ cls: 'bad', ic: '🏦', text: `<b>Heavy FII selling</b> (${money(flow.fii_net)}) — bearish pressure on index.` });
  if (crude && Number(crude.close) >= 90) alerts.push({ cls: 'warn', ic: '🛢️', text: `<b>Crude above $90</b> (${num(crude.close)}) — inflation / OMC pressure.` });
  else if (crude && Number(crude.change_pct) >= 3) alerts.push({ cls: 'warn', ic: '🛢️', text: `<b>Crude spiking ${pct(crude.change_pct)}</b> — watch energy-sensitive names.` });
  if (dxy && Number(dxy.change_pct) >= 0.5) alerts.push({ cls: 'warn', ic: '💵', text: `<b>Dollar strengthening ${pct(dxy.change_pct)}</b> — pressure on EM equities.` });
  const us = regionAvg('US');
  if (us !== null && us <= -1) alerts.push({ cls: 'bad', ic: '🌎', text: `<b>US markets fell</b> (${pct(us)} avg) — cautious global cue.` });
  if (!alerts.length) alerts.push({ cls: 'good', ic: '✅', text: 'No major alerts — calm pre-market setup.' });
  el.innerHTML = alerts.map(a => `<div class="alert ${a.cls}"><span class="ic">${a.ic}</span><span>${a.text}</span></div>`).join('');
}

function renderLevels() {
  const el = document.getElementById('levelsGrid');
  if (!el) return;
  const chains = APP.data.option_chains || {};
  const items = ['NIFTY', 'BANKNIFTY'].map(k => chains[k] || { symbol: k });
  const distTxt = (spot, lvl) => {
    const s = Number(spot), l = Number(lvl);
    if (!Number.isFinite(s) || !Number.isFinite(l) || s === 0) return '';
    return (Math.abs((l - s) / s) * 100).toFixed(2) + '% away';
  };
  el.innerHTML = items.map(it => `
    <div class="level-card">
      <h3><span>${escapeHtml(it.symbol || '')}</span><span class="spot">Spot ${num(it.underlying)}</span></h3>
      <div class="level-row">
        <div class="level-box sup"><div class="lk">Support</div><div class="lv">${num(it.support)}</div><div class="st-sub">${distTxt(it.underlying, it.support)}</div></div>
        <div class="level-box res"><div class="lk">Resistance</div><div class="lv">${num(it.resistance)}</div><div class="st-sub">${distTxt(it.underlying, it.resistance)}</div></div>
      </div>
      <div class="level-meta"><span>PCR ${num(it.pcr)}</span><span>Expiry ${escapeHtml(it.expiry || 'N/A')}</span></div>
    </div>`).join('') || '<p class="muted">No option-chain levels available.</p>';
}

function indCard(name, value, changePct, interp, interpCls) {
  const a = arrow(changePct);
  return `
    <div class="ind-card">
      <div class="ind-top"><span class="ind-name">${escapeHtml(name)}</span><span class="ind-arrow ind-interp ${a.cls}">${a.s}</span></div>
      <div class="ind-value">${value}</div>
      <div class="ind-interp ${interpCls}">${escapeHtml(interp)}</div>
    </div>`;
}
function renderIndicators() {
  const el = document.getElementById('indicatorGrid');
  if (!el) return;
  const nse = APP.data.nse_indices || {};
  const sectors = nse.sectors || [];
  const vix = nse.india_vix || {};
  const nifty = (APP.data.option_chains || {}).NIFTY || {};
  const bank = (APP.data.option_chains || {}).BANKNIFTY || {};
  const dxy = findAsset(APP.data.currencies, 'DXY');
  const crude = findAsset(APP.data.commodities, 'Crude Oil WTI');
  const gold = findAsset(APP.data.commodities, 'Gold');
  const btc = findAsset(APP.data.crypto, 'Bitcoin');
  const up = sectors.filter(s => Number(s.change_pct || 0) > 0).length;
  const down = sectors.filter(s => Number(s.change_pct || 0) < 0).length;
  const breadth = (up + down) ? Math.round(up / (up + down) * 100) : 0;
  const vol = volatilityInfo();
  const pcrInterp = v => { const n = Number(v); if (!Number.isFinite(n)) return ['N/A', 'neutral']; if (n < 0.8) return ['Bearish / oversold', 'bad']; if (n > 1.1) return ['Bullish / toppy', 'good']; return ['Neutral', 'neutral']; };
  const nP = pcrInterp(nifty.pcr), bP = pcrInterp(bank.pcr);
  const cards = [
    indCard('India VIX', num(vix.last), vix.change_pct, vol.label + ' volatility', vol.tone),
    indCard('Nifty PCR', num(nifty.pcr), (Number(nifty.pcr) - 1), nP[0], nP[1]),
    indCard('Bank Nifty PCR', num(bank.pcr), (Number(bank.pcr) - 1), bP[0], bP[1]),
    indCard('Advance / Decline', up + ' : ' + down, (up - down), up >= down ? 'More sectors advancing' : 'More sectors declining', up >= down ? 'good' : 'bad'),
    indCard('Market Breadth', breadth + '%', (breadth - 50), breadth >= 55 ? 'Broad participation' : breadth <= 45 ? 'Weak participation' : 'Mixed breadth', breadth >= 55 ? 'good' : breadth <= 45 ? 'bad' : 'neutral'),
    indCard('Dollar Index', num(dxy.close), dxy.change_pct, Number(dxy.change_pct || 0) > 0 ? 'Stronger USD — EM headwind' : 'Softer USD — EM tailwind', Number(dxy.change_pct || 0) > 0 ? 'bad' : 'good'),
    indCard('Crude Oil', num(crude.close), crude.change_pct, Number(crude.change_pct || 0) > 0 ? 'Rising — inflation watch' : 'Easing — supportive', Number(crude.change_pct || 0) > 0 ? 'bad' : 'good'),
    indCard('Gold', num(gold.close), gold.change_pct, Number(gold.change_pct || 0) > 0 ? 'Bid — some risk-off' : 'Soft — risk-on', Number(gold.change_pct || 0) > 0 ? 'neutral' : 'good'),
    indCard('Bitcoin', num(btc.close), btc.change_pct, Number(btc.change_pct || 0) >= 0 ? 'Risk appetite healthy' : 'Risk appetite fading', Number(btc.change_pct || 0) >= 0 ? 'good' : 'bad'),
  ];
  el.innerHTML = cards.join('');
}

function shortDate(iso) {
  if (!iso) return '';
  const p = String(iso).split('-');
  if (p.length < 3) return iso;
  const m = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return p[2] + ' ' + (m[parseInt(p[1], 10) - 1] || '');
}
function renderFlow() {
  const el = document.getElementById('flowCards');
  if (!el) return;
  const flow = APP.data.fii_dii || {};
  const hist = (APP.history || []).filter(h => h.date);
  const lastN = (key, n) => hist.slice(-n).map(h => h[key]);
  const dataDate = hist.length ? hist[hist.length - 1].date : null;
  const prevDate = hist.length >= 2 ? hist[hist.length - 2].date : null;
  const yFii = hist.length >= 2 ? hist[hist.length - 2].fii_net : null;
  const yDii = hist.length >= 2 ? hist[hist.length - 2].dii_net : null;
  const dLbl = dataDate ? shortDate(dataDate) : 'last close';
  const pLbl = prevDate ? shortDate(prevDate) : '—';
  const toneVal = v => `<b class="${Number(v || 0) >= 0 ? 'ind-interp good' : 'ind-interp bad'}">${money(v)}</b>`;
  const card = (title, today, yest, key) => `
    <div class="flow-card">
      <div class="fh"><span>${title}</span><span class="muted small">${dLbl}</span></div>
      <div class="flow-row"><span>Net (last session)</span>${toneVal(today)}</div>
      <div class="flow-row"><span>Prior (${pLbl})</span>${toneVal(yest)}</div>
      <div class="flow-row"><span>5-session net</span>${toneVal(sum(lastN(key, 5)))}</div>
      <div class="flow-row"><span>22-session net</span>${toneVal(sum(lastN(key, 22)))}</div>
    </div>`;
  const combinedToday = Number(flow.fii_net || 0) + Number(flow.dii_net || 0);
  el.innerHTML =
    card('FII / FPI', flow.fii_net, yFii, 'fii_net') +
    card('DII', flow.dii_net, yDii, 'dii_net') +
    `<div class="flow-card">
      <div class="fh"><span>Combined</span><span class="muted small">${dLbl}</span></div>
      <div class="flow-row"><span>Net (FII + DII)</span>${toneVal(combinedToday)}</div>
      <div class="flow-row"><span>Read</span><b>${combinedToday >= 0 ? 'Net buying' : 'Net selling'}</b></div>
      <div class="flow-row"><span>Bias impact</span><b class="${combinedToday >= 0 ? 'ind-interp good' : 'ind-interp bad'}">${combinedToday >= 0 ? 'Supportive' : 'Bearish'}</b></div>
      <div class="flow-row"><span>Source</span><span class="muted small">${escapeHtml((flow.source || 'N/A')).toUpperCase()} · provisional</span></div>
    </div>`;
}

function renderTimeline() {
  const el = document.getElementById('marketTimeline');
  if (!el) return;
  const nse = APP.data.nse_indices || {};
  const us = regionAvg('US'), asia = regionAvg('Asia'), eu = regionAvg('Europe');
  const gift = nse.gift_nifty;
  const bias = APP.score.bias || 'Neutral';
  const bt = biasTone(bias);
  const steps = [
    { t: 'Yesterday Close', v: num(nse.nifty_spot), s: 'Nifty spot' },
    { t: 'US Market', v: us === null ? 'N/A' : pct(us), s: us === null ? 'no data' : (us >= 0 ? 'positive cue' : 'negative cue') },
    { t: 'Europe', v: eu === null ? 'N/A' : pct(eu), s: eu === null ? 'no data' : (eu >= 0 ? 'positive' : 'negative') },
    { t: 'Asian Market', v: asia === null ? 'N/A' : pct(asia), s: asia === null ? 'no data' : (asia >= 0 ? 'positive' : 'negative') },
    { t: 'Gift Nifty', v: gift === null || gift === undefined ? 'N/A' : num(gift), s: 'gap indicator' },
    { t: 'Opening Prediction', v: escapeHtml(bias), s: (APP.score.confidence || '') + ' confidence', pred: true },
  ];
  el.innerHTML = steps.map((st, i) => `
    <div class="tl-step ${st.pred ? 'pred' : ''}"${st.pred ? ` style="border-color:${bt.color}"` : ''}>
      <div class="tl-t">${st.t}</div>
      <div class="tl-v"${st.pred ? ` style="color:${bt.color}"` : ''}>${st.v}</div>
      <div class="tl-s">${st.s}</div>
    </div>${i < steps.length - 1 ? '<div class="tl-arrow">→</div>' : ''}`).join('');
}

/* ================= Nav: clock, theme, refresh, search, shortcuts ================= */
function activateTab(name) {
  const btn = document.querySelector(`.tab-btn[data-tab="${name}"]`);
  if (!btn) return;
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  const panel = document.getElementById(name);
  if (panel) { panel.classList.add('active'); panel.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
  setTimeout(renderAll, 20);
}
function startClock() {
  const el = document.getElementById('navClock');
  if (!el) return;
  const tick = () => { el.textContent = new Date().toLocaleTimeString('en-IN', { hour12: false }); };
  tick();
  setInterval(tick, 1000);
}
function applyTheme(theme) {
  const root = document.documentElement;
  if (theme === 'light') root.setAttribute('data-theme', 'light');
  else root.removeAttribute('data-theme');
  const btn = document.getElementById('themeToggle');
  if (btn) btn.textContent = theme === 'light' ? '☀️' : '🌙';
}
(function initTheme() {
  let saved = 'dark';
  try { saved = localStorage.getItem('mmb_theme') || 'dark'; } catch (e) {}
  applyTheme(saved);
})();
function toggleTheme() {
  const isLight = document.documentElement.getAttribute('data-theme') === 'light';
  const next = isLight ? 'dark' : 'light';
  applyTheme(next);
  try { localStorage.setItem('mmb_theme', next); } catch (e) {}
  setTimeout(renderAll, 30);
}
const SEARCH_MAP = [
  { k: ['global', 'us', 'europe', 'asia', 'dow', 'nasdaq'], tab: 'global' },
  { k: ['commodit', 'gold', 'crude', 'oil', 'silver', 'copper', 'gas'], tab: 'commodities' },
  { k: ['crypto', 'bitcoin', 'btc', 'ether', 'eth', 'solana'], tab: 'crypto' },
  { k: ['currency', 'dxy', 'dollar', 'usd', 'inr', 'eur', 'jpy'], tab: 'currency' },
  { k: ['sector', 'bank', 'it', 'auto', 'pharma', 'fmcg', 'metal'], tab: 'sectors' },
  { k: ['pivot', 'nifty 50', 'nifty50', 'stock', 'constituent', 'reliance', 'tcs', 'infy', 'hdfc'], tab: 'nifty50' },
  { k: ['technical', 'moving average', 'dma', 'sma', 'ema', 'rsi', 'macd', 'bollinger', 'indicator'], tab: 'technicals' },
  { k: ['signal', 'score', 'bias'], tab: 'signals' },
  { k: ['history', 'pcr', 'trend'], tab: 'history' },
  { k: ['news', 'headline'], tab: 'news' },
  { k: ['event', 'calendar', 'board meeting', 'result', 'earning', 'dividend', 'buyback', 'bonus', 'split'], tab: 'events' },
  { k: ['report', 'markdown', 'summary'], tab: 'report' },
];
function runSearch(q) {
  const s = String(q || '').trim().toLowerCase();
  if (!s) return;
  const hit = SEARCH_MAP.find(m => m.k.some(w => s.includes(w)));
  if (hit) {
    activateTab(hit.tab);
    if (hit.tab === 'sectors') { const box = document.getElementById('sectorSearch'); if (box) { box.value = q; renderSectors(); } }
    if (hit.tab === 'news') { const box = document.getElementById('newsSearch'); if (box) { box.value = q; renderNews(); } }
    if (hit.tab === 'events') { const box = document.getElementById('eventSearch'); if (box) { box.value = q; renderEventCalendar(); } }
  }
}
(function initNav() {
  startClock();
  document.getElementById('themeToggle')?.addEventListener('click', toggleTheme);
  document.getElementById('refreshBtn')?.addEventListener('click', () => location.reload());
  const search = document.getElementById('globalSearch');
  if (search) search.addEventListener('keydown', e => { if (e.key === 'Enter') runSearch(search.value); });
  document.addEventListener('keydown', e => {
    const typing = /^(input|select|textarea)$/i.test(e.target.tagName);
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); search?.focus(); return; }
    if (e.key === 'Escape') { if (search) { search.value = ''; search.blur(); } return; }
    if (typing) return;
    const k = e.key.toLowerCase();
    if (k === 'r') { e.preventDefault(); location.reload(); }
    else if (k === 'n') activateTab('news');
    else if (k === 's') activateTab('sectors');
    else if (k === 'm') activateTab('overview');
    else if (k === 't') toggleTheme();
  });
})();

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
['nifty50Search','nifty50Sector','nifty50Sort','nifty50View','nifty50Zone'].forEach(id =>
  document.getElementById(id)?.addEventListener(id === 'nifty50Search' ? 'input' : 'change', renderNifty50));
document.getElementById('nifty50Csv')?.addEventListener('click', downloadNifty50Csv);
document.getElementById('eventSearch')?.addEventListener('input', renderEventCalendar);
document.getElementById('eventCategory')?.addEventListener('change', renderEventCalendar);
document.getElementById('eventScope')?.addEventListener('change', renderEventCalendar);
document.getElementById('eventCsv')?.addEventListener('click', downloadEventCsv);
['gasChartMode','gasRegionScope'].forEach(id =>
  document.getElementById(id)?.addEventListener('change', renderNaturalGas));
document.getElementById('gasCsv')?.addEventListener('click', downloadGasCsv);
['technicalIndex','technicalMaOverlay'].forEach(id => document.getElementById(id)?.addEventListener('change', renderTechnicals));
document.getElementById('signalStatusFilter').addEventListener('change', renderSignals);
document.getElementById('pcrWindow')?.addEventListener('change', renderPcrRolling);
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
function speechMarkdown() {
  // The Nifty 50 pivot table (~50 rows of levels) and the event calendar (dozens
  // of company filings) are listenable as headlines, not as read-outs, so their
  // table bodies are dropped from the spoken report while the summary stays.
  const HEAVY_TABLES = ['Nifty 50 Pivot Table', 'Corporate Event Calendar'];
  let inHeavySection = false;
  return String(APP.markdown || '').split('\\n').filter(line => {
    if (line.startsWith('## ')) inHeavySection = HEAVY_TABLES.some(t => line.includes(t));
    return !(inHeavySection && line.trim().startsWith('|'));
  }).join('\\n');
}
function getSpeechText() {
  const mode = document.getElementById('ttsMode').value;
  if (mode === 'full') return stripMarkdown(speechMarkdown());
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
refreshNaturalGasSidecar();
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


def _bcf_text(value: Any) -> str:
    """Storage volumes are reported as whole Bcf, so no decimals are shown."""
    if value is None:
        return "N/A"
    return f"{float(value):,.0f}"


def _natural_gas_markdown(gas: dict[str, Any]) -> list[str]:
    """EIA weekly natural gas storage section.

    Weekly rather than daily, so the heading always names the week the numbers
    cover — otherwise a Monday reader would assume Friday's data.
    """
    heading = "## US Natural Gas Storage (EIA Weekly)"
    if not gas or not gas.get("regions"):
        return [heading, "", "EIA storage report not available in this run.", ""]

    total = gas.get("total") or {}
    signal = gas.get("signal") or {}
    lines = [heading, ""]

    week = gas.get("week_ending_label") or "the latest week"
    released = gas.get("released_label")
    lines.append(f"- **Week Ending:** {week}" + (f" (released {released})" if released else ""))
    lines.append(f"- **Working Gas, Lower 48:** {_bcf_text(total.get('stocks'))} Bcf")

    change = total.get("net_change")
    if change is not None:
        word = "build" if change >= 0 else "draw"
        lines.append(f"- **Weekly Net Change:** {_bcf_text(abs(change))} Bcf {word}")

    vs_norm = gas.get("change_vs_norm")
    if vs_norm is not None:
        lines.append(
            f"- **vs 5-Year Norm for This Week:** {_bcf_text(abs(vs_norm))} Bcf "
            f"{'larger' if vs_norm > 0 else 'smaller'} than average"
        )

    lines.append(f"- **vs Year Ago:** {pct_text(total.get('year_ago_pct'))}")
    lines.append(f"- **vs 5-Year Average:** {pct_text(total.get('five_year_pct'))}")
    if gas.get("season"):
        lines.append(f"- **Season:** {gas['season']} season")
    if signal.get("label"):
        lines.append(f"- **Read:** {signal['label']} — {signal.get('note', '')}")
    if gas.get("next_release_ist_label"):
        lines.append(f"- **Next Release:** {gas['next_release_ist_label']}")
    if gas.get("from_cache"):
        lines.append("- **Note:** live EIA fetch failed this run; showing the last cached release.")

    lines.append("")
    lines.append("| Region | Stocks (Bcf) | Net Change | vs Year Ago | vs 5-Yr Avg |")
    lines.append("| --- | --- | --- | --- | --- |")
    for row in gas.get("regions", []):
        # Salt / Nonsalt are splits of South Central, indented so the table does
        # not read as if they were separate regions being double-counted.
        name = f"— {row.get('name')}" if row.get("is_subregion") else str(row.get("name"))
        lines.append(
            f"| {name} | {_bcf_text(row.get('stocks'))} | "
            f"{_bcf_text(row.get('net_change'))} | "
            f"{pct_text(row.get('year_ago_pct'))} | {pct_text(row.get('five_year_pct'))} |"
        )
    lines.append("")
    return lines


def _event_calendar_markdown(calendar: dict[str, Any]) -> list[str]:
    """Corporate event section, scoped to the single date that was fetched."""
    if not calendar:
        return ["## Corporate Event Calendar", "", "Event calendar data not available in this run.", ""]

    label = calendar.get("date_label") or calendar.get("date") or "selected date"
    weekday = calendar.get("weekday")
    heading = f"## Corporate Event Calendar - {label}"
    if weekday:
        heading += f" ({weekday})"

    lines = [heading, ""]
    events = calendar.get("events", [])
    if not events:
        lines.append(f"No NSE board meetings or corporate actions are listed for {label}.")
        lines.append("")
        return lines

    total = calendar.get("total", len(events))
    breakdown = " · ".join(
        f"{row.get('name')} {row.get('count')}" for row in calendar.get("category_counts", [])
    )
    lines.append(f"- **Companies with announcements:** {total}")
    lines.append(f"- **Nifty 50 constituents:** {calendar.get('nifty50_count', 0)}")
    if breakdown:
        lines.append(f"- **Breakdown:** {breakdown}")
    lines.append("")

    lines.append("| Symbol | Company | Purpose | Details |")
    lines.append("|---|---|---|---|")
    for event in events[:EVENT_MARKDOWN_LIMIT]:
        symbol = event.get("symbol") or "-"
        if event.get("is_nifty50"):
            symbol = f"**{symbol}**"
        details = str(event.get("description") or "").replace("|", "/")
        if len(details) > 120:
            details = details[:120].rstrip() + "..."
        lines.append(
            f"| {symbol} | {event.get('company') or '-'} | "
            f"{str(event.get('purpose') or '-').replace('|', '/')} | {details} |"
        )
    lines.append("")
    if total > EVENT_MARKDOWN_LIMIT:
        lines.append(
            f"_Showing {EVENT_MARKDOWN_LIMIT} of {total} announcements "
            "(Nifty 50 names first). Full list is on the dashboard Events tab._"
        )
        lines.append("")
    return lines


def _index_technicals_markdown(technicals: dict[str, Any]) -> list[str]:
    lines = ["## Index Moving Averages & Indicators", ""]
    if not technicals:
        lines.append("Index technical data not available in this run.")
        return lines

    lines.append("| Index | Close | Daily % | Weekly % | Monthly % | 20 DMA | 50 DMA | 100 DMA | 200 DMA | Trend |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for snapshot in technicals.values():
        mas = {ma["period"]: ma for ma in snapshot.get("moving_averages", [])}
        lines.append(
            f"| {snapshot.get('label')} | {number_text(snapshot.get('close'))} | {pct_text(snapshot.get('change_pct'))} | "
            f"{pct_text(snapshot.get('week_pct'))} | {pct_text(snapshot.get('month_pct'))} | "
            + " | ".join(number_text(mas.get(period, {}).get("sma")) for period in (20, 50, 100, 200))
            + f" | {(snapshot.get('trend') or {}).get('label', 'N/A')} |"
        )
    lines.append("")

    for snapshot in technicals.values():
        lines.append(f"### {snapshot.get('label')} Indicators")
        lines.append("")
        for indicator in snapshot.get("indicators", []):
            lines.append(
                f"- **{indicator.get('name')}:** {number_text(indicator.get('value'))} "
                f"({indicator.get('status')}) — {indicator.get('note')}"
            )
        levels = snapshot.get("levels", {})
        lines.append(
            f"- **Pivot levels:** S2 {number_text(levels.get('s2'))} · S1 {number_text(levels.get('s1'))} · "
            f"PP {number_text(levels.get('pivot'))} · R1 {number_text(levels.get('r1'))} · R2 {number_text(levels.get('r2'))}"
        )
        lines.append("")
    return lines


def _nifty50_markdown(nifty50: dict[str, Any]) -> list[str]:
    lines = ["## Nifty 50 Pivot Table", ""]
    rows = nifty50.get("rows", [])
    if not rows:
        lines.append("Nifty 50 constituent data not available in this run.")
        return lines

    breadth = nifty50.get("breadth", {})
    lines.append(
        f"Breadth as of {nifty50.get('as_of', 'N/A')}: **{breadth.get('advancing', 0)} advancing / "
        f"{breadth.get('declining', 0)} declining**, {breadth.get('above_pivot', 0)} of {len(rows)} trading above their daily pivot. "
        f"Average change: {pct_text(breadth.get('avg_change_pct'))} daily, {pct_text(breadth.get('avg_week_pct'))} weekly, "
        f"{pct_text(breadth.get('avg_month_pct'))} monthly."
    )
    lines.append("")
    lines.append("| Stock | LTP | Daily % | Weekly % | Monthly % | S2 | S1 | Pivot | R1 | R2 | RSI | Zone |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for row in rows:
        lines.append(
            f"| {row.get('symbol')} | {number_text(row.get('close'))} | {pct_text(row.get('change_pct'))} | "
            f"{pct_text(row.get('week_pct'))} | {pct_text(row.get('month_pct'))} | {number_text(row.get('s2'))} | "
            f"{number_text(row.get('s1'))} | {number_text(row.get('pivot'))} | {number_text(row.get('r1'))} | "
            f"{number_text(row.get('r2'))} | {number_text(row.get('rsi'))} | {row.get('zone', 'N/A')} |"
        )
    lines.append("")
    lines.append("### Sector Roll-Up")
    lines.append("")
    lines.append("| Sector | Stocks | Daily % | Weekly % | Monthly % | Advancing |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for sector in nifty50.get("sectors", []):
        lines.append(
            f"| {sector.get('sector')} | {sector.get('count')} | {pct_text(sector.get('change_pct'))} | "
            f"{pct_text(sector.get('week_pct'))} | {pct_text(sector.get('month_pct'))} | "
            f"{sector.get('advancing')}/{sector.get('count')} |"
        )
    return lines


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
