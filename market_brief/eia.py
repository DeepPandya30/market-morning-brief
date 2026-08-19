"""EIA Weekly Natural Gas Storage Report (WNGSR).

Published every Thursday at 10:30 a.m. eastern time for the week ending the
previous Friday. In IST that lands at 20:00 on Thursday — well after the 07:50
morning brief has gone out — so the daily pipeline always renders whatever the
most recent release is, and a separate Thursday-evening job refreshes the
side-car JSON once the new number is out.

Everything here fails soft: a fetch error returns the cached payload from the
previous run rather than blanking the dashboard section.
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
    NG_INJECTION_MONTHS,
    NG_STORAGE_CSV_URL,
    NG_STORAGE_HISTORY_URL,
    NG_STORAGE_HISTORY_WEEKS,
    NG_STORAGE_LANDING_URL,
    NG_STORAGE_REPORT_URL,
    NG_STORAGE_SEASONAL_YEARS,
    NG_STORAGE_SUBREGIONS,
    NEWS_USER_AGENT,
)
from .utils import now_ist, to_float

# Order the eight numeric fields appear in on every wngsr.csv data row once the
# padding columns are dropped. The file is laid out for spreadsheet display, so
# each logical column is followed by two or three empty ones.
CSV_VALUE_FIELDS = (
    "stocks",
    "prior_stocks",
    "net_change",
    "implied_flow",
    "year_ago_stocks",
    "year_ago_pct",
    "five_year_stocks",
    "five_year_pct",
)

REQUEST_TIMEOUT = 30

HISTORY_SHEET = "html_report_history"
NET_CHANGE_SHEET = "weekly_net_changes"

# Both sheets carry five preamble rows of survey notes, then a header row, then
# data. Column 0 is the week-ending date and column 9 is Total Lower 48.
HISTORY_HEADER_ROW = 6
HISTORY_DATE_COL = 0
HISTORY_TOTAL_COL = 9


def fetch_natural_gas_storage(
    warnings: list[str],
    cache_path: Path | None = None,
    include_history: bool = True,
) -> dict[str, Any]:
    """Build the natural gas storage payload, falling back to cache on failure.

    ``include_history`` downloads the ~700 KB history workbook for the
    trajectory chart and the 5-year seasonal band. It is optional because the
    weekly headline numbers are useful on their own, and the workbook needs the
    ``xlrd`` reader which may not be installed everywhere.
    """
    cached = _load_cache(cache_path)

    try:
        payload = _parse_weekly_csv(_download_text(NG_STORAGE_CSV_URL))
    except Exception as exc:
        warnings.append(f"natural_gas_storage: weekly report fetch failed ({exc})")
        if cached:
            cached["from_cache"] = True
            cached["cache_reason"] = str(exc)
            return cached
        return _empty_payload()

    if include_history:
        try:
            payload["history"], payload["seasonal"], payload["net_change_history"] = _parse_history(
                _download_bytes(NG_STORAGE_HISTORY_URL),
                payload.get("week_ending"),
            )
        except Exception as exc:
            warnings.append(f"natural_gas_storage: history workbook unavailable ({exc})")
            # Keep whatever history the previous run cached — a stale chart is
            # better than an empty one, and the headline numbers are still fresh.
            for key in ("history", "seasonal", "net_change_history"):
                payload[key] = (cached or {}).get(key) or ([] if key != "seasonal" else {})
            # The seasonal norm is specific to one calendar week, so reusing it
            # against a newer print would compare this week's build to last
            # week's average. Drop it and let the signal fall back to the
            # 5-year percentage, which the weekly CSV still carries.
            if (cached or {}).get("week_ending") != payload.get("week_ending"):
                payload["seasonal"] = dict(payload["seasonal"] or {})
                payload["seasonal"].pop("net_change_norm", None)

    payload["signal"] = _build_signal(payload)
    payload["stats"] = _build_stats(payload)

    if not payload.get("regions"):
        warnings.append("natural_gas_storage: report parsed but contained no region rows")
    for note in _reconcile(payload):
        warnings.append(f"natural_gas_storage: {note}")

    _write_cache(cache_path, payload)
    return payload


# ---------------------------------------------------------------------------
# Downloads
# ---------------------------------------------------------------------------


def _download_bytes(url: str) -> bytes:
    response = requests.get(
        url,
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": NEWS_USER_AGENT, "Accept": "*/*"},
    )
    response.raise_for_status()
    return response.content


def _download_text(url: str) -> str:
    # The CSV is served with a UTF-8 BOM, which would otherwise end up glued to
    # the first header cell.
    return _download_bytes(url).decode("utf-8-sig", errors="replace")


# ---------------------------------------------------------------------------
# Weekly report (wngsr.csv)
# ---------------------------------------------------------------------------


def _parse_weekly_csv(text: str) -> dict[str, Any]:
    rows = list(csv.reader(io.StringIO(text)))
    payload = _empty_payload()

    header_blob = " ".join(cell for row in rows[:6] for cell in row if cell)
    payload.update(_parse_header_dates(header_blob))

    for row in rows:
        region = _region_name(row)
        if region is None:
            continue
        values = _row_values(row)
        if not values:
            continue
        entry: dict[str, Any] = {
            "name": region,
            "is_total": region.lower().startswith("total"),
            "is_subregion": region in NG_STORAGE_SUBREGIONS,
        }
        entry.update(dict(zip(CSV_VALUE_FIELDS, values)))
        # The file stops emitting columns once a row runs out of data, so any
        # field the row never reached is explicitly absent rather than zero.
        for field in CSV_VALUE_FIELDS:
            entry.setdefault(field, None)
        entry["fill_pct"] = _fill_pct(entry)
        payload["regions"].append(entry)

    payload["total"] = next(
        (row for row in payload["regions"] if row["is_total"]),
        {},
    )
    return payload


def _region_name(row: list[str]) -> str | None:
    """Return the canonical region name for a data row, or None if not one."""
    if not row:
        return None
    label = row[0].strip()
    if not label:
        return None
    # "  Salt" / "  Nonsalt" arrive indented to mark them as South Central splits.
    canonical = {"salt": "Salt", "nonsalt": "Nonsalt", "non-salt": "Nonsalt"}.get(label.lower())
    if canonical:
        return canonical
    if label.lower().startswith("total"):
        return "Total"
    if label in {"East", "Midwest", "Mountain", "Pacific", "South Central"}:
        return label
    return None


def _row_values(row: list[str]) -> list[float | None]:
    """Pull the eight numeric fields out of a padded spreadsheet row."""
    values: list[float | None] = []
    for cell in row[1:]:
        text = cell.strip()
        if not text:
            continue
        values.append(to_float(text))
    return values[: len(CSV_VALUE_FIELDS)]


def _parse_header_dates(blob: str) -> dict[str, Any]:
    """Extract release / week-ending / next-release dates from the preamble."""
    out: dict[str, Any] = {}

    released = _match_date(blob, "Released:")
    if released:
        out["released_at"] = released.isoformat()
        out["released_label"] = released.strftime("%d %b %Y")

    week_ending = _match_date(blob, "for the Week Ending")
    if week_ending:
        out["week_ending"] = week_ending.isoformat()
        out["week_ending_label"] = week_ending.strftime("%d %b %Y")
        out["prior_week_ending"] = (week_ending - timedelta(days=7)).isoformat()
        out["prior_week_ending_label"] = (week_ending - timedelta(days=7)).strftime("%d %b %Y")
        out["season"] = (
            "Injection" if week_ending.month in NG_INJECTION_MONTHS else "Withdrawal"
        )

    next_release = _match_date(blob, "Next Release:")
    if next_release:
        out["next_release"] = next_release.isoformat()
        out["next_release_label"] = next_release.strftime("%d %b %Y")
        # 10:30 ET is 20:00 IST; EDT and IST are both fixed offsets over the
        # week in question, so a plain label is accurate enough here.
        out["next_release_ist_label"] = f"{next_release:%d %b %Y}, 08:00 PM IST"
        today = now_ist().date()
        out["days_to_next_release"] = (next_release - today).days
        # A next-release date in the past means EIA slipped the schedule (or
        # this run is reading a stale cache), which the dashboard flags.
        out["is_overdue"] = next_release < today

    return out


def _match_date(blob: str, marker: str) -> date | None:
    """Read the 'Month D, YYYY' date that follows ``marker`` in the preamble."""
    idx = blob.find(marker)
    if idx < 0:
        return None
    tail = blob[idx + len(marker) : idx + len(marker) + 40].strip()
    parts = tail.replace(",", " ").split()
    if len(parts) < 3:
        return None
    for fmt in ("%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(" ".join(parts[:3]), fmt).date()
        except ValueError:
            continue
    return None


def _reconcile(payload: dict[str, Any]) -> list[str]:
    """Sanity-check the parse, since wngsr.csv is read by column position.

    The file pads every logical column with two or three empty ones, so the
    fields are located by dropping blanks and taking what is left in order. If
    EIA ever adds, drops or reorders a column, that mapping shifts silently and
    every number would still look plausible. Two identities in the data catch
    it: each row's stocks must equal the prior week plus the net change, and the
    five regions must sum to the reported total.
    """
    notes: list[str] = []
    regions = payload.get("regions") or []

    for row in regions:
        stocks, prior, change = row.get("stocks"), row.get("prior_stocks"), row.get("net_change")
        if stocks is None or prior is None or change is None:
            continue
        # EIA rounds each column to whole Bcf independently, so allow a little slack.
        if abs((prior + change) - stocks) > 1.5:
            notes.append(
                f"{row['name']} does not reconcile "
                f"({prior:g} + {change:g} != {stocks:g}) — the report format may have changed"
            )

    total = payload.get("total") or {}
    parts = [
        row.get("stocks")
        for row in regions
        if not row.get("is_total") and not row.get("is_subregion")
    ]
    if total.get("stocks") is not None and parts and all(value is not None for value in parts):
        if abs(sum(parts) - total["stocks"]) > 2.5:
            notes.append(
                f"regions sum to {sum(parts):g} Bcf but the total row reads "
                f"{total['stocks']:g} Bcf — the report format may have changed"
            )
    return notes


def _fill_pct(entry: dict[str, Any]) -> float | None:
    """Current stocks as a share of the 5-year average for the same week."""
    stocks = entry.get("stocks")
    average = entry.get("five_year_stocks")
    if stocks is None or not average:
        return None
    return round(stocks / average * 100, 1)


# ---------------------------------------------------------------------------
# History workbook (ngshistory.xls)
# ---------------------------------------------------------------------------


def _parse_history(
    raw: bytes,
    week_ending: str | None,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    import pandas as pd

    stocks = _read_history_sheet(pd, raw, HISTORY_SHEET)
    changes = _read_history_sheet(pd, raw, NET_CHANGE_SHEET)
    change_by_week = {row["week_ending"]: row["value"] for row in changes}

    history = [
        {
            "week_ending": row["week_ending"],
            "total": row["value"],
            "net_change": change_by_week.get(row["week_ending"]),
        }
        for row in stocks
    ]

    seasonal = _build_seasonal(history, week_ending)
    # Computed here, off the untruncated series, because the payload only keeps
    # ~3 years of weeks — not enough to average 5 prior years of the same week.
    seasonal["net_change_norm"] = _net_change_norm(history, week_ending)
    net_change_history = [
        {"week_ending": row["week_ending"], "net_change": row["net_change"]}
        for row in history[-NG_STORAGE_HISTORY_WEEKS:]
    ]
    return history[-NG_STORAGE_HISTORY_WEEKS:], seasonal, net_change_history


def _net_change_norm(history: list[dict[str, Any]], week_ending: str | None) -> float | None:
    """Average weekly net change for this calendar week across the prior 5 years."""
    if not history:
        return None
    target = date.fromisoformat(week_ending or history[-1]["week_ending"])
    target_week = target.isocalendar().week
    years = {target.year - offset for offset in range(1, NG_STORAGE_SEASONAL_YEARS + 1)}

    window = []
    for row in history:
        if row.get("net_change") is None:
            continue
        stamp = date.fromisoformat(row["week_ending"])
        if stamp.year in years and stamp.isocalendar().week == target_week:
            window.append(row["net_change"])
    if not window:
        return None
    return round(sum(window) / len(window), 1)


def _read_history_sheet(pd: Any, raw: bytes, sheet: str) -> list[dict[str, Any]]:
    frame = pd.read_excel(io.BytesIO(raw), sheet_name=sheet, header=None, skiprows=HISTORY_HEADER_ROW + 1)
    out: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        stamp = pd.to_datetime(row.iloc[HISTORY_DATE_COL], errors="coerce")
        value = to_float(row.iloc[HISTORY_TOTAL_COL])
        if pd.isna(stamp) or value is None:
            continue
        out.append({"week_ending": stamp.date().isoformat(), "value": value})
    out.sort(key=lambda item: item["week_ending"])
    return out


def _build_seasonal(history: list[dict[str, Any]], week_ending: str | None) -> dict[str, Any]:
    """Current storage year against the prior 5 years, aligned by week of year.

    Storage is strongly seasonal, so a level only means something next to the
    same week in prior years. Weeks are matched on ISO week number rather than
    calendar date because the week-ending Friday drifts across years.
    """
    if not history:
        return {}

    latest = week_ending or history[-1]["week_ending"]
    latest_date = date.fromisoformat(latest)

    by_year: dict[int, dict[int, float]] = {}
    for row in history:
        stamp = date.fromisoformat(row["week_ending"])
        by_year.setdefault(stamp.year, {})[stamp.isocalendar().week] = row["total"]

    current_year = latest_date.year
    prior_years = [current_year - offset for offset in range(1, NG_STORAGE_SEASONAL_YEARS + 1)]

    weeks = list(range(1, 53))
    current: list[float | None] = []
    year_ago: list[float | None] = []
    averages: list[float | None] = []
    minimums: list[float | None] = []
    maximums: list[float | None] = []

    for week in weeks:
        current.append(by_year.get(current_year, {}).get(week))
        year_ago.append(by_year.get(current_year - 1, {}).get(week))
        window = [by_year.get(year, {}).get(week) for year in prior_years]
        window = [value for value in window if value is not None]
        averages.append(round(sum(window) / len(window), 1) if window else None)
        minimums.append(min(window) if window else None)
        maximums.append(max(window) if window else None)

    return {
        "weeks": weeks,
        "labels": [f"W{week:02d}" for week in weeks],
        "current_year": current_year,
        "current": current,
        "year_ago_year": current_year - 1,
        "year_ago": year_ago,
        "average_label": f"{min(prior_years)}-{str(max(prior_years))[-2:]} average",
        "average": averages,
        "min": minimums,
        "max": maximums,
    }


# ---------------------------------------------------------------------------
# Derived read-outs
# ---------------------------------------------------------------------------


def _build_signal(payload: dict[str, Any]) -> dict[str, Any]:
    """Translate the storage print into a price-direction read for gas.

    Storage above the seasonal norm means supply is comfortable, which is
    bearish for prices; a deficit is bullish. The size of the weekly change
    relative to the same week in prior years is the closer read on momentum,
    so it decides the label when history is available.
    """
    total = payload.get("total") or {}
    five_year_pct = total.get("five_year_pct")
    net_change = total.get("net_change")
    surprise = _change_vs_norm(payload)
    payload["change_vs_norm"] = surprise

    if five_year_pct is None:
        return {
            "label": "No Read",
            "tone": "neutral",
            "note": "Storage report did not include a 5-year comparison this week.",
        }

    direction = "build" if (net_change or 0) >= 0 else "draw"
    parts = [
        f"Lower 48 stocks are {abs(five_year_pct):.1f}% "
        f"{'above' if five_year_pct >= 0 else 'below'} the 5-year average"
    ]
    if net_change is not None:
        parts.append(f"this week was a {abs(net_change):,.0f} Bcf {direction}")
    if surprise is not None:
        parts.append(
            f"{abs(surprise):,.0f} Bcf {'larger' if surprise > 0 else 'smaller'} "
            "than the 5-year norm for this week"
        )

    # A surplus is bearish for gas; the weekly surprise sharpens or softens it.
    if five_year_pct >= 5:
        label, tone = "Bearish for Gas", "bad"
    elif five_year_pct <= -5:
        label, tone = "Bullish for Gas", "good"
    else:
        label, tone = "Balanced", "neutral"

    if surprise is not None and abs(surprise) >= 15 and label == "Balanced":
        label = "Bearish for Gas" if surprise > 0 else "Bullish for Gas"
        tone = "bad" if surprise > 0 else "good"

    return {"label": label, "tone": tone, "note": "; ".join(parts) + "."}


def _change_vs_norm(payload: dict[str, Any]) -> float | None:
    """This week's net change minus the 5-year average change for the same week."""
    norm = (payload.get("seasonal") or {}).get("net_change_norm")
    actual = (payload.get("total") or {}).get("net_change")
    if norm is None or actual is None:
        return None
    return round(actual - norm, 1)


