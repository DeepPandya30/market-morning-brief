from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any
import feedparser
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf
from .config import NEWS_FEEDS, NEWS_KEYWORDS

from .config import (
    ASIA_MARKETS,
    COMMODITY_TICKERS,
    CRYPTO_TICKERS,
    CURRENCY_TICKERS,
    EUROPE_MARKETS,
    GLOBAL_MARKET_TICKERS,
    NSE_ENDPOINTS,
    OPTION_CHAIN_REFERERS,
    SECTOR_KEYWORDS,
    US_MARKETS,
)
from .nse_client import NSEClient
from .utils import safe_get, to_float


def fetch_global_markets(warnings: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, ticker in GLOBAL_MARKET_TICKERS.items():
        try:
            data = yf.Ticker(ticker).history(period="5d", interval="1d", auto_adjust=False)
            if data.empty or "Close" not in data.columns:
                warnings.append(f"global_{name}: no data returned for {ticker}")
                continue
            data = data.dropna(subset=["Close"])
            if len(data) < 2:
                warnings.append(f"global_{name}: insufficient close history for {ticker}")
                continue
            latest = float(data["Close"].iloc[-1])
            previous = float(data["Close"].iloc[-2])
            change = latest - previous
            change_pct = (change / previous) * 100 if previous else None
            region = "US" if name in US_MARKETS else "Europe" if name in EUROPE_MARKETS else "Asia"
            rows.append(
                {
                    "name": name,
                    "ticker": ticker,
                    "region": region,
                    "close": latest,
                    "change": change,
                    "change_pct": change_pct,
                    "date": str(data.index[-1].date()),
                }
            )
        except Exception as exc:
            warnings.append(f"global_{name}: {exc}")
    return rows


def fetch_yfinance_group(
    tickers: dict[str, str],
    group_name: str,
    warnings: list[str],
    period: str = "5d",
    interval: str = "1d",
) -> list[dict[str, Any]]:
    """Fetch a small market watchlist from Yahoo Finance/yfinance.

    Used for commodities, crypto, and currency pairs. The output shape is kept
    close to global_markets so the dashboard can render all groups consistently.
    """
    rows: list[dict[str, Any]] = []
    for name, ticker in tickers.items():
        try:
            data = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=False)
            if data.empty or "Close" not in data.columns:
                warnings.append(f"{group_name.lower()}_{name}: no data returned for {ticker}")
                continue
            data = data.dropna(subset=["Close"])
            if len(data) < 2:
                warnings.append(f"{group_name.lower()}_{name}: insufficient close history for {ticker}")
                continue
            latest = float(data["Close"].iloc[-1])
            previous = float(data["Close"].iloc[-2])
            change = latest - previous
            change_pct = (change / previous) * 100 if previous else None
            rows.append(
                {
                    "name": name,
                    "ticker": ticker,
                    "group": group_name,
                    "close": latest,
                    "change": change,
                    "change_pct": change_pct,
                    "date": str(data.index[-1].date()),
                }
            )
        except Exception as exc:
            warnings.append(f"{group_name.lower()}_{name}: {exc}")
    return rows


