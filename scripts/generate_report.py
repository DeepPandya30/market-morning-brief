from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from market_brief.config import DASHBOARD_DIR, DOCS_DIR, PROCESSED_DIR, RAW_DIR, REPORTS_DIR
from market_brief.fetchers import build_data_bundle
from market_brief.render import create_report_context, save_outputs
from market_brief.scoring import score_market
from market_brief.utils import dump_json, ensure_dirs, now_ist


def main() -> None:
    ensure_dirs(RAW_DIR, PROCESSED_DIR, REPORTS_DIR, DASHBOARD_DIR, DOCS_DIR)

    data = build_data_bundle()
    score = score_market(data)
    context = create_report_context(data, score)

    stamp = now_ist().strftime("%Y-%m-%d_%H-%M-%S")
    dump_json(RAW_DIR / f"market_data_{stamp}.json", data)
    dump_json(PROCESSED_DIR / "latest_summary.json", {"score": score, "data": data})

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


if __name__ == "__main__":
    main()