def _build_stats(payload: dict[str, Any]) -> dict[str, Any]:
    total = payload.get("total") or {}
    history = payload.get("history") or []
    stocks = [row["total"] for row in history if row.get("total") is not None]
    return {
        "stocks": total.get("stocks"),
        "net_change": total.get("net_change"),
        "year_ago_pct": total.get("year_ago_pct"),
        "five_year_pct": total.get("five_year_pct"),
        "fill_pct": total.get("fill_pct"),
        "weeks_of_history": len(history),
        # Where the current level sits inside the range the chart is showing,
        # so the headline tile can say "3-year high" without a second lookup.
        "period_high": max(stocks) if stocks else None,
        "period_low": min(stocks) if stocks else None,
    }


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


def _empty_payload() -> dict[str, Any]:
    return {
        "source": "eia_wngsr",
        "title": "Working Gas in Underground Storage, Lower 48",
        "report_url": NG_STORAGE_REPORT_URL,
        "landing_url": NG_STORAGE_LANDING_URL,
        "fetched_at": now_ist().strftime("%d %b %Y, %I:%M %p IST"),
        "fetched_at_iso": now_ist().isoformat(),
        "released_at": None,
        "released_label": None,
        "week_ending": None,
        "week_ending_label": None,
        "next_release": None,
        "next_release_label": None,
        "season": None,
        "regions": [],
        "total": {},
        "history": [],
        "net_change_history": [],
        "seasonal": {},
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
