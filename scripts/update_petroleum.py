"""Refresh only the EIA crude oil section of the dashboard.

EIA publishes the Weekly Petroleum Status Report every Wednesday — data tables
at 10:30 a.m. eastern, the Highlights write-up at 1:00 p.m. eastern, which is
about 23:00 IST. That is long after the morning brief has been generated and
published, so this script touches the crude section and nothing else:

  1. writes the parsed report to data/processed/ (the fetch cache)
  2. writes the side-car docs/data/petroleum.json the dashboard fetches
  3. patches the petroleum branch of the payload embedded in the published
     HTML, so the section is correct even for a viewer whose browser cannot
     reach the side-car

Exits 0 when EIA has not published yet, so a job that runs slightly early does
not report a false failure. A US federal holiday on the Monday pushes the whole
release to Thursday; the later slots simply find the new week then.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from market_brief.config import (
    DASHBOARD_DIR,
    DOCS_DIR,
    PETROLEUM_CACHE_NAME,
    PETROLEUM_SIDECAR_NAME,
    PROCESSED_DIR,
)
from market_brief.petroleum import fetch_petroleum_status
from market_brief.utils import dump_json, ensure_dirs

PAYLOAD_OPEN = '<script id="app-data" type="application/json">'
PAYLOAD_CLOSE = "</script>"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh the EIA crude oil section.")
    parser.add_argument(
        "--require-new",
        action="store_true",
        help=(
            "Report changed=false unless the fetched report is a newer week than "
            "the one already published. Used by the weekly workflow so a retry "
            "slot does not create an empty commit."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_dirs(PROCESSED_DIR, DOCS_DIR / "data", DASHBOARD_DIR / "data")

    published_week = _published_week()

    warnings: list[str] = []
    crude = fetch_petroleum_status(warnings, cache_path=PROCESSED_DIR / PETROLEUM_CACHE_NAME)

    for warning in warnings:
        print(f"- {warning}")

    week = crude.get("week_ending")
    if not week:
        print("SKIP: EIA returned no usable report this run.")
        _emit("changed", False)
        return 0

    label = crude.get("week_ending_label") or week
    stocks = (crude.get("stats") or {}).get("crude_stocks")
    signal = (crude.get("signal") or {}).get("label", "no read")
    print(f"Fetched week ending {label}: commercial crude {stocks} MMbbl ({signal})")

    if args.require_new and published_week and week <= published_week:
        print(
            f"SKIP: dashboard already carries week ending {published_week}; "
            "EIA has not published a newer report yet."
        )
        _emit("changed", False)
        return 0

    dump_json(DOCS_DIR / "data" / PETROLEUM_SIDECAR_NAME, crude)
    dump_json(DASHBOARD_DIR / "data" / PETROLEUM_SIDECAR_NAME, crude)

    patched = [path.name for path in _dashboard_files() if _patch_payload(path, crude)]
    _patch_summary(DOCS_DIR / "data" / "latest_summary.json", crude)
    _patch_summary(PROCESSED_DIR / "latest_summary.json", crude)

    print(f"Published side-car and patched embedded payload in: {', '.join(patched) or 'nothing'}")
    _emit("changed", True)
    _emit("week_ending", week)
    _summarize(crude, published_week)
    return 0


def _dashboard_files() -> list[Path]:
    return [path for path in (DOCS_DIR / "index.html", DASHBOARD_DIR / "index.html") if path.exists()]


def _published_week() -> str | None:
    """Week the live dashboard is currently showing, if it has one."""
    sidecar = DOCS_DIR / "data" / PETROLEUM_SIDECAR_NAME
    if not sidecar.exists():
        return None
    try:
        return json.loads(sidecar.read_text(encoding="utf-8")).get("week_ending")
    except Exception:
        return None


def _patch_payload(path: Path, crude: dict[str, Any]) -> bool:
    """Swap the petroleum branch of a rendered page's embedded JSON payload.

    The payload lives in a single well-delimited <script type="application/json">
    block, so it can be parsed and re-serialised without touching the rest of
    the page.
    """
    html = path.read_text(encoding="utf-8")
    start = html.find(PAYLOAD_OPEN)
    if start < 0:
        print(f"WARN: no embedded payload found in {path.name}; side-car fetch will cover it")
        return False
    body_start = start + len(PAYLOAD_OPEN)
    end = html.find(PAYLOAD_CLOSE, body_start)
    if end < 0:
        print(f"WARN: unterminated payload in {path.name}")
        return False

    try:
        payload = json.loads(html[body_start:end])
    except json.JSONDecodeError as exc:
        print(f"WARN: could not parse payload in {path.name} ({exc})")
        return False

    payload.setdefault("data", {})["petroleum"] = crude
    # Matches how render.py serialises the payload, so the closing tag of the
    # script block can never be produced by the data itself.
    encoded = json.dumps(payload, ensure_ascii=False, default=str).replace("</", "<\\/")
    path.write_text(html[:body_start] + encoded + html[end:], encoding="utf-8")
    return True


def _patch_summary(path: Path, crude: dict[str, Any]) -> None:
    """Keep the published summary JSON in step with the refreshed section."""
    if not path.exists():
        return
    try:
        summary = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(summary, dict) or not isinstance(summary.get("data"), dict):
        return
    summary["data"]["petroleum"] = crude
    dump_json(path, summary)


def _emit(name: str, value: Any) -> None:
    output = os.environ.get("GITHUB_OUTPUT")
    if not output:
        return
    text = str(value).lower() if isinstance(value, bool) else str(value)
    with open(output, "a", encoding="utf-8") as handle:
        handle.write(f"{name}={text}\n")


def _summarize(crude: dict[str, Any], previous_week: str | None) -> None:
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary:
        return
    stats = crude.get("stats") or {}
    signal = crude.get("signal") or {}
    lines = [
        "### EIA Weekly Petroleum Status refreshed",
        "",
        f"- Week ending: **{crude.get('week_ending_label')}** (previously {previous_week or 'none'})",
        f"- Released: {crude.get('released_label')}",
        f"- Commercial crude stocks: **{stats.get('crude_stocks')} MMbbl**",
        f"- Weekly change: {stats.get('crude_change')} MMbbl",
        f"- Cushing: {stats.get('cushing_stocks')} MMbbl ({stats.get('cushing_change')})",
        f"- Refinery utilisation: {stats.get('refinery_utilization')}%",
        f"- Read: {signal.get('label')} — {signal.get('note')}",
        f"- Next release: {crude.get('next_release_ist_label')}",
        "",
    ]
    with open(summary, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


if __name__ == "__main__":
    raise SystemExit(main())
