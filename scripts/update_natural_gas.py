"""Refresh only the EIA natural gas storage section of the dashboard.

EIA publishes the Weekly Natural Gas Storage Report every Thursday at 10:30
a.m. eastern time, which is 20:00 IST — hours after the morning brief has been
generated and published. Regenerating the whole brief in the evening would
replace a pre-market snapshot with stale intraday data, so this script touches
the gas section and nothing else:

  1. writes the parsed report to data/processed/ (the fetch cache)
  2. writes the side-car docs/data/natural_gas.json the dashboard fetches
  3. patches the natural_gas branch of the payload embedded in the published
     HTML, so the section is correct even for a viewer whose browser cannot
     reach the side-car

Exits 0 when EIA has not published yet, so a job that runs slightly early does
not report a false failure.
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
    NG_STORAGE_CACHE_NAME,
    NG_STORAGE_SIDECAR_NAME,
    PROCESSED_DIR,
)
from market_brief.eia import fetch_natural_gas_storage
from market_brief.utils import dump_json, ensure_dirs

PAYLOAD_OPEN = '<script id="app-data" type="application/json">'
PAYLOAD_CLOSE = "</script>"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh the EIA natural gas storage section.")
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
    gas = fetch_natural_gas_storage(warnings, cache_path=PROCESSED_DIR / NG_STORAGE_CACHE_NAME)

    for warning in warnings:
        print(f"- {warning}")

    week = gas.get("week_ending")
    if not week:
        print("SKIP: EIA returned no usable report this run.")
        _emit("changed", False)
        return 0

    label = gas.get("week_ending_label") or week
    total = (gas.get("total") or {}).get("stocks")
    signal = (gas.get("signal") or {}).get("label", "no read")
    print(f"Fetched week ending {label}: {total} Bcf ({signal})")

    if args.require_new and published_week and week <= published_week:
        print(
            f"SKIP: dashboard already carries week ending {published_week}; "
            "EIA has not published a newer report yet."
        )
        _emit("changed", False)
        return 0

    dump_json(DOCS_DIR / "data" / NG_STORAGE_SIDECAR_NAME, gas)
    dump_json(DASHBOARD_DIR / "data" / NG_STORAGE_SIDECAR_NAME, gas)

    patched = [path.name for path in _dashboard_files() if _patch_payload(path, gas)]
    _patch_summary(DOCS_DIR / "data" / "latest_summary.json", gas)
    _patch_summary(PROCESSED_DIR / "latest_summary.json", gas)

    print(f"Published side-car and patched embedded payload in: {', '.join(patched) or 'nothing'}")
    _emit("changed", True)
    _emit("week_ending", week)
    _summarize(gas, published_week)
    return 0


def _dashboard_files() -> list[Path]:
    return [path for path in (DOCS_DIR / "index.html", DASHBOARD_DIR / "index.html") if path.exists()]


def _published_week() -> str | None:
    """Week the live dashboard is currently showing, if it has one."""
    sidecar = DOCS_DIR / "data" / NG_STORAGE_SIDECAR_NAME
    if not sidecar.exists():
        return None
    try:
        return json.loads(sidecar.read_text(encoding="utf-8")).get("week_ending")
    except Exception:
        return None


def _patch_payload(path: Path, gas: dict[str, Any]) -> bool:
    """Swap the natural_gas branch of a rendered page's embedded JSON payload.

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

    payload.setdefault("data", {})["natural_gas"] = gas
    # Matches how render.py serialises the payload, so the closing tag of the
    # script block can never be produced by the data itself.
    encoded = json.dumps(payload, ensure_ascii=False, default=str).replace("</", "<\\/")
    path.write_text(html[:body_start] + encoded + html[end:], encoding="utf-8")
    return True


def _patch_summary(path: Path, gas: dict[str, Any]) -> None:
    """Keep the published summary JSON in step with the refreshed section."""
    if not path.exists():
        return
    try:
        summary = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(summary, dict) or not isinstance(summary.get("data"), dict):
        return
    summary["data"]["natural_gas"] = gas
    dump_json(path, summary)


def _emit(name: str, value: Any) -> None:
    output = os.environ.get("GITHUB_OUTPUT")
    if not output:
        return
    text = str(value).lower() if isinstance(value, bool) else str(value)
    with open(output, "a", encoding="utf-8") as handle:
        handle.write(f"{name}={text}\n")


def _summarize(gas: dict[str, Any], previous_week: str | None) -> None:
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary:
        return
    total = gas.get("total") or {}
    signal = gas.get("signal") or {}
    lines = [
        "### EIA Natural Gas Storage refreshed",
        "",
        f"- Week ending: **{gas.get('week_ending_label')}** (previously {previous_week or 'none'})",
        f"- Released: {gas.get('released_label')}",
        f"- Working gas, Lower 48: **{total.get('stocks')} Bcf**",
        f"- Weekly net change: {total.get('net_change')} Bcf",
        f"- vs 5-year average: {total.get('five_year_pct')}%",
        f"- Read: {signal.get('label')} — {signal.get('note')}",
        f"- Next release: {gas.get('next_release_ist_label')}",
        "",
    ]
    with open(summary, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


if __name__ == "__main__":
    raise SystemExit(main())