def fetch_nse_indices(client: NSEClient, warnings: list[str]) -> dict[str, Any]:
    result = {
        "indices": [],
        "sectors": [],
        "india_vix": None,
        "nifty_spot": None,
        "banknifty_spot": None,
        "gift_nifty": None,
    }
    try:
        raw = client.get_json(
            NSE_ENDPOINTS["all_indices"],
            referer="https://www.nseindia.com/market-data/live-market-indices",
        )
    except Exception as exc:
        warnings.append(f"nse_indices: {exc}")
        return result

    data = raw.get("data", raw if isinstance(raw, list) else [])
    if not isinstance(data, list):
        warnings.append("nse_indices: unexpected allIndices payload")
        return result

    rows: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = str(safe_get(item, ["index", "indexName", "name"], "")).strip()
        if not name:
            continue
        last = to_float(safe_get(item, ["last", "lastPrice", "ltp", "last traded price"]))
        change = to_float(safe_get(item, ["variation", "change", "changeValue"]))
        change_pct = to_float(safe_get(item, ["percentChange", "pChange", "perChange", "% Change"]))
        row = {
            "name": name,
            "last": last,
            "change": change,
            "change_pct": change_pct,
        }
        rows.append(row)

        upper_name = name.upper()
        if upper_name == "INDIA VIX":
            result["india_vix"] = row
        elif upper_name == "NIFTY 50":
            result["nifty_spot"] = last
        elif upper_name in {"NIFTY BANK", "BANK NIFTY", "NIFTY BANK INDEX"}:
            result["banknifty_spot"] = last
        elif "GIFT" in upper_name:
            result["gift_nifty"] = row

        if upper_name in SECTOR_KEYWORDS:
            result["sectors"].append(row)

    result["indices"] = rows
    result["sectors"] = sorted(
        result["sectors"],
        key=lambda x: x["change_pct"] if x.get("change_pct") is not None else -999999,
        reverse=True,
    )
    return result


def fetch_fii_dii(client: NSEClient, warnings: list[str]) -> dict[str, Any]:
    raw = None
    source = "nse"
    try:
        raw = client.get_json(NSE_ENDPOINTS["fii_dii"], referer="https://www.nseindia.com/reports/fii-dii")
    except Exception as exc:
        warnings.append(f"fii_dii_nse: {exc}")
        try:
            from nsepython import nse_fiidii

            raw = nse_fiidii()
            source = "nsepython"
        except Exception as fallback_exc:
            warnings.append(f"fii_dii_nsepython: {fallback_exc}")
            return {"source": None, "fii_net": None, "dii_net": None, "rows": []}

    rows = _find_dict_rows(raw)
    parsed_rows = []
    fii_net = None
    dii_net = None
    for row in rows:
        category = str(safe_get(row, ["category", "Category", "investorType", "name"], "")).upper()
        buy = to_float(safe_get(row, ["buyValue", "buy", "grossBuy", "Buy Value", "gross_purchase"], None))
        sell = to_float(safe_get(row, ["sellValue", "sell", "grossSell", "Sell Value", "gross_sales"], None))
        net = to_float(safe_get(row, ["netValue", "net", "netValueCr", "Net Value", "net_investment"], None))
        if net is None and buy is not None and sell is not None:
            net = buy - sell
        if not category or net is None:
            continue
        clean = {"category": category, "buy": buy, "sell": sell, "net": net}
        parsed_rows.append(clean)
        if "FII" in category or "FPI" in category:
            fii_net = net
        elif "DII" in category:
            dii_net = net

    if fii_net is None and dii_net is None:
        warnings.append(f"fii_dii: could not parse FII/DII net values from {source} payload")
    return {"source": source, "fii_net": fii_net, "dii_net": dii_net, "rows": parsed_rows}


def fetch_option_chain(
    client: NSEClient,
    symbol: str,
    warnings: list[str],
    fallback_spot: float | None = None,
) -> dict[str, Any]:
    symbol = symbol.upper().replace(" ", "")
    referer = OPTION_CHAIN_REFERERS.get(symbol, "https://www.nseindia.com/option-chain")
    attempts: list[tuple[str, Any]] = []

    for endpoint_key, label in [("option_chain_next", "nse_nextapi"), ("option_chain_old", "nse_old")]:
        try:
            raw = client.get_json(NSE_ENDPOINTS[endpoint_key].format(symbol=symbol), referer=referer)
            result = normalize_option_chain(raw, symbol, label, fallback_spot)
            if result["rows"]:
                return result
            attempts.append((label, "payload received but no CE/PE rows were detected"))
        except Exception as exc:
            attempts.append((label, exc))

    try:
        from nsepython import nse_optionchain_scrapper

        raw = nse_optionchain_scrapper(symbol)
        result = normalize_option_chain(raw, symbol, "nsepython", fallback_spot)
        if result["rows"]:
            return result
        attempts.append(("nsepython", "payload received but no CE/PE rows were detected"))
    except Exception as exc:
        attempts.append(("nsepython", exc))

    short_errors = "; ".join(f"{label}: {err}" for label, err in attempts[-3:])
    warnings.append(f"option_chain_{symbol}: unavailable after all sources ({short_errors})")
    return _empty_option_result(symbol, None)


