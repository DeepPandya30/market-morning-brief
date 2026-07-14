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

    @media (max-width: 720px) {
      .navbar { flex-wrap: wrap; padding: 10px 16px; }
      .nav-search { order: 3; flex: 1 0 100%; }
      main { padding: 16px 14px 50px; }
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
    <button class="tab-btn" data-tab="crypto">Crypto</button>
    <button class="tab-btn" data-tab="currency">Currency</button>
    <button class="tab-btn" data-tab="sectors">Sectors</button>
    <button class="tab-btn" data-tab="signals">Signals</button>
    <button class="tab-btn" data-tab="history">History</button>
    <button class="tab-btn" data-tab="news">News</button>
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
  const brandSub = document.getElementById('generatedAt');
  if (brandSub) brandSub.textContent = APP.generated_at ? `Updated ${APP.generated_at}` : 'Pre-market cockpit';
  const navUpd = document.getElementById('navUpdated');
  if (navUpd) navUpd.textContent = APP.generated_at ? `Updated ${APP.generated_at}` : 'Updated —';
  const footUpd = document.getElementById('footerUpdated');
  if (footUpd) footUpd.textContent = APP.generated_at ? `Last update ${APP.generated_at}` : 'Last update —';
  document.getElementById('marketView').textContent = APP.market_view || '';
  document.getElementById('riskNote').textContent = APP.risk_note || '';
  document.getElementById('markdownReport').textContent = APP.markdown || '';
  renderOICards(); renderGlobal(); renderCommodities(); renderCrypto(); renderCurrency(); renderSectors(); renderSignals(); renderHistory(); renderWarnings();
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
  { k: ['signal', 'score', 'bias'], tab: 'signals' },
  { k: ['history', 'pcr', 'trend'], tab: 'history' },
  { k: ['news', 'headline'], tab: 'news' },
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
