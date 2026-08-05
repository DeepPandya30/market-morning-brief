"""Price-history derived analytics: NIFTY 50 pivot table and index indicators.

Everything here is computed from daily OHLC pulled in bulk from Yahoo Finance.
NSE's own equity-stockIndices endpoint is blocked from datacenter IPs (the same
reason the option-chain fetch has fallbacks), so yfinance is the primary source
for constituent prices as well as the index series.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd
import yfinance as yf

from .config import (
    INDEX_SERIES_BARS,
    INDEX_TECHNICAL_TICKERS,
    LOOKBACK_SESSIONS,
    MA_PERIODS,
    NIFTY50_CONSTITUENTS,
)


def _round(value: Any, digits: int = 2) -> float | None:
    """Coerce a pandas/numpy scalar to a JSON-safe rounded float."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return round(number, digits)


def _download(tickers: list[str], period: str) -> pd.DataFrame:
    return yf.download(
        tickers,
        period=period,
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        progress=False,
        threads=True,
    )


def _extract(frame: pd.DataFrame, ticker: str) -> pd.DataFrame | None:
    """Pull one ticker's OHLC frame out of a (possibly multi-index) download."""
    if frame is None or frame.empty:
        return None
    try:
        sub = frame[ticker] if isinstance(frame.columns, pd.MultiIndex) else frame
    except KeyError:
        return None
    if "Close" not in sub.columns:
        return None
    sub = sub.dropna(subset=["Close"])
    return sub if not sub.empty else None


def _change_pct(closes: pd.Series, sessions: int) -> float | None:
    """Percent change over N completed sessions (5 ~ a week, 21 ~ a month)."""
    if len(closes) <= sessions:
        return None
    past = float(closes.iloc[-(sessions + 1)])
    if not past:
        return None
    return (float(closes.iloc[-1]) - past) / past * 100


def _rsi(closes: pd.Series, period: int = 14) -> pd.Series:
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    return 100 - (100 / (1 + rs))


