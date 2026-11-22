"""Transparent research score. Missing inputs stay missing.

This is a research summary, not a trade instruction and not a win probability.
"""
from __future__ import annotations

from typing import Optional

WEIGHTS = {"trend": 0.40, "valuation": 0.25, "momentum": 0.20, "risk": 0.15}
DISCLAIMER = (
    "Research score only. Not financial advice, not a trade instruction, "
    "and not a probability of profit. Source limits are listed with the inputs."
)


def _band(score: float) -> str:
    if score >= 72:
        return "Constructive"
    if score >= 58:
        return "Balanced"
    if score >= 45:
        return "Cautious"
    return "Defensive"


def _trend(features: dict) -> tuple[Optional[float], str]:
    price = features.get("price")
    sma50 = features.get("sma50")
    sma200 = features.get("sma200")
    rsi = features.get("rsi")
    recommend = features.get("recommend")
    parts: list[float] = []
    notes: list[str] = []
    if price and sma50:
        above = price >= sma50
        parts.append(100 if above else 25)
        notes.append(f"Price is {'above' if above else 'below'} the 50-day average ({sma50:.2f}).")
    if price and sma200:
        above = price >= sma200
        parts.append(100 if above else 20)
        notes.append(f"Price is {'above' if above else 'below'} the 200-day average ({sma200:.2f}).")
    if sma50 and sma200:
        stacked = sma50 >= sma200
        parts.append(100 if stacked else 30)
        notes.append("The 50-day average is " + ("above" if stacked else "below") + " the 200-day average.")
    if rsi is not None:
        if 45 <= rsi <= 60:
            parts.append(80)
            notes.append(f"RSI {rsi:.0f} is in a moderate band.")
        elif 35 <= rsi < 45 or 60 < rsi <= 70:
            parts.append(60)
            notes.append(f"RSI {rsi:.0f} is leaning, not extreme.")
        elif rsi >= 75 or rsi <= 30:
            parts.append(30)
            notes.append(f"RSI {rsi:.0f} is stretched.")
        else:
            parts.append(50)
            notes.append(f"RSI {rsi:.0f}.")
    if recommend is not None:
        mapped = max(0.0, min(100.0, (recommend + 1) * 50))
        parts.append(mapped)
        notes.append(f"TradingView technical composite is {recommend:+.2f} on a -1 to +1 scale.")
    if not parts:
        return None, "Trend inputs are missing."
    return sum(parts) / len(parts), " ".join(notes)


def _valuation(features: dict) -> tuple[Optional[float], str]:
    pe = features.get("pe")
    if pe is None or pe <= 0:
        return None, "Trailing P/E is missing, so valuation is left out of the score."
    if pe < 12:
        score = 85
    elif pe < 18:
        score = 75
    elif pe < 25:
        score = 62
    elif pe < 35:
        score = 48
    elif pe < 50:
        score = 32
    else:
        score = 18
    return score, f"Trailing P/E is {pe:.1f}. This is not adjusted for sector or growth."


def _momentum(features: dict) -> tuple[Optional[float], str]:
    def one(pct: Optional[float]) -> Optional[float]:
        if pct is None:
            return None
        if pct > 15:
            return 40
        if pct > 3:
            return 75
        if pct >= 0:
            return 65
        if pct > -5:
            return 50
        if pct > -12:
            return 35
        return 20

    week = one(features.get("perf_w"))
    month = one(features.get("perf_1m"))
    parts = [p for p in (week, month) if p is not None]
    if not parts:
        return None, "Week and month performance are missing."
    bits = []
    if features.get("perf_w") is not None:
        bits.append(f"1-week {features['perf_w']:+.1f}%")
    if features.get("perf_1m") is not None:
        bits.append(f"1-month {features['perf_1m']:+.1f}%")
    return sum(parts) / len(parts), "Recent performance: " + ", ".join(bits) + ". A very large gain lowers the score because it is extended."


def _risk(features: dict) -> tuple[Optional[float], str]:
    price = features.get("price")
    high = features.get("high_52w")
    if not price or not high or high <= 0:
        return None, "52-week high is missing, so the risk pillar is left out."
    drawdown = (high - price) / high * 100
    if drawdown < 3:
        score = 42
        place = "within 3% of the 52-week high"
    elif drawdown < 12:
        score = 78
        place = f"{drawdown:.1f}% below the 52-week high"
    elif drawdown < 25:
        score = 60
        place = f"{drawdown:.1f}% below the 52-week high"
    elif drawdown < 40:
        score = 40
        place = f"{drawdown:.1f}% below the 52-week high"
    else:
        score = 28
        place = f"{drawdown:.1f}% below the 52-week high"
    note = f"Price is {place} ({high:.2f})."
    volume = features.get("volume")
    average = features.get("avg_volume")
    if volume and average and average > 0:
        ratio = volume / average
        if ratio < 0.4:
            score = max(0, score - 10)
            note += f" Volume is light at {ratio:.1f}× the recent average."
        elif ratio > 2 and features.get("change_pct") is not None and abs(features["change_pct"]) > 2:
            score = max(0, score - 8)
            note += f" Volume is elevated at {ratio:.1f}× average on a large day move."
        else:
            note += f" Volume is {ratio:.1f}× the recent average."
    return score, note


def score(features: dict) -> dict:
    builders = {
        "trend": ("Trend", _trend),
        "valuation": ("Valuation", _valuation),
        "momentum": ("Momentum", _momentum),
        "risk": ("Risk", _risk),
    }
    pillars = []
    weight_used = 0.0
    weighted = 0.0
    reasons = []
    for key, (label, builder) in builders.items():
        value, note = builder(features or {})
        weight = WEIGHTS[key]
        pillars.append({
            "key": key,
            "label": label,
            "score": None if value is None else round(value, 1),
            "weight": weight,
            "used": value is not None,
            "note": note,
        })
        reasons.append(note)
        if value is not None:
            weight_used += weight
            weighted += value * weight
    coverage = weight_used / sum(WEIGHTS.values())
    if weight_used <= 0 or coverage < 0.45:
        label = "Insufficient"
        total = None
    else:
        total_value = weighted / weight_used
        total = round(total_value, 1)
        label = _band(total_value)
    return {
        "score": total,
        "label": label,
        "coverage": round(coverage, 2),
        "pillars": pillars,
        "reasons": reasons,
        "disclaimer": DISCLAIMER,
    }
