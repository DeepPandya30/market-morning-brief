from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None


def ensure_dirs(*paths: Path) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def now_ist() -> datetime:
    if ZoneInfo is None:
        return datetime.now().astimezone()
    return datetime.now(ZoneInfo("Asia/Kolkata"))


def to_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return default
        return float(value)
    text = str(value).strip()
    if not text or text.lower() in {"-", "--", "nan", "none", "null"}:
        return default
    text = text.replace(",", "").replace("%", "")
    try:
        return float(text)
    except ValueError:
        return default


def pct_text(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2f}%"


def money_text(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"₹{value:,.2f} Cr"


def number_text(value: float | None) -> str:
    if value is None:
        return "N/A"
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    return f"{value:.2f}"


def dump_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def safe_get(row: dict[str, Any], keys: list[str], default: Any = None) -> Any:
    lower_map = {str(k).lower().replace(" ", "").replace("_", ""): k for k in row.keys()}
    for key in keys:
        if key in row:
            return row[key]
        normalized = key.lower().replace(" ", "").replace("_", "")
        original = lower_map.get(normalized)
        if original is not None:
            return row[original]
    return default
