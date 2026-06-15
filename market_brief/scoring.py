from __future__ import annotations

from typing import Any

from .config import ASIA_MARKETS, EUROPE_MARKETS, US_MARKETS


def score_market(data: dict[str, Any]) -> dict[str, Any]:
    components: list[dict[str, Any]] = []

    gift = data.get("nse_indices", {}).get("gift_nifty")
    components.append(_score_gift_nifty(gift))

    global_rows = data.get("global_markets", [])
    components.append(_score_region(global_rows, "US", US_MARKETS))
    components.append(_score_region(global_rows, "Europe", EUROPE_MARKETS))
    components.append(_score_region(global_rows, "Asia", ASIA_MARKETS))

    components.append(_score_fii_dii(data.get("fii_dii", {})))
    components.append(_score_options(data.get("option_chains", {}).get("NIFTY", {}), "Nifty OI"))
    components.append(_score_options(data.get("option_chains", {}).get("BANKNIFTY", {}), "Bank Nifty OI"))
    components.append(_score_vix(data.get("nse_indices", {}).get("india_vix")))
    components.append(_score_sectors(data.get("nse_indices", {}).get("sectors", [])))
    components.append(_score_commodities(data.get("commodities", [])))
    components.append(_score_crypto(data.get("crypto", [])))
    components.append(_score_currencies(data.get("currencies", [])))

    total = sum(item["score"] for item in components)
    bias = _bias_from_score(total)
    confidence = _confidence(components)

    return {
        "score": total,
        "bias": bias,
        "confidence": confidence,
        "components": components,
    }


def _score_gift_nifty(gift: dict[str, Any] | None) -> dict[str, Any]:
    if not gift:
        return {
            "name": "GIFT Nifty",
            "score": 0,
            "status": "Unavailable",
            "reason": "GIFT Nifty was not available from the fetched index snapshot.",
        }
    change = gift.get("change")
    change_pct = gift.get("change_pct")
    score = 0
    if change is not None:
        if change >= 100:
            score = 2
        elif change >= 30:
            score = 1
        elif change <= -100:
            score = -2
        elif change <= -30:
            score = -1
    elif change_pct is not None:
        if change_pct >= 0.5:
            score = 2
        elif change_pct >= 0.15:
            score = 1
        elif change_pct <= -0.5:
            score = -2
        elif change_pct <= -0.15:
            score = -1
    return {
        "name": "GIFT Nifty",
        "score": score,
        "status": _status_from_score(score),
        "reason": f"GIFT Nifty change: {change if change is not None else change_pct}.",
    }


def _score_region(rows: list[dict[str, Any]], region: str, names: set[str]) -> dict[str, Any]:
    selected = [row for row in rows if row.get("name") in names]
    valid = [row for row in selected if row.get("change_pct") is not None]
    if not valid:
        return {
            "name": f"{region} markets",
            "score": 0,
            "status": "Unavailable",
            "reason": f"No usable {region} market data.",
        }
    avg = sum(row["change_pct"] for row in valid) / len(valid)
    positive = sum(1 for row in valid if row["change_pct"] > 0)
    negative = sum(1 for row in valid if row["change_pct"] < 0)
    score = 1 if avg > 0.2 and positive >= negative else -1 if avg < -0.2 and negative > positive else 0
    return {
        "name": f"{region} markets",
        "score": score,
        "status": _status_from_score(score),
        "reason": f"Average move {avg:.2f}% across {len(valid)} indices.",
    }


def _score_fii_dii(flow: dict[str, Any]) -> dict[str, Any]:
    fii = flow.get("fii_net")
    dii = flow.get("dii_net")
    if fii is None and dii is None:
        return {
            "name": "FII/DII flow",
            "score": 0,
            "status": "Unavailable",
            "reason": "Institutional flow was not available.",
        }
    fii = fii or 0
    dii = dii or 0
    net = fii + dii
    if fii > 0 and dii > 0:
        score = 2
    elif fii < 0 and dii < 0:
        score = -2
    elif net > 1000:
        score = 1
    elif net < -1000:
        score = -1
    else:
        score = 0
    return {
        "name": "FII/DII flow",
        "score": score,
        "status": _status_from_score(score),
        "reason": f"FII net {fii:.2f} Cr, DII net {dii:.2f} Cr, combined {net:.2f} Cr.",
    }


def _score_options(options: dict[str, Any], label: str) -> dict[str, Any]:
    pcr = options.get("pcr")
    if pcr is None:
        return {
            "name": label,
            "score": 0,
            "status": "Unavailable",
            "reason": "Option-chain PCR/support/resistance not available.",
        }
    if 0.9 <= pcr <= 1.25:
        score = 1
    elif pcr > 1.25:
        score = 1
    elif 0.7 <= pcr < 0.9:
        score = 0
    else:
        score = -1
    return {
        "name": label,
        "score": score,
        "status": _status_from_score(score),
        "reason": f"PCR {pcr:.2f}, support {options.get('support')}, resistance {options.get('resistance')}.",
    }


