"""Five-factor core bias model.

A deliberately small, hand-specified rule set that runs alongside the broader
twelve-signal composite in :mod:`market_brief.scoring`. Every factor resolves to
a raw -1, 0 or +1, then carries a weight so that a slow regime read (the moving
average stack) counts for more than a fast, noisy one (crude):

1. Trend (DMA)  x2.0  — full bullish/bearish moving-average stack, else neutral.
2. FII / DII    x1.5  — FII direction, with DII absorption deciding the seller case.
3. India VIX    x1.0  — percentile of its own trailing range, not a fixed level.
4. US market    x1.0  — S&P 500 / Nasdaq last close, with a neutral band.
5. Crude oil    x0.5  — Brent / WTI daily move, gated on the US read.

A factor whose inputs are missing scores 0 and is marked unavailable, so a
failed fetch never pushes the bias in either direction. Stale FII/DII data is
treated the same way rather than being scored as if it were current.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from .config import VIX_CALM_PERCENTILE, VIX_FEAR_PERCENTILE
from .utils import now_ist

# Factor weights, so a tweak is a one-line edit. The maximum reachable score is
# their sum, which keeps the bias thresholds below expressed as fractions.
FACTOR_WEIGHTS = {
    "Trend (DMA)": 2.0,
    "FII / DII flow": 1.5,
    "India VIX": 1.0,
    "US market": 1.0,
    "Crude oil": 0.5,
}
MAX_SCORE = sum(FACTOR_WEIGHTS.values())

# Bias label cut-offs, as a fraction of MAX_SCORE so re-weighting a factor does
# not silently shift what "Bullish" means.
STRONG_RATIO = 0.5
MILD_RATIO = 0.15

# Fallback thresholds, used only when the India VIX trailing series is missing.
VIX_CALM = 15.0
VIX_FEARFUL = 20.0

# The US factor needs a positive move to read bullish, not merely the absence of
# a drop -- otherwise a flat tape scores +1 and the model carries a long tilt.
US_DROP_PCT = -1.0
US_RISE_PCT = 0.3

CRUDE_MOVE_PCT = 2.0

# NSE publishes the previous session's flows, so one business day of lag is
# expected. More than this means a holiday gap or a stale cache.
MAX_FLOW_LAG_SESSIONS = 2

TREND_PERIODS = (20, 50, 200)
US_HEADLINE_INDICES = ("S&P 500", "Nasdaq")
CRUDE_NAMES = ("Brent Oil", "Crude Oil WTI")


def score_core_bias(data: dict[str, Any], as_of: date | None = None) -> dict[str, Any]:
    """Run the five factors over a fetched data bundle."""
    technicals = (data.get("index_technicals") or {}).get("NIFTY 50") or {}
    as_of = as_of or now_ist().date()

    trend = _factor_trend(technicals)
    flows = _factor_flows(data.get("fii_dii") or {}, as_of)
    vix = _factor_vix(
        (data.get("nse_indices") or {}).get("india_vix"),
        data.get("vix_regime") or {},
    )
    us = _factor_us_market(data.get("global_markets") or [])
    # Cheap crude only reads as a tailwind when the US tape is not already
    # bearish — otherwise the fall is demand destruction, not an India positive.
    crude = _factor_crude(data.get("commodities") or [], us)

    factors = [trend, flows, vix, us, crude]
    for factor in factors:
        factor["weight"] = FACTOR_WEIGHTS[factor["name"]]
        factor["weighted"] = round(factor["score"] * factor["weight"], 2)

    total = round(sum(factor["weighted"] for factor in factors), 2)
    available = [factor for factor in factors if factor["available"]]
    bullish = sum(1 for factor in factors if factor["score"] > 0)
    bearish = sum(1 for factor in factors if factor["score"] < 0)

    return {
        "score": total,
        "max_score": MAX_SCORE,
        "bias": _bias_label(total),
        "confidence": _confidence(available),
        "available": len(available),
        "total_factors": len(factors),
        "available_weight": round(sum(factor["weight"] for factor in available), 2),
        "bullish_count": bullish,
        "bearish_count": bearish,
        "neutral_count": len(factors) - bullish - bearish,
        "factors": factors,
    }


def _factor_trend(technicals: dict[str, Any]) -> dict[str, Any]:
    """Price against the 20/50/200 DMA stack on NIFTY 50."""
    close = technicals.get("close")
    stack = {
        ma.get("period"): ma.get("sma")
        for ma in technicals.get("moving_averages") or []
        if ma.get("period") in TREND_PERIODS and ma.get("sma") is not None
    }
    if close is None or len(stack) != len(TREND_PERIODS):
        return _unavailable("Trend (DMA)", "NIFTY 50 close or the 20/50/200 DMA stack was not available.")

    dma20, dma50, dma200 = (stack[period] for period in TREND_PERIODS)
    levels = f"spot {close:,.2f} · 20DMA {dma20:,.2f} · 50DMA {dma50:,.2f} · 200DMA {dma200:,.2f}"

    if close > dma20 > dma50 > dma200:
        return _factor("Trend (DMA)", 1, "Price > 20 > 50 > 200 DMA", f"Full bullish stack — {levels}.")
    if close < dma20 < dma50 < dma200:
        return _factor("Trend (DMA)", -1, "Price < 20 < 50 < 200 DMA", f"Full bearish stack — {levels}.")
    return _factor("Trend (DMA)", 0, "Mixed DMA stack", f"Stack is not cleanly aligned — {levels}.")


def _factor_vix(vix: dict[str, Any] | None, regime: dict[str, Any]) -> dict[str, Any]:
    """India VIX against its own trailing range, falling back to fixed levels.

    A fixed "below 15" threshold is a constant in a low-volatility regime, so the
    percentile read is preferred whenever the trailing series is available.
    """
    percentile = regime.get("percentile")
    level = regime.get("level") if regime.get("level") is not None else (vix or {}).get("last")
    if level is None:
        return _unavailable("India VIX", "India VIX level was not available.")
    level = float(level)

    if percentile is None:
        # Fallback path: the absolute thresholds, flagged in the rule text so a
        # reader knows the regime series was missing.
        if level < VIX_CALM:
            return _factor("India VIX", 1, f"VIX < {VIX_CALM:g} (no regime history)", f"India VIX at {level:.2f} — low-fear regime.")
        if level > VIX_FEARFUL:
            return _factor("India VIX", -1, f"VIX > {VIX_FEARFUL:g} (no regime history)", f"India VIX at {level:.2f} — elevated fear.")
        return _factor(
            "India VIX",
            0,
            f"VIX between {VIX_CALM:g} and {VIX_FEARFUL:g} (no regime history)",
            f"India VIX at {level:.2f} — neither calm nor fearful.",
        )

    percentile = float(percentile)
    # Phrased as a share rather than an ordinal, so no "73th" slips through.
    band = (
        f"India VIX at {level:.2f} — {percentile:.0f}% of its "
        f"{regime.get('lookback', 'trailing')} range sits below it ({regime.get('low')}–{regime.get('high')})"
    )
    if percentile <= VIX_CALM_PERCENTILE:
        return _factor("India VIX", 1, f"VIX in bottom {VIX_CALM_PERCENTILE:g}% of its range", f"{band} — calm for this regime.")
    if percentile >= VIX_FEAR_PERCENTILE:
        return _factor("India VIX", -1, f"VIX in top {100 - VIX_FEAR_PERCENTILE:g}% of its range", f"{band} — fearful for this regime.")
    return _factor("India VIX", 0, "VIX mid-range for its own regime", f"{band} — mid-range.")


def _factor_flows(flow: dict[str, Any], as_of: date) -> dict[str, Any]:
    """FII direction, with DII absorption deciding the FII-seller case."""
    fii = flow.get("fii_net")
    if fii is None:
        return _unavailable("FII / DII flow", "FII net flow was not available.")

    # NSE reports the previous session. Scoring a multi-session-old print as if
    # it were last night's flow is worse than not scoring it at all.
    data_date = _parse_date(flow.get("data_date"))
    if data_date is not None:
        lag = _business_days_between(data_date, as_of)
        if lag > MAX_FLOW_LAG_SESSIONS:
            return _unavailable(
                "FII / DII flow",
                f"FII/DII print is from {data_date}, {lag} sessions before {as_of} — too stale to score.",
            )

    dii = float(flow.get("dii_net")) if flow.get("dii_net") is not None else 0.0
    fii = float(fii)
    net = fii + dii
    session = f" (session {flow.get('data_date')})" if flow.get("data_date") else ""
    figures = f"FII {fii:+,.2f} Cr, DII {dii:+,.2f} Cr, net {net:+,.2f} Cr{session}"

    if fii > 0:
        return _factor("FII / DII flow", 1, "FII net buyer", f"FIIs bought — {figures}.")
    if net < 0:
        return _factor(
            "FII / DII flow",
            -1,
            "FII seller, DII did not absorb (net < 0)",
            f"FII selling outweighed DII buying — {figures}.",
        )
    return _factor(
        "FII / DII flow",
        0,
        "FII seller, DII absorbed it (net >= 0)",
        f"DIIs absorbed the FII selling — {figures}.",
    )


def _factor_us_market(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """S&P 500 / Nasdaq last close, with a neutral band around flat."""
    moves = {
        row.get("name"): row.get("change_pct")
        for row in rows
        if row.get("name") in US_HEADLINE_INDICES and row.get("change_pct") is not None
    }
    if not moves:
        return _unavailable("US market", "Neither S&P 500 nor Nasdaq change was available.")

    figures = " · ".join(f"{name} {float(value):+.2f}%" for name, value in moves.items())
    values = [float(value) for value in moves.values()]
    worst, best = min(values), max(values)

    # A 1% drawdown dominates, even if the other index closed higher.
    if worst <= US_DROP_PCT:
        return _factor(
            "US market",
            -1,
            f"S&P 500 or Nasdaq fell {abs(US_DROP_PCT):g}% or more",
            f"US tape closed sharply lower — {figures}.",
        )
    if best >= US_RISE_PCT:
        return _factor(
            "US market",
            1,
            f"S&P 500 or Nasdaq gained {US_RISE_PCT:g}% or more",
            f"US tape closed firmly higher — {figures}.",
        )
    return _factor(
        "US market",
        0,
        f"US indices between {US_DROP_PCT:g}% and +{US_RISE_PCT:g}%",
        f"US tape closed flat — {figures}.",
    )


def _factor_crude(rows: list[dict[str, Any]], us_factor: dict[str, Any]) -> dict[str, Any]:
    """Brent / WTI daily move. A crude slide only counts when the US tape held up."""
    moves = {
        row.get("name"): row.get("change_pct")
        for row in rows
        if row.get("name") in CRUDE_NAMES and row.get("change_pct") is not None
    }
    if not moves:
        return _unavailable("Crude oil", "Neither Brent nor WTI change was available.")

    figures = " · ".join(f"{name} {float(value):+.2f}%" for name, value in moves.items())
    # "Brent or WTI" — the larger move is the one that decides the factor.
    headline = max((float(value) for value in moves.values()), key=abs)

    if headline >= CRUDE_MOVE_PCT:
        return _factor(
            "Crude oil",
            -1,
            f"Crude up {CRUDE_MOVE_PCT:g}% or more",
            f"Crude spike raises India's import and inflation bill — {figures}.",
        )
    if headline <= -CRUDE_MOVE_PCT:
        if us_factor["score"] < 0:
            return _factor(
                "Crude oil",
                0,
                f"Crude down {CRUDE_MOVE_PCT:g}%+ but US market is bearish",
                f"Crude fell with a weak US tape, so it reads as demand fear rather than relief — {figures}.",
            )
        return _factor(
            "Crude oil",
            1,
            f"Crude down {CRUDE_MOVE_PCT:g}%+ with US market not bearish",
            f"Cheaper crude with a steady US tape is a clean India positive — {figures}.",
        )
    return _factor(
        "Crude oil",
        0,
        f"Crude move within +/-{CRUDE_MOVE_PCT:g}%",
        f"Crude move is too small to shift the bias — {figures}.",
    )


def _factor(name: str, score: int, rule: str, reason: str) -> dict[str, Any]:
    return {
        "name": name,
        "score": score,
        "status": "Bullish" if score > 0 else "Bearish" if score < 0 else "Neutral",
        "rule": rule,
        "reason": reason,
        "available": True,
    }


def _unavailable(name: str, reason: str) -> dict[str, Any]:
    return {
        "name": name,
        "score": 0,
        "status": "Unavailable",
        "rule": "No usable data",
        "reason": reason,
        "available": False,
    }


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d-%b-%Y", "%d %b %Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    return None


def _business_days_between(start: date, end: date) -> int:
    """Weekday count between two dates. Exchange holidays are not modelled, so a
    holiday-adjacent run reads one session staler than it truly is -- which errs
    toward not scoring, the safe direction."""
    if end <= start:
        return 0
    days = (end - start).days
    return sum(1 for offset in range(1, days + 1) if (start.toordinal() + offset - 1) % 7 < 5)


def _bias_label(score: float) -> str:
    ratio = score / MAX_SCORE if MAX_SCORE else 0
    if ratio >= STRONG_RATIO:
        return "Bullish"
    if ratio >= MILD_RATIO:
        return "Mild Bullish"
    if ratio <= -STRONG_RATIO:
        return "Bearish"
    if ratio <= -MILD_RATIO:
        return "Mild Bearish"
    return "Neutral / Range-bound"


def _confidence(available: list[dict[str, Any]]) -> str:
    """Confidence tracks how much of the model's weight actually had data."""
    covered = sum(factor["weight"] for factor in available) / MAX_SCORE if MAX_SCORE else 0
    if covered >= 0.95:
        return "High"
    if covered >= 0.6:
        return "Medium"
    return "Low"