def normalize_option_chain(raw: Any, symbol: str, source: str, fallback_spot: float | None = None) -> dict[str, Any]:
    rows_raw = _find_option_rows(raw)
    rows_raw = _combine_single_leg_option_rows(rows_raw)

    parsed_rows: list[dict[str, Any]] = []
    for row in rows_raw:
        parsed = _parse_option_row(row)
        if parsed:
            parsed_rows.append(parsed)

    parsed_rows = _filter_nearest_expiry(parsed_rows)

    spot = _extract_underlying_value(raw) or fallback_spot
    total_call_oi = sum(row.get("call_oi") or 0 for row in parsed_rows)
    total_put_oi = sum(row.get("put_oi") or 0 for row in parsed_rows)
    pcr = total_put_oi / total_call_oi if total_call_oi else None

    resistance_row = max(parsed_rows, key=lambda x: x.get("call_oi") or 0, default=None)
    support_row = max(parsed_rows, key=lambda x: x.get("put_oi") or 0, default=None)

    if spot is not None:
        below_spot = [row for row in parsed_rows if row["strike"] <= spot]
        above_spot = [row for row in parsed_rows if row["strike"] >= spot]
        support_row = max(below_spot, key=lambda x: x.get("put_oi") or 0, default=support_row)
        resistance_row = max(above_spot, key=lambda x: x.get("call_oi") or 0, default=resistance_row)

    return {
        "symbol": symbol,
        "source": source,
        "underlying": spot,
        "pcr": pcr,
        "total_call_oi": total_call_oi,
        "total_put_oi": total_put_oi,
        "support": support_row["strike"] if support_row else None,
        "resistance": resistance_row["strike"] if resistance_row else None,
        "support_put_oi": support_row.get("put_oi") if support_row else None,
        "resistance_call_oi": resistance_row.get("call_oi") if resistance_row else None,
        "expiry": support_row.get("expiry") if support_row else resistance_row.get("expiry") if resistance_row else None,
        "rows": parsed_rows,
    }


def _empty_option_result(symbol: str, source: str | None) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "source": source,
        "underlying": None,
        "pcr": None,
        "total_call_oi": None,
        "total_put_oi": None,
        "support": None,
        "resistance": None,
        "support_put_oi": None,
        "resistance_call_oi": None,
        "rows": [],
    }


