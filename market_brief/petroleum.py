"""EIA Weekly Petroleum Status Report (WPSR) — the crude oil section.

EIA releases the data tables every Wednesday at 10:30 a.m. eastern and the
Highlights write-up at 1:00 p.m. eastern, both covering the week ending the
previous Friday. 1:00 p.m. ET is 22:30 IST (23:30 in US winter), so a Wednesday
morning brief can only ever carry the *previous* week's report: the daily
pipeline renders whatever the latest available release is, and a separate
Wednesday-evening job refreshes this section once the new week is out. When
Monday is a US federal holiday the whole release slips to Thursday.

Everything is read from Table 9 (U.S. and PAD District Weekly Estimates), the
one file that carries every number the Highlights leads with. Failures fall
back to the previous run's cache rather than blanking the dashboard section.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import requests

from .config import (
    NEWS_USER_AGENT,
    PETROLEUM_ACTIVITY_ROWS,
    PETROLEUM_BUILD_THRESHOLD_MMBBL,
    PETROLEUM_ENCODINGS,
    PETROLEUM_HIGHLIGHTS_URL,
    PETROLEUM_LANDING_URL,
    PETROLEUM_STOCK_ROWS,
    PETROLEUM_TABLE_URL,
)
from .utils import now_ist

REQUEST_TIMEOUT = 30

# Table 9 columns after the two label columns.
COL_WEEK = 0
COL_PRIOR = 1
COL_YEAR_AGO = 2
COL_FOUR_WEEK = 4

# EIA writes an en-dash pair into cells that have no value (four-week averages
# are not published for stock levels, for instance).
BLANK_CELLS = {"", "-", "--", "– –", "–", "—", "— —", "NA", "W"}


def fetch_petroleum_status(
    warnings: list[str],
    cache_path: Path | None = None,
) -> dict[str, Any]:
    """Build the crude oil payload, falling back to cache on failure."""
    cached = _load_cache(cache_path)

    try:
        payload = _parse_table(_download_text(PETROLEUM_TABLE_URL))
    except Exception as exc:
        warnings.append(f"petroleum_status: WPSR table fetch failed ({exc})")
        if cached:
            cached["from_cache"] = True
            cached["cache_reason"] = str(exc)
            return cached
        return _empty_payload()

    if not payload.get("stocks"):
        warnings.append("petroleum_status: table parsed but carried no stock rows")
        if cached:
            cached["from_cache"] = True
            cached["cache_reason"] = "no stock rows in fetched table"
            return cached

    payload["signal"] = _build_signal(payload)
    payload["stats"] = _build_stats(payload)
    _write_cache(cache_path, payload)
    return payload


# ---------------------------------------------------------------------------
# Download and parse
# ---------------------------------------------------------------------------


def _download_text(url: str) -> str:
    response = requests.get(
        url,
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": NEWS_USER_AGENT, "Accept": "*/*"},
    )
    response.raise_for_status()
    for encoding in PETROLEUM_ENCODINGS:
        try:
            return response.content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return response.content.decode(PETROLEUM_ENCODINGS[-1], errors="replace")


def _cell(value: str) -> float | None:
    text = str(value or "").strip().replace(",", "")
    if text in BLANK_CELLS or not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_date(text: str) -> date | None:
    """Table 9 stamps its columns M/D/YY."""
    raw = str(text or "").strip()
    for fmt in ("%m/%d/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _round(value: float | None, digits: int = 3) -> float | None:
    return None if value is None else round(value, digits)


def _parse_table(text: str) -> dict[str, Any]:
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        raise ValueError("empty table")

    header = rows[0]
    week = _parse_date(header[2]) if len(header) > 2 else None
    prior = _parse_date(header[3]) if len(header) > 3 else None
    year_ago = _parse_date(header[4]) if len(header) > 4 else None
    if week is None:
        raise ValueError(f"unrecognised week column {header[2:3]}")

    # First value wins: section headline rows (e.g. "Crude Oil Inputs") precede
    # their PAD district children, and some child labels repeat across sections.
    values: dict[tuple[str, str], list[float | None]] = {}
    for row in rows[1:]:
        if len(row) < 3:
            continue
        key = (row[0].strip(), row[1].strip())
        if key in values:
            continue
        values[key] = [_cell(cell) for cell in row[2:]]

    payload = _empty_payload()
    payload.update(_release_dates(week, prior, year_ago))

    for key, section, label, name in PETROLEUM_STOCK_ROWS:
        cells = values.get((section, label))
        if cells is None:
            continue
        payload["stocks"].append(_stock_entry(key, name, cells))

    for key, section, label, name, unit in PETROLEUM_ACTIVITY_ROWS:
        cells = values.get((section, label))
        if cells is None:
            continue
        payload["activity"].append(_activity_entry(key, name, unit, cells))

    payload["by_key"] = {row["key"]: row for row in payload["stocks"]}
    payload["by_key"].update({row["key"]: row for row in payload["activity"]})
    return payload


def _at(cells: list[float | None], index: int) -> float | None:
    return cells[index] if index < len(cells) else None


def _stock_entry(key: str, name: str, cells: list[float | None]) -> dict[str, Any]:
    latest = _at(cells, COL_WEEK)
    prior = _at(cells, COL_PRIOR)
    year_ago = _at(cells, COL_YEAR_AGO)
    change = None if latest is None or prior is None else latest - prior
    year_ago_change = None if latest is None or year_ago is None else latest - year_ago
    return {
        "key": key,
        "name": name,
        "unit": "MMbbl",
        "stocks": _round(latest),
        "prior": _round(prior),
        "change": _round(change),
        "pct_change": _round(_pct(change, prior), 2),
        "year_ago": _round(year_ago),
        "year_ago_change": _round(year_ago_change),
        "year_ago_pct": _round(_pct(year_ago_change, year_ago), 2),
    }


def _activity_entry(key: str, name: str, unit: str, cells: list[float | None]) -> dict[str, Any]:
    latest = _at(cells, COL_WEEK)
    prior = _at(cells, COL_PRIOR)
    year_ago = _at(cells, COL_YEAR_AGO)
    change = None if latest is None or prior is None else latest - prior
    return {
        "key": key,
        "name": name,
        "unit": unit,
        "value": _round(latest, 1),
        "prior": _round(prior, 1),
        "change": _round(change, 1),
        "year_ago": _round(year_ago, 1),
        "year_ago_change": _round(None if latest is None or year_ago is None else latest - year_ago, 1),
        "four_week_avg": _round(_at(cells, COL_FOUR_WEEK), 1),
    }


def _pct(change: float | None, base: float | None) -> float | None:
    if change is None or base in (None, 0):
        return None
    return change / abs(base) * 100


def _release_dates(week: date, prior: date | None, year_ago: date | None) -> dict[str, Any]:
    """Nominal release timing derived from the week-ending date.

    EIA publishes the week ending Friday on the following Wednesday, so the
    release date is inferred rather than scraped. A holiday week slips the real
    release to Thursday; the weekly job simply keeps retrying until the newer
    week appears, so an inferred date being a day early is harmless — it is a
    label, never a gate.
    """
    released = week + timedelta(days=(2 - week.weekday()) % 7 or 7)
    next_release = released + timedelta(days=7)
    today = now_ist().date()
    return {
        "week_ending": week.isoformat(),
        "week_ending_label": week.strftime("%d %b %Y"),
        "prior_week_ending": prior.isoformat() if prior else None,
        "prior_week_ending_label": prior.strftime("%d %b %Y") if prior else None,
        "year_ago_week_ending": year_ago.isoformat() if year_ago else None,
        "year_ago_label": year_ago.strftime("%d %b %Y") if year_ago else None,
        "released": released.isoformat(),
        "released_label": released.strftime("%d %b %Y"),
        # 1:00 p.m. ET, the Highlights slot, is 23:00 IST give or take the US
        # daylight-time shift.
        "released_ist_label": f"{released:%d %b %Y}, 11:00 PM IST",
        "next_release": next_release.isoformat(),
        "next_release_label": next_release.strftime("%d %b %Y"),
        "next_release_ist_label": f"{next_release:%d %b %Y}, 11:00 PM IST",
        "days_to_next_release": (next_release - today).days,
        "is_overdue": next_release < today,
    }


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def _build_signal(payload: dict[str, Any]) -> dict[str, Any]:
    """Turn the week's crude move into a read for an India-focused reader.

    A crude build points to softer oil prices, which is supportive for India as
    a net importer — the opposite of how the same print reads for an oil
    producer, so the note says which way it is being read.
    """
    lookup = payload.get("by_key") or {}
    crude = lookup.get("crude_commercial") or {}
    change = crude.get("change")
    if change is None:
        return {"label": "No read", "tone": "neutral", "note": "Crude stock change unavailable."}

    threshold = PETROLEUM_BUILD_THRESHOLD_MMBBL
    if change >= threshold:
        label, tone = "Crude build", "good"
        lead = f"Commercial crude stocks rose {abs(change):.1f} million barrels"
        read = "softer crude is supportive for India as a net importer"
    elif change <= -threshold:
        label, tone = "Crude draw", "bad"
        lead = f"Commercial crude stocks fell {abs(change):.1f} million barrels"
        read = "tighter crude lifts the import bill for India"
    else:
        label, tone = "Little changed", "neutral"
        lead = f"Commercial crude stocks moved {change:+.1f} million barrels"
        read = "too small to move the oil price on its own"

    parts = [f"{lead} — {read}"]

    gasoline = (lookup.get("gasoline") or {}).get("change")
    distillate = (lookup.get("distillate") or {}).get("change")
    if gasoline is not None and distillate is not None:
        parts.append(f"gasoline {gasoline:+.1f} and distillate {distillate:+.1f} million barrels")

    utilization = lookup.get("refinery_utilization") or {}
    if utilization.get("value") is not None:
        detail = f"refineries running at {utilization['value']:.1f}%"
        if utilization.get("change") is not None:
            detail += f" ({utilization['change']:+.1f} pt on the week)"
        parts.append(detail)

    return {"label": label, "tone": tone, "note": "; ".join(parts) + "."}


def _build_stats(payload: dict[str, Any]) -> dict[str, Any]:
    """Headline tiles: the numbers the Highlights leads with."""
    lookup = payload.get("by_key") or {}
    crude = lookup.get("crude_commercial") or {}
    cushing = lookup.get("cushing") or {}
    production = lookup.get("production") or {}
    utilization = lookup.get("refinery_utilization") or {}
    spr = lookup.get("spr") or {}
    return {
        "crude_stocks": crude.get("stocks"),
        "crude_change": crude.get("change"),
        "crude_vs_year_ago_pct": crude.get("year_ago_pct"),
        "cushing_stocks": cushing.get("stocks"),
        "cushing_change": cushing.get("change"),
        "production": production.get("value"),
        "production_change": production.get("change"),
        "refinery_utilization": utilization.get("value"),
        "refinery_utilization_change": utilization.get("change"),
        "spr_stocks": spr.get("stocks"),
        "spr_change": spr.get("change"),
    }


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


def _empty_payload() -> dict[str, Any]:
    return {
        "source": "eia_wpsr",
        "title": "US Weekly Petroleum Status — Crude Oil",
        "landing_url": PETROLEUM_LANDING_URL,
        "highlights_url": PETROLEUM_HIGHLIGHTS_URL,
        "table_url": PETROLEUM_TABLE_URL,
        "fetched_at": now_ist().strftime("%d %b %Y, %I:%M %p IST"),
        "fetched_at_iso": now_ist().isoformat(),
        "week_ending": None,
        "week_ending_label": None,
        "prior_week_ending": None,
        "prior_week_ending_label": None,
        "year_ago_week_ending": None,
        "year_ago_label": None,
        "released": None,
        "released_label": None,
        "released_ist_label": None,
        "next_release": None,
        "next_release_label": None,
        "next_release_ist_label": None,
        "days_to_next_release": None,
        "is_overdue": False,
        "stocks": [],
        "activity": [],
        "by_key": {},
        "signal": {},
        "stats": {},
        "from_cache": False,
    }


def _load_cache(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return cached if isinstance(cached, dict) else None


def _write_cache(path: Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
    except Exception:
        # A cache write failure must never take the report down with it.
        pass
