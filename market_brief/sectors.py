"""Sector tagging for arbitrary NSE symbols.

The event-calendar feed names companies but not their industry, so sectors are
resolved in three steps, cheapest first:

1. NIFTY50_CONSTITUENTS — the index names already carry a hand-kept bucket.
2. data/processed/sector_map.json — everything looked up on a previous run.
3. Yahoo Finance company profiles — one HTTP call per never-seen symbol, run in
   a small thread pool and capped per run, then written back to the cache.

Because the cache is committed with the rest of data/processed, a warm repo
resolves almost every symbol with no network calls.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import yfinance as yf

from .config import (
    NIFTY50_CONSTITUENTS,
    SECTOR_CACHE_PATH,
    SECTOR_LOOKUP_MAX_NEW,
    SECTOR_LOOKUP_WORKERS,
    SECTOR_UNKNOWN,
    YF_INDUSTRY_OVERRIDES,
    YF_SECTOR_BUCKETS,
)


def _load_cache() -> dict[str, str]:
    try:
        raw = json.loads(SECTOR_CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {
        str(symbol).upper(): str(sector)
        for symbol, sector in raw.items()
        if isinstance(sector, str) and sector
    }


def _save_cache(cache: dict[str, str]) -> None:
    SECTOR_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SECTOR_CACHE_PATH.write_text(
        json.dumps(dict(sorted(cache.items())), indent=2) + "\n", encoding="utf-8"
    )


def bucket_for(sector: str | None, industry: str | None) -> str:
    """Fold a Yahoo sector/industry pair into this dashboard's bucket names."""
    industry_text = str(industry or "").lower()
    for bucket, keywords in YF_INDUSTRY_OVERRIDES:
        if any(keyword in industry_text for keyword in keywords):
            return bucket
    return YF_SECTOR_BUCKETS.get(str(sector or "").strip(), SECTOR_UNKNOWN)


def _lookup(symbol: str) -> tuple[str, str | None]:
    """Fetch one symbol's sector bucket from Yahoo. Never raises."""
    for suffix in (".NS", ".BO"):
        try:
            info = yf.Ticker(f"{symbol}{suffix}").get_info() or {}
        except Exception:
            continue
        bucket = bucket_for(info.get("sector"), info.get("industry"))
        if bucket != SECTOR_UNKNOWN:
            return symbol, bucket
    return symbol, None


def resolve_sectors(symbols: list[str], warnings: list[str]) -> dict[str, str]:
    """Map each symbol to a sector bucket, warming the on-disk cache as it goes.

    Symbols that cannot be classified come back as SECTOR_UNKNOWN rather than
    being dropped, so the events table always has a value to show.
    """
    wanted = [symbol.upper() for symbol in dict.fromkeys(s for s in symbols if s)]
    resolved = {
        symbol: NIFTY50_CONSTITUENTS[symbol][1]
        for symbol in wanted
        if symbol in NIFTY50_CONSTITUENTS
    }

    cache = _load_cache()
    missing = []
    for symbol in wanted:
        if symbol in resolved:
            continue
        if symbol in cache:
            resolved[symbol] = cache[symbol]
        else:
            missing.append(symbol)

    if missing:
        capped = missing[:SECTOR_LOOKUP_MAX_NEW]
        if len(missing) > len(capped):
            warnings.append(
                f"event_sectors: {len(missing) - len(capped)} symbols left unclassified "
                f"this run (lookup cap {SECTOR_LOOKUP_MAX_NEW}); the cache picks them up next run"
            )
        found = 0
        with ThreadPoolExecutor(max_workers=SECTOR_LOOKUP_WORKERS) as pool:
            for symbol, bucket in pool.map(_lookup, capped):
                if bucket:
                    resolved[symbol] = cache[symbol] = bucket
                    found += 1
        if found:
            try:
                _save_cache(cache)
            except OSError as exc:
                warnings.append(f"event_sectors: could not write sector cache: {exc}")
        if found < len(capped):
            warnings.append(
                f"event_sectors: no Yahoo profile for {len(capped) - found} of "
                f"{len(capped)} new symbols"
            )

    return {symbol: resolved.get(symbol, SECTOR_UNKNOWN) for symbol in wanted}


def sector_counts(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sector histogram for the events list, biggest bucket first.

    Unclassified is always sorted last so it never leads the chip row.
    """
    counts: dict[str, int] = {}
    for event in events:
        name = event.get("sector") or SECTOR_UNKNOWN
        counts[name] = counts.get(name, 0) + 1
    ordered = sorted(
        counts.items(), key=lambda kv: (kv[0] == SECTOR_UNKNOWN, -kv[1], kv[0])
    )
    return [{"name": name, "count": count} for name, count in ordered]