def _score_vix(vix: dict[str, Any] | None) -> dict[str, Any]:
    if not vix or vix.get("change_pct") is None:
        return {
            "name": "India VIX",
            "score": 0,
            "status": "Unavailable",
            "reason": "India VIX change was not available.",
        }
    change_pct = vix["change_pct"]
    score = 1 if change_pct < -1 else -1 if change_pct > 1 else 0
    return {
        "name": "India VIX",
        "score": score,
        "status": _status_from_score(score),
        "reason": f"India VIX change {change_pct:.2f}%.",
    }


def _score_sectors(sectors: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [row for row in sectors if row.get("change_pct") is not None]
    if not valid:
        return {
            "name": "Sector breadth",
            "score": 0,
            "status": "Unavailable",
            "reason": "Sector data not available.",
        }
    positive = sum(1 for row in valid if row["change_pct"] > 0)
    negative = sum(1 for row in valid if row["change_pct"] < 0)
    score = 1 if positive > negative else -1 if negative > positive else 0
    return {
        "name": "Sector breadth",
        "score": score,
        "status": _status_from_score(score),
        "reason": f"{positive} sectors positive and {negative} sectors negative.",
    }


def _score_commodities(rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [row for row in rows if row.get("change_pct") is not None]
    if not valid:
        return {
            "name": "Global commodities",
            "score": 0,
            "status": "Unavailable",
            "reason": "Commodity data was not available.",
        }
    energy = [row for row in valid if row.get("name") in {"Crude Oil WTI", "Brent Oil"}]
    energy_avg = _avg_change(energy)
    score = 0
    reason = f"Commodity average move {_avg_change(valid):.2f}%."
    if energy_avg is not None:
        if energy_avg > 1:
            score = -1
            reason = f"Crude/Brent average up {energy_avg:.2f}%, which can pressure India inflation and import costs."
        elif energy_avg < -1:
            score = 1
            reason = f"Crude/Brent average down {energy_avg:.2f}%, which is supportive for India market sentiment."
        else:
            reason = f"Crude/Brent average move {energy_avg:.2f}%, commodity pressure is limited."
    return {
        "name": "Global commodities",
        "score": score,
        "status": _status_from_score(score),
        "reason": reason,
    }


def _score_crypto(rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [row for row in rows if row.get("change_pct") is not None]
    if not valid:
        return {
            "name": "Crypto risk appetite",
            "score": 0,
            "status": "Unavailable",
            "reason": "Crypto data was not available.",
        }
    avg = _avg_change(valid)
    score = 1 if avg is not None and avg > 1.5 else -1 if avg is not None and avg < -1.5 else 0
    return {
        "name": "Crypto risk appetite",
        "score": score,
        "status": _status_from_score(score),
        "reason": f"Major crypto basket average move {avg:.2f}% across {len(valid)} coins.",
    }


def _score_currencies(rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [row for row in rows if row.get("change_pct") is not None]
    if not valid:
        return {
            "name": "Currency pressure",
            "score": 0,
            "status": "Unavailable",
            "reason": "Currency data was not available.",
        }
    dxy = next((row for row in valid if row.get("name") == "DXY"), None)
    usdinr = next((row for row in valid if row.get("name") == "USD/INR"), None)
    pressure_values = [row.get("change_pct") for row in [dxy, usdinr] if row and row.get("change_pct") is not None]
    if not pressure_values:
        avg = _avg_change(valid)
        score = -1 if avg is not None and avg > 0.4 else 1 if avg is not None and avg < -0.4 else 0
        reason = f"Currency basket average move {avg:.2f}%."
    else:
        pressure = sum(float(value) for value in pressure_values) / len(pressure_values)
        score = -1 if pressure > 0.25 else 1 if pressure < -0.25 else 0
        reason = f"DXY/USDINR pressure average {pressure:.2f}%; rising dollar/rupee pressure is usually negative for India."
    return {
        "name": "Currency pressure",
        "score": score,
        "status": _status_from_score(score),
        "reason": reason,
    }


def _avg_change(rows: list[dict[str, Any]]) -> float | None:
    values = [row.get("change_pct") for row in rows if row.get("change_pct") is not None]
    if not values:
        return None
    return sum(float(value) for value in values) / len(values)


def _status_from_score(score: int) -> str:
    if score > 0:
        return "Bullish"
    if score < 0:
        return "Bearish"
    return "Neutral"


def _bias_from_score(score: int) -> str:
    if score >= 5:
        return "Bullish"
    if score >= 2:
        return "Mild Bullish"
    if score <= -5:
        return "Bearish"
    if score <= -2:
        return "Mild Bearish"
    return "Neutral / Range-bound"


def _confidence(components: list[dict[str, Any]]) -> str:
    usable = [item for item in components if item.get("status") != "Unavailable"]
    ratio = len(usable) / len(components) if components else 0
    if ratio >= 0.8:
        return "High"
    if ratio >= 0.55:
        return "Medium"
    return "Low"
