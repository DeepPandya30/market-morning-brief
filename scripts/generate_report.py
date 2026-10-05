from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from market_brief.config import (
    DASHBOARD_DIR,
    DOCS_DIR,
    NG_STORAGE_SIDECAR_NAME,
    PETROLEUM_SIDECAR_NAME,
    PROCESSED_DIR,
    RAW_DIR,
    REPORTS_DIR,
)
from market_brief.fetchers import build_data_bundle
from market_brief.render import create_report_context, save_outputs
from market_brief.scoring import score_market
from market_brief.utils import dump_json, ensure_dirs, now_ist


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the morning market brief.")
    parser.add_argument(
        "--event-date",
        default=os.environ.get("MARKET_EVENT_DATE", ""),
        help=(
            "Single date to pull the NSE corporate event calendar for, e.g. "
            "2026-08-12, 12-08-2026 or '12 August'. Defaults to today (IST)."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_dirs(RAW_DIR, PROCESSED_DIR, REPORTS_DIR, DASHBOARD_DIR, DOCS_DIR, DOCS_DIR / "data")

    data = build_data_bundle(event_date=args.event_date or None)
    score = score_market(data)
    history = update_history(data, score, PROCESSED_DIR / "history.json")
    scored = next((row for row in reversed(history) if row.get("realized_date")), None)
    context = create_report_context(data, score, history=history)

    stamp = now_ist().strftime("%Y-%m-%d_%H-%M-%S")
    latest_summary = {"score": score, "data": data, "history": history}

    dump_json(RAW_DIR / f"market_data_{stamp}.json", data)
    dump_json(PROCESSED_DIR / "latest_summary.json", latest_summary)
    dump_json(DOCS_DIR / "data" / "latest_summary.json", latest_summary)
    dump_json(DOCS_DIR / "data" / "history.json", history)
    # Side-car so the Thursday-evening gas refresh can republish this one
    # section without regenerating the whole morning brief.
    natural_gas = data.get("natural_gas") or {}
    dump_json(DOCS_DIR / "data" / NG_STORAGE_SIDECAR_NAME, natural_gas)
    dump_json(DASHBOARD_DIR / "data" / NG_STORAGE_SIDECAR_NAME, natural_gas)
    # Same side-car arrangement for the Wednesday-evening crude oil refresh.
    petroleum = data.get("petroleum") or {}
    dump_json(DOCS_DIR / "data" / PETROLEUM_SIDECAR_NAME, petroleum)
    dump_json(DASHBOARD_DIR / "data" / PETROLEUM_SIDECAR_NAME, petroleum)

    save_outputs(
        context,
        REPORTS_DIR / "morning_report.md",
        DASHBOARD_DIR / "index.html",
        DOCS_DIR / "index.html",
    )

    print(f"Generated report with bias={score['bias']} score={score['score']} confidence={score['confidence']}")
    core = score.get("core_model") or {}
    print(
        f"Core 5-factor model: {core.get('bias')} ({core.get('score')} of {core.get('max_score')}), "
        f"{core.get('available')}/{core.get('total_factors')} factors with data"
    )
    for factor in core.get("factors", []):
        print(f"  - {factor['name']}: {factor['score']:+d} x{factor['weight']:g} = {factor['weighted']:+g} ({factor['rule']})")
    if scored:
        print(
            f"Scored previous call for {scored['realized_date']}: "
            f"NIFTY {scored['realized_change_pct']:+.2f}% ({scored['realized_direction']}) — "
            f"core {scored.get('core_bias')} {_hit_text(scored.get('core_hit'))}, "
            f"composite {scored.get('bias')} {_hit_text(scored.get('composite_hit'))}"
        )
    print(_hit_rate_text(history))
    calendar = data.get("event_calendar", {})
    print(
        f"Event calendar for {calendar.get('date_label')}: "
        f"{calendar.get('total', 0)} announcements ({calendar.get('nifty50_count', 0)} Nifty 50)"
    )
    crude = data.get("petroleum") or {}
    print(
        f"Crude oil week ending {crude.get('week_ending_label') or 'n/a'}: "
        f"commercial stocks {(crude.get('stats') or {}).get('crude_stocks')} MMbbl "
        f"({(crude.get('signal') or {}).get('label', 'no read')})"
    )
    gas = data.get("natural_gas") or {}
    print(
        f"Natural gas storage week ending {gas.get('week_ending_label') or 'n/a'}: "
        f"{(gas.get('total') or {}).get('stocks')} Bcf "
        f"({(gas.get('signal') or {}).get('label', 'no read')})"
    )
    if data.get("warnings"):
        print("Fetch warnings:")
        for warning in data["warnings"]:
            print(f"- {warning}")


def update_history(data: dict[str, Any], score: dict[str, Any], history_path: Path) -> list[dict[str, Any]]:
    history = load_json_list(history_path)
    entry = build_history_entry(data, score)
    existing_index = next((idx for idx, row in enumerate(history) if row.get("date") == entry["date"]), None)
    if existing_index is None:
        history.append(entry)
    else:
        history[existing_index] = entry
    history = history[-120:]
    backfill_realized(history, data, as_of=now_ist().date())
    dump_json(history_path, history)
    return history


def backfill_realized(
    history: list[dict[str, Any]],
    data: dict[str, Any],
    as_of: date | None = None,
) -> dict[str, Any] | None:
    """Score a past call against what the market actually did.

    The brief is generated pre-market for session D, so the NIFTY technicals in
    today's run — which close on the last completed session — are the realised
    outcome of the entry filed on that same date. Filling it in here is what
    makes the five-factor model measurable instead of merely plausible.

    Only sessions strictly before the run date are scored. On a re-run after the
    close, today's technicals are the same bars that fed today's factors, so
    scoring that row would record hindsight as a forecast.
    """
    nifty = (data.get("index_technicals") or {}).get("NIFTY 50") or {}
    session = nifty.get("date")
    change_pct = nifty.get("change_pct")
    if not session or change_pct is None:
        return None

    as_of = as_of or now_ist().date()
    session_date = _parse_iso(session)
    if session_date is None or session_date >= as_of:
        return None

    row = next((item for item in history if item.get("date") == session), None)
    if row is None:
        return None

    change_pct = float(change_pct)
    row["realized_date"] = session
    row["realized_change_pct"] = change_pct
    row["realized_gap_pct"] = nifty.get("gap_pct")
    row["realized_close"] = nifty.get("close")
    row["realized_direction"] = "Up" if change_pct > 0 else "Down" if change_pct < 0 else "Flat"
    row["core_hit"] = _bias_hit(row.get("core_bias"), change_pct)
    row["composite_hit"] = _bias_hit(row.get("bias"), change_pct)
    return row


def _parse_iso(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _bias_hit(bias: Any, realized_change_pct: float) -> bool | None:
    """Did a published bias call match the session? None when no call was made."""
    if not bias:
        return None
    label = str(bias).lower()
    if "bull" in label:
        predicted = 1
    elif "bear" in label:
        predicted = -1
    else:
        # Neutral / range-bound is not a directional call, so it is not scored.
        return None
    if realized_change_pct == 0:
        return None
    return predicted == (1 if realized_change_pct > 0 else -1)


def load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


def build_history_entry(data: dict[str, Any], score: dict[str, Any]) -> dict[str, Any]:
    nse = data.get("nse_indices", {})
    flow = data.get("fii_dii", {})
    chains = data.get("option_chains", {})
    nifty = chains.get("NIFTY", {})
    bank = chains.get("BANKNIFTY", {})
    sectors = nse.get("sectors", [])
    top_sector = sectors[0] if sectors else {}
    weak_sector = sectors[-1] if sectors else {}
    global_rows = data.get("global_markets", [])

    return {
        "date": now_ist().strftime("%Y-%m-%d"),
        "generated_at": now_ist().strftime("%Y-%m-%d %H:%M:%S IST"),
        "bias": score.get("bias"),
        "score": score.get("score"),
        "confidence": score.get("confidence"),
        # Tracked per day so the five-factor model can be scored against the
        # broad composite once there is enough history to compare them.
        "core_bias": (score.get("core_model") or {}).get("bias"),
        "core_score": (score.get("core_model") or {}).get("score"),
        "core_confidence": (score.get("core_model") or {}).get("confidence"),
        "fii_net": flow.get("fii_net"),
        "dii_net": flow.get("dii_net"),
        # Gross legs as well as the net, so the day-wise hover can show how much
        # was bought and sold rather than only the difference.
        "fii_buy": _flow_leg(flow, "FII", "buy"),
        "fii_sell": _flow_leg(flow, "FII", "sell"),
        "dii_buy": _flow_leg(flow, "DII", "buy"),
        "dii_sell": _flow_leg(flow, "DII", "sell"),
        # The NSE session these figures belong to, which is not the run date on
        # weekends, holidays, or a re-run before the next session settles.
        "fii_dii_date": flow.get("data_date"),
        "combined_flow": _sum_optional(flow.get("fii_net"), flow.get("dii_net")),
        "gift_nifty_change_pct": (nse.get("gift_nifty") or {}).get("change_pct"),
        "india_vix_change_pct": (nse.get("india_vix") or {}).get("change_pct"),
        "nifty_pcr": nifty.get("pcr"),
        "nifty_support": nifty.get("support"),
        "nifty_resistance": nifty.get("resistance"),
        "banknifty_pcr": bank.get("pcr"),
        "banknifty_support": bank.get("support"),
        "banknifty_resistance": bank.get("resistance"),
        "us_avg_change_pct": _region_avg(global_rows, "US"),
        "europe_avg_change_pct": _region_avg(global_rows, "Europe"),
        "asia_avg_change_pct": _region_avg(global_rows, "Asia"),
        "top_sector": top_sector.get("name"),
        "top_sector_change_pct": top_sector.get("change_pct"),
        "weak_sector": weak_sector.get("name"),
        "weak_sector_change_pct": weak_sector.get("change_pct"),
        "gold_change_pct": _named_change(data.get("commodities", []), "Gold"),
        "crude_oil_change_pct": _named_change(data.get("commodities", []), "Crude Oil WTI"),
        "brent_oil_change_pct": _named_change(data.get("commodities", []), "Brent Oil"),
        "bitcoin_change_pct": _named_change(data.get("crypto", []), "Bitcoin"),
        "ethereum_change_pct": _named_change(data.get("crypto", []), "Ethereum"),
        "dxy_change_pct": _named_change(data.get("currencies", []), "DXY"),
        "usdinr_change_pct": _named_change(data.get("currencies", []), "USD/INR"),
    }


def _hit_text(hit: Any) -> str:
    if hit is None:
        return "(no directional call)"
    return "HIT" if hit else "MISS"


def _hit_rate_text(history: list[dict[str, Any]]) -> str:
    """Running hit rate for both models over every scored day so far."""
    parts = []
    for label, key in (("core", "core_hit"), ("composite", "composite_hit")):
        calls = [row[key] for row in history if row.get(key) is not None]
        if not calls:
            parts.append(f"{label} n/a")
            continue
        hits = sum(1 for call in calls if call)
        parts.append(f"{label} {hits}/{len(calls)} ({hits / len(calls) * 100:.0f}%)")
    return "Directional hit rate so far: " + ", ".join(parts)


def _flow_leg(flow: dict[str, Any], category: str, side: str) -> float | None:
    """Gross buy or sell value for one investor category.

    NSE labels the foreign leg "FII/FPI" and the domestic one "DII", so the
    match is a prefix test rather than equality.
    """
    for row in flow.get("rows") or []:
        label = str(row.get("category") or "").upper().replace(" ", "")
        if label.startswith(category.upper()):
            value = row.get(side)
            return float(value) if value is not None else None
    return None


def _named_change(rows: list[dict[str, Any]], name: str) -> float | None:
    for row in rows:
        if row.get("name") == name:
            value = row.get("change_pct")
            return float(value) if value is not None else None
    return None


def _sum_optional(a: Any, b: Any) -> float | None:
    if a is None and b is None:
        return None
    return float(a or 0) + float(b or 0)


def _region_avg(rows: list[dict[str, Any]], region: str) -> float | None:
    values = [row.get("change_pct") for row in rows if row.get("region") == region and row.get("change_pct") is not None]
    if not values:
        return None
    return sum(float(value) for value in values) / len(values)


if __name__ == "__main__":
    main()