def _parse_option_row(row: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None

    option_type = str(safe_get(row, ["optionType", "option_type", "type"], "")).upper()
    ce = safe_get(row, ["CE", "ce", "call", "CALL"], {})
    pe = safe_get(row, ["PE", "pe", "put", "PUT"], {})

    if not isinstance(ce, dict):
        ce = {}
    if not isinstance(pe, dict):
        pe = {}

    if option_type == "CE" and not ce:
        ce = row
    elif option_type == "PE" and not pe:
        pe = row

    strike = to_float(
        safe_get(
            row,
            ["strikePrice", "strike", "Strike Price", "STRIKE", "strike_price"],
            safe_get(ce, ["strikePrice", "strike"], safe_get(pe, ["strikePrice", "strike"])),
        )
    )
    if strike is None:
        return None

    call_oi = to_float(
        safe_get(
            ce,
            ["openInterest", "oi", "Open Interest", "open_interest", "openInterestContracts"],
            safe_get(row, ["CE_openInterest", "CE OI", "call_oi", "CALL_OI", "Call OI"]),
        ),
        0,
    )
    put_oi = to_float(
        safe_get(
            pe,
            ["openInterest", "oi", "Open Interest", "open_interest", "openInterestContracts"],
            safe_get(row, ["PE_openInterest", "PE OI", "put_oi", "PUT_OI", "Put OI"]),
        ),
        0,
    )
    call_change_oi = to_float(
        safe_get(
            ce,
            ["changeinOpenInterest", "changeInOI", "change_oi", "changeInOpenInterest"],
            safe_get(row, ["CE_changeinOpenInterest", "call_change_oi"]),
        ),
        0,
    )
    put_change_oi = to_float(
        safe_get(
            pe,
            ["changeinOpenInterest", "changeInOI", "change_oi", "changeInOpenInterest"],
            safe_get(row, ["PE_changeinOpenInterest", "put_change_oi"]),
        ),
        0,
    )
    if not call_oi and not put_oi:
        return None
    return {
        "strike": strike,
        "expiry": safe_get(row, ["expiryDate", "expiry", "Expiry Date"], safe_get(ce, ["expiryDate", "expiry"], safe_get(pe, ["expiryDate", "expiry"]))),
        "call_oi": call_oi,
        "put_oi": put_oi,
        "call_change_oi": call_change_oi,
        "put_change_oi": put_change_oi,
    }

def _extract_underlying_value(obj: Any) -> float | None:
    if isinstance(obj, dict):
        value = to_float(
            safe_get(
                obj,
                ["underlyingValue", "underlying", "lastPrice", "spot", "indexValue"],
            )
        )
        if value is not None:
            return value
        records = obj.get("records")
        if isinstance(records, dict):
            value = to_float(safe_get(records, ["underlyingValue", "underlying", "lastPrice"]))
            if value is not None:
                return value
        for child in obj.values():
            found = _extract_underlying_value(child)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for child in obj:
            found = _extract_underlying_value(child)
            if found is not None:
                return found
    return None


def _find_option_rows(obj: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    if isinstance(obj, pd.DataFrame):
        return obj.to_dict("records")

    if isinstance(obj, list):
        dict_items = [item for item in obj if isinstance(item, dict)]
        if dict_items and any(_looks_like_option_row(item) for item in dict_items):
            rows.extend(dict_items)
        for item in obj:
            if isinstance(item, (dict, list, pd.DataFrame)):
                rows.extend(_find_option_rows(item))
        return _dedupe_rows(rows)

    if isinstance(obj, dict):
        if _looks_like_option_row(obj):
            rows.append(obj)
        for key in ["data", "filtered", "records", "optionChain", "option_chain", "payload", "stocks"]:
            value = obj.get(key)
            if value is not None:
                rows.extend(_find_option_rows(value))
        for value in obj.values():
            if isinstance(value, (dict, list, pd.DataFrame)):
                rows.extend(_find_option_rows(value))
        return _dedupe_rows(rows)

    return rows


def _looks_like_option_row(row: dict[str, Any]) -> bool:
    keys = {str(k).lower().replace(" ", "").replace("_", "") for k in row.keys()}
    if "ce" in keys or "pe" in keys:
        return True
    if "optiontype" in keys and "strikeprice" in keys:
        return True
    flat_markers = {
        "ceopeninterest",
        "peopeninterest",
        "calloi",
        "putoi",
        "ceoi",
        "peoi",
    }
    return bool(flat_markers & keys)


def _combine_single_leg_option_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    combined: dict[tuple[Any, Any], dict[str, Any]] = {}
    passthrough: list[dict[str, Any]] = []

    for row in rows:
        option_type = str(safe_get(row, ["optionType", "option_type", "type"], "")).upper()
        strike = safe_get(row, ["strikePrice", "strike", "Strike Price", "strike_price"])
        expiry = safe_get(row, ["expiryDate", "expiry", "Expiry Date"])

        if option_type in {"CE", "PE"} and strike is not None:
            key = (to_float(strike, 0), expiry or "")
            if key not in combined:
                combined[key] = {"strikePrice": strike, "expiryDate": expiry, "CE": {}, "PE": {}}
            combined[key][option_type] = row
        else:
            passthrough.append(row)

    return passthrough + list(combined.values())


def _parse_expiry_date(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ["%d-%b-%Y", "%d-%B-%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"]:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _filter_nearest_expiry(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dated = [(row, _parse_expiry_date(row.get("expiry"))) for row in rows if row.get("expiry")]
    valid_dates = sorted({date for _, date in dated if date is not None})
    if not valid_dates:
        return rows
    nearest = valid_dates[0]
    return [row for row, date in dated if date == nearest]

def _dedupe_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[int] = set()
    for row in rows:
        marker = id(row)
        if marker not in seen:
            seen.add(marker)
            output.append(row)
    return output


def _find_dict_rows(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, pd.DataFrame):
        return raw.to_dict("records")
    if isinstance(raw, list):
        rows = []
        for item in raw:
            if isinstance(item, dict):
                rows.append(item)
            else:
                rows.extend(_find_dict_rows(item))
        return rows
    if isinstance(raw, dict):
        rows = []
        for key in ["data", "rows", "result", "payload"]:
            if key in raw:
                rows.extend(_find_dict_rows(raw[key]))
        if not rows and raw:
            rows.append(raw)
        return rows
    return []


def build_data_bundle() -> dict[str, Any]:
    warnings: list[str] = []
    
    client = NSEClient()

    global_markets = fetch_global_markets(warnings)
    commodities = fetch_yfinance_group(COMMODITY_TICKERS, "Commodities", warnings)
    crypto = fetch_yfinance_group(CRYPTO_TICKERS, "Crypto", warnings)
    currencies = fetch_yfinance_group(CURRENCY_TICKERS, "Currency", warnings)
    nse_indices = fetch_nse_indices(client, warnings)
    fii_dii = fetch_fii_dii(client, warnings)
    nifty_options = fetch_option_chain(client, "NIFTY", warnings, nse_indices.get("nifty_spot"))
    banknifty_options = fetch_option_chain(client, "BANKNIFTY", warnings, nse_indices.get("banknifty_spot"))
    

    return {
        "global_markets": global_markets,
        "commodities": commodities,
        "crypto": crypto,
        "currencies": currencies,
        "nse_indices": nse_indices,
        "fii_dii": fii_dii,
        "option_chains": {
            "NIFTY": nifty_options,
            "BANKNIFTY": banknifty_options,
            "market_news": fetch_market_news(limit=10),
        },
        "warnings": warnings,
    }

def fetch_market_news(limit: int = 10) -> list[dict]:
    news_items: list[dict] = []
    seen_links: set[str] = set()

    for feed in NEWS_FEEDS:
        feed_name = feed.get("name", "News")
        feed_url = feed.get("url")

        if not feed_url:
            continue

        try:
            parsed = feedparser.parse(feed_url)

            for entry in parsed.entries:
                title = str(entry.get("title", "")).strip()
                link = str(entry.get("link", "")).strip()
                summary = str(entry.get("summary", "")).strip()

                if not title or not link:
                    continue

                if link in seen_links:
                    continue

                text_blob = f"{title} {summary}".lower()
                relevance_score = sum(1 for keyword in NEWS_KEYWORDS if keyword.lower() in text_blob)

                published = (
                    entry.get("published")
                    or entry.get("updated")
                    or ""
                )

                news_items.append(
                    {
                        "title": title,
                        "link": link,
                        "summary": _clean_news_summary(summary),
                        "published": published,
                        "source": feed_name,
                        "relevance_score": relevance_score,
                    }
                )

                seen_links.add(link)

        except Exception as exc:
            # Do not fail whole dashboard if news fails
            news_items.append(
                {
                    "title": "News fetch warning",
                    "link": "",
                    "summary": f"{feed_name} failed: {exc}",
                    "published": "",
                    "source": feed_name,
                    "relevance_score": -1,
                    "is_warning": True,
                }
            )

    news_items = sorted(
        news_items,
        key=lambda row: (
            row.get("is_warning", False),
            -(row.get("relevance_score") or 0),
            row.get("published") or "",
        ),
    )

    return news_items[:limit]


def _clean_news_summary(summary: str, max_len: int = 220) -> str:
    import re

    text = re.sub(r"<[^>]+>", " ", summary or "")
    text = re.sub(r"\s+", " ", text).strip()

    if len(text) > max_len:
        return text[:max_len].rstrip() + "..."

    return text