def _macd(closes: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    fast = closes.ewm(span=12, adjust=False).mean()
    slow = closes.ewm(span=26, adjust=False).mean()
    macd = fast - slow
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal, macd - signal


def _bollinger(closes: pd.Series, period: int = 20, width: float = 2.0):
    mid = closes.rolling(period).mean()
    std = closes.rolling(period).std()
    return mid + width * std, mid, mid - width * std


def _atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = frame["High"], frame["Low"], frame["Close"]
    prev_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return true_range.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def _pivot_levels(high: float, low: float, close: float) -> dict[str, float | None]:
    """Classic (floor trader) pivot levels from the last completed session."""
    pivot = (high + low + close) / 3
    span = high - low
    return {
        "pivot": _round(pivot),
        "r1": _round(2 * pivot - low),
        "r2": _round(pivot + span),
        "r3": _round(high + 2 * (pivot - low)),
        "s1": _round(2 * pivot - high),
        "s2": _round(pivot - span),
        "s3": _round(low - 2 * (high - pivot)),
    }


def fetch_nifty50_pivots(warnings: list[str]) -> dict[str, Any]:
    """Pivot levels plus daily/weekly/monthly change for every NIFTY 50 stock."""
    result: dict[str, Any] = {"as_of": None, "rows": [], "sectors": []}
    symbols = list(NIFTY50_CONSTITUENTS)
    tickers = [f"{symbol}.NS" for symbol in symbols]

    try:
        frame = _download(tickers, period="6mo")
    except Exception as exc:
        warnings.append(f"nifty50_pivots: {exc}")
        return result

    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        name, sector = NIFTY50_CONSTITUENTS[symbol]
        sub = _extract(frame, f"{symbol}.NS")
        if sub is None or len(sub) < 2:
            warnings.append(f"nifty50_{symbol}: no usable price history")
            continue

        closes = sub["Close"]
        last = sub.iloc[-1]
        close = float(closes.iloc[-1])
        prev_close = float(closes.iloc[-2])
        high = float(last["High"])
        low = float(last["Low"])
        rsi_series = _rsi(closes)

        row: dict[str, Any] = {
            "symbol": symbol,
            "name": name,
            "sector": sector,
            "date": str(sub.index[-1].date()),
            "close": _round(close),
            "prev_close": _round(prev_close),
            "high": _round(high),
            "low": _round(low),
            "change": _round(close - prev_close),
            "change_pct": _round((close - prev_close) / prev_close * 100 if prev_close else None),
            "week_pct": _round(_change_pct(closes, LOOKBACK_SESSIONS["week"])),
            "month_pct": _round(_change_pct(closes, LOOKBACK_SESSIONS["month"])),
            "rsi": _round(rsi_series.iloc[-1] if len(rsi_series) else None, 1),
            "volume": _round(last.get("Volume"), 0),
        }
        row.update(_pivot_levels(high, low, close))
        pivot = row.get("pivot")
        row["vs_pivot_pct"] = _round((close - pivot) / pivot * 100 if pivot else None)
        row["zone"] = _pivot_zone(close, row)
        rows.append(row)

    if not rows:
        warnings.append("nifty50_pivots: no constituent data returned")
        return result

    rows.sort(key=lambda r: r["change_pct"] if r["change_pct"] is not None else -999999, reverse=True)
    result["rows"] = rows
    result["as_of"] = rows[0]["date"]
    result["sectors"] = _sector_rollup(rows)
    result["breadth"] = _breadth(rows)
    return result


def _pivot_zone(close: float, levels: dict[str, Any]) -> str:
    """Which pivot band the last close sits in — the trade-planning read."""
    r1, r2, s1, s2, pivot = (levels.get(k) for k in ("r1", "r2", "s1", "s2", "pivot"))
    if r2 is not None and close >= r2:
        return "Above R2"
    if r1 is not None and close >= r1:
        return "R1 - R2"
    if pivot is not None and close >= pivot:
        return "Pivot - R1"
    if s1 is not None and close >= s1:
        return "S1 - Pivot"
    if s2 is not None and close >= s2:
        return "S2 - S1"
    return "Below S2"


def _sector_rollup(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Average change per sector bucket — the pivot-table group-by view."""
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        buckets.setdefault(row["sector"], []).append(row)

    summary = []
    for sector, members in buckets.items():
        summary.append(
            {
                "sector": sector,
                "count": len(members),
                "change_pct": _round(_mean(members, "change_pct")),
                "week_pct": _round(_mean(members, "week_pct")),
                "month_pct": _round(_mean(members, "month_pct")),
                "advancing": sum(1 for m in members if (m.get("change_pct") or 0) > 0),
            }
        )
    summary.sort(key=lambda r: r["change_pct"] if r["change_pct"] is not None else -999999, reverse=True)
    return summary


def _mean(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [row[key] for row in rows if row.get(key) is not None]
    return sum(values) / len(values) if values else None


def _breadth(rows: list[dict[str, Any]]) -> dict[str, Any]:
    advancing = sum(1 for r in rows if (r.get("change_pct") or 0) > 0)
    declining = sum(1 for r in rows if (r.get("change_pct") or 0) < 0)
    return {
        "advancing": advancing,
        "declining": declining,
        "unchanged": len(rows) - advancing - declining,
        "above_pivot": sum(1 for r in rows if r.get("vs_pivot_pct") is not None and r["vs_pivot_pct"] >= 0),
        "avg_change_pct": _round(_mean(rows, "change_pct")),
        "avg_week_pct": _round(_mean(rows, "week_pct")),
        "avg_month_pct": _round(_mean(rows, "month_pct")),
    }


def fetch_index_technicals(warnings: list[str]) -> dict[str, Any]:
    """Moving averages, oscillators and chart series for Nifty and Bank Nifty."""
    result: dict[str, Any] = {}
    tickers = list(INDEX_TECHNICAL_TICKERS.values())

    try:
        frame = _download(tickers, period="2y")
    except Exception as exc:
        warnings.append(f"index_technicals: {exc}")
        return result

    for label, ticker in INDEX_TECHNICAL_TICKERS.items():
        sub = _extract(frame, ticker)
        if sub is None or len(sub) < 30:
            warnings.append(f"index_technicals_{label}: insufficient history for {ticker}")
            continue
        result[label] = _index_snapshot(label, ticker, sub)
    return result


def _index_snapshot(label: str, ticker: str, frame: pd.DataFrame) -> dict[str, Any]:
    closes = frame["Close"]
    close = float(closes.iloc[-1])
    prev_close = float(closes.iloc[-2])

    smas = {period: closes.rolling(period).mean() for period in MA_PERIODS}
    emas = {period: closes.ewm(span=period, adjust=False).mean() for period in MA_PERIODS}
    rsi = _rsi(closes)
    macd, signal, hist = _macd(closes)
    bb_upper, bb_mid, bb_lower = _bollinger(closes)
    atr = _atr(frame)

    moving_averages = []
    for period in MA_PERIODS:
        sma_value = _round(smas[period].iloc[-1])
        moving_averages.append(
            {
                "period": period,
                "sma": sma_value,
                "ema": _round(emas[period].iloc[-1]),
                "distance_pct": _round((close - sma_value) / sma_value * 100 if sma_value else None),
                "position": "Above" if sma_value is not None and close >= sma_value else "Below" if sma_value is not None else "N/A",
            }
        )

    last_macd = _round(macd.iloc[-1])
    last_signal = _round(signal.iloc[-1])
    last_rsi = _round(rsi.iloc[-1], 1)
    upper, lower = _round(bb_upper.iloc[-1]), _round(bb_lower.iloc[-1])

    indicators = [
        {
            "name": "RSI (14)",
            "value": last_rsi,
            "status": _rsi_status(last_rsi),
            "note": "Overbought above 70, oversold below 30",
        },
        {
            "name": "MACD (12,26,9)",
            "value": last_macd,
            "status": "Bullish" if last_macd is not None and last_signal is not None and last_macd >= last_signal else "Bearish" if last_macd is not None else "N/A",
            "note": f"Signal {last_signal if last_signal is not None else 'N/A'} · Histogram {_round(hist.iloc[-1])}",
        },
        {
            "name": "Bollinger (20,2)",
            "value": _round(bb_mid.iloc[-1]),
            "status": _bollinger_status(close, upper, lower),
            "note": f"Upper {upper if upper is not None else 'N/A'} · Lower {lower if lower is not None else 'N/A'}",
        },
        {
            "name": "ATR (14)",
            "value": _round(atr.iloc[-1]),
            "status": "Volatility",
            "note": f"{_round(atr.iloc[-1] / close * 100 if close else None)}% of spot — expected daily range",
        },
    ]

    snapshot = {
        "label": label,
        "ticker": ticker,
        "date": str(frame.index[-1].date()),
        "close": _round(close),
        "change": _round(close - prev_close),
        "change_pct": _round((close - prev_close) / prev_close * 100 if prev_close else None),
        "week_pct": _round(_change_pct(closes, LOOKBACK_SESSIONS["week"])),
        "month_pct": _round(_change_pct(closes, LOOKBACK_SESSIONS["month"])),
        "year_high": _round(closes.tail(250).max()),
        "year_low": _round(closes.tail(250).min()),
        "moving_averages": moving_averages,
        "indicators": indicators,
        "trend": _ma_trend(close, moving_averages),
        "series": _chart_series(frame, closes, smas, rsi, macd, signal, hist, bb_upper, bb_lower),
    }
    snapshot.update(
        {
            "levels": _pivot_levels(float(frame["High"].iloc[-1]), float(frame["Low"].iloc[-1]), close),
        }
    )
    return snapshot


def _rsi_status(value: float | None) -> str:
    if value is None:
        return "N/A"
    if value >= 70:
        return "Overbought"
    if value <= 30:
        return "Oversold"
    if value >= 55:
        return "Bullish"
    if value <= 45:
        return "Bearish"
    return "Neutral"


def _bollinger_status(close: float, upper: float | None, lower: float | None) -> str:
    if upper is None or lower is None:
        return "N/A"
    if close >= upper:
        return "Upper band breakout"
    if close <= lower:
        return "Lower band breakdown"
    return "Inside bands"


def _ma_trend(close: float, moving_averages: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarise price against the MA stack into one headline verdict."""
    available = [ma for ma in moving_averages if ma["sma"] is not None]
    if not available:
        return {"label": "N/A", "above": 0, "total": 0, "note": "Not enough history"}
    above = sum(1 for ma in available if close >= ma["sma"])
    ratio = above / len(available)
    if ratio == 1:
        label = "Strong uptrend"
    elif ratio >= 0.5:
        label = "Mild uptrend"
    elif ratio > 0:
        label = "Mild downtrend"
    else:
        label = "Strong downtrend"
    return {
        "label": label,
        "above": above,
        "total": len(available),
        "note": f"Spot above {above} of {len(available)} moving averages",
    }


def _chart_series(
    frame: pd.DataFrame,
    closes: pd.Series,
    smas: dict[int, pd.Series],
    rsi: pd.Series,
    macd: pd.Series,
    signal: pd.Series,
    hist: pd.Series,
    bb_upper: pd.Series,
    bb_lower: pd.Series,
) -> list[dict[str, Any]]:
    """Trailing window of price + indicator values for the dashboard charts."""
    tail = min(INDEX_SERIES_BARS, len(frame))
    dates = [str(value.date()) for value in frame.index[-tail:]]
    series = []
    for offset, date in enumerate(dates):
        idx = len(frame) - tail + offset
        point = {
            "date": date,
            "close": _round(closes.iloc[idx]),
            "rsi": _round(rsi.iloc[idx], 1),
            "macd": _round(macd.iloc[idx]),
            "signal": _round(signal.iloc[idx]),
            "hist": _round(hist.iloc[idx]),
            "bb_upper": _round(bb_upper.iloc[idx]),
            "bb_lower": _round(bb_lower.iloc[idx]),
        }
        for period, values in smas.items():
            point[f"sma{period}"] = _round(values.iloc[idx])
        series.append(point)
    return series
