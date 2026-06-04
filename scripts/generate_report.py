from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from market_brief.config import DASHBOARD_DIR, DOCS_DIR, PROCESSED_DIR, RAW_DIR, REPORTS_DIR
from market_brief.fetchers import build_data_bundle
from market_brief.render import create_report_context, save_outputs
from market_brief.scoring import score_market
from market_brief.utils import dump_json, ensure_dirs, now_ist


def main() -> None:
    ensure_dirs(RAW_DIR, PROCESSED_DIR, REPORTS_DIR, DASHBOARD_DIR, DOCS_DIR, DOCS_DIR / "data")

    data = build_data_bundle()
    score = score_market(data)
    history = update_history(data, score, PROCESSED_DIR / "history.json")
    context = create_report_context(data, score, history=history)

    stamp = now_ist().strftime("%Y-%m-%d_%H-%M-%S")
    latest_summary = {"score": score, "data": data, "history": history}

    dump_json(RAW_DIR / f"market_data_{stamp}.json", data)
    dump_json(PROCESSED_DIR / "latest_summary.json", latest_summary)
    dump_json(DOCS_DIR / "data" / "latest_summary.json", latest_summary)
    dump_json(DOCS_DIR / "data" / "history.json", history)

    save_outputs(
        context,
        REPORTS_DIR / "morning_report.md",
        DASHBOARD_DIR / "index.html",
        DOCS_DIR / "index.html",
    )

    print(f"Generated report with bias={score['bias']} score={score['score']} confidence={score['confidence']}")
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
    dump_json(history_path, history)
    return history


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
        "fii_net": flow.get("fii_net"),
        "dii_net": flow.get("dii_net"),
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
    }


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
