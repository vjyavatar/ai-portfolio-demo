"""
r63.72.27 — Woodshed Signal.

Detects when a stock has been punished beyond fundamentals — the institutional
"buy weakness when retail panics" setup. Composite score 0-100 from 5 components:

  Component                         Weight   What it measures
  ─────────────────────────────────────────────────────────────────────────
  Drawdown from 52-week high        40%      Deep enough to be "in the woodshed"
  RSI(14) oversold extreme          20%      Technical capitulation
  Volume capitulation pattern       15%      Climax volume on the way down
  Insider buying inflection         15%      Smart money stepping in
  Distance to historical support    10%      Volume profile support nearby
  ─────────────────────────────────────────────────────────────────────────

Bands:
  80+   ELITE WOODSHED         — historically the moment to buy
  60-79 STRONG WOODSHED        — punishment looks overdone
  40-59 MILD WOODSHED          — early signal, watch
  <40   NOT IN WOODSHED        — stock isn't actually beaten down

Designed to fail gracefully: any missing component just doesn't contribute.
Confidence drops accordingly.
"""

import time
import threading
import statistics
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime, timedelta


_ws_cache: Dict[str, tuple] = {}
_ws_lock = threading.Lock()
_CACHE_TTL = 1800  # 30 min — capitulation can shift intra-day


# ─── HELPERS ────────────────────────────────────────────────────────────

def _fetch_with_timeout(fn, timeout_sec: float, default=None):
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(fn)
        try:
            return fut.result(timeout=timeout_sec)
        except (FuturesTimeoutError, Exception):
            return default


def _safe_yahoo_ticker(ticker: str, region: str):
    try:
        import yfinance as yf
        try:
            from api import _yahoo_rate_wait
            _yahoo_rate_wait()
        except Exception:
            pass
        yf_sym = ticker if region.upper() == "US" else f"{ticker}.NS"
        return yf.Ticker(yf_sym)
    except Exception:
        return None


def _compute_rsi(closes: List[float], period: int = 14) -> Optional[float]:
    """Standard RSI(14). Returns None if insufficient data."""
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        if diff > 0:
            gains.append(diff); losses.append(0)
        else:
            gains.append(0); losses.append(-diff)
    # Initial avg over the first `period`
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    # Wilder's smoothing for remainder
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


# ─── COMPONENT SCORERS ──────────────────────────────────────────────────

def _score_drawdown(current_price: float, high_52w: float) -> Optional[dict]:
    """Drawdown depth from 52w high. -40% is sweet spot, -50%+ is deep woodshed."""
    if not current_price or not high_52w or high_52w <= 0:
        return None
    dd_pct = ((high_52w - current_price) / high_52w) * 100  # positive = drawdown
    # Mapping: -10% = 10, -20% = 30, -35% = 70, -50% = 95, -65%+ = 100
    if dd_pct < 10:
        score = max(0, dd_pct * 1.0)
    elif dd_pct < 20:
        score = 10 + (dd_pct - 10) * 2.0   # 10 → 30
    elif dd_pct < 35:
        score = 30 + (dd_pct - 20) * 2.67  # 30 → 70
    elif dd_pct < 50:
        score = 70 + (dd_pct - 35) * 1.67  # 70 → 95
    elif dd_pct < 65:
        score = 95 + (dd_pct - 50) * 0.33  # 95 → 100
    else:
        # Past -65% — likely something fundamentally broken; score caps
        score = 100 - (dd_pct - 65) * 0.5  # decay above -65%
    score = max(0, min(100, score))
    return {
        "score":   round(score, 1),
        "dd_pct":  round(dd_pct, 1),
        "high_52w": round(high_52w, 2),
        "current": round(current_price, 2),
    }


def _score_rsi_oversold(rsi: Optional[float]) -> Optional[dict]:
    """RSI(14): 50 = neutral, <30 oversold, <20 extreme oversold."""
    if rsi is None:
        return None
    # Mapping: 50 → 0, 30 → 70, 20 → 95, <15 → 100
    if rsi >= 50:
        score = 0
    elif rsi >= 40:
        score = (50 - rsi) * 2  # 50 → 0, 40 → 20
    elif rsi >= 30:
        score = 20 + (40 - rsi) * 5  # 40 → 20, 30 → 70
    elif rsi >= 20:
        score = 70 + (30 - rsi) * 2.5  # 30 → 70, 20 → 95
    elif rsi >= 10:
        score = 95 + (20 - rsi) * 0.5  # 20 → 95, 10 → 100
    else:
        score = 100
    score = max(0, min(100, score))
    return {"score": round(score, 1), "rsi": round(rsi, 1)}


def _score_volume_climax(closes: List[float], volumes: List[int]) -> Optional[dict]:
    """
    Volume capitulation: recent down days on heavy volume (capitulation),
    followed by easing volume (selling exhaustion).
    """
    if len(closes) < 30 or len(volumes) < 30:
        return None

    avg_vol_90d = sum(volumes[-90:]) / max(1, min(90, len(volumes[-90:])))
    if avg_vol_90d <= 0:
        return None

    # Last 10 days: count of "capitulation days" (down >2% on >150% avg vol)
    capit_days = 0
    for i in range(max(1, len(closes) - 10), len(closes)):
        if i < 1: continue
        pct_chg = ((closes[i] - closes[i-1]) / closes[i-1]) * 100 if closes[i-1] > 0 else 0
        vol_ratio = volumes[i] / avg_vol_90d if avg_vol_90d > 0 else 0
        if pct_chg < -2 and vol_ratio > 1.5:
            capit_days += 1

    # Recent 5 days volume vs prior 5 days — selling drying up?
    recent5_vol = sum(volumes[-5:]) / 5
    prior5_vol = sum(volumes[-10:-5]) / 5 if len(volumes) >= 10 else recent5_vol
    drying = prior5_vol > 0 and recent5_vol < prior5_vol * 0.75

    # Score: 1 capit_day = 30, 2 = 60, 3+ = 90. Drying up adds 10.
    base = min(90, capit_days * 30)
    score = base + (10 if drying else 0)
    score = max(0, min(100, score))

    return {
        "score":         round(score, 1),
        "capit_days_10": capit_days,
        "vol_drying":    drying,
        "recent5_vol":   int(recent5_vol),
        "prior5_vol":    int(prior5_vol),
        "avg_90d_vol":   int(avg_vol_90d),
    }


def _score_insider_buying(insider_buys: int, insider_sells: int) -> Optional[dict]:
    """Insider buying during the woodshed is a strong signal."""
    total = insider_buys + insider_sells
    if total == 0:
        return None
    buy_ratio = insider_buys / total
    # Insider BUYING is what we want; selling = lower score
    # 0.5 ratio = 30, 0.7 = 65, 0.85+ = 90, 1.0 = 100
    if buy_ratio < 0.3:
        score = buy_ratio * 30  # 0-30
    elif buy_ratio < 0.5:
        score = 30 + (buy_ratio - 0.3) * 50  # 30-40
    elif buy_ratio < 0.7:
        score = 40 + (buy_ratio - 0.5) * 125  # 40-65
    elif buy_ratio < 0.85:
        score = 65 + (buy_ratio - 0.7) * 167  # 65-90
    else:
        score = 90 + (buy_ratio - 0.85) * 67  # 90-100
    score = max(0, min(100, score))
    return {
        "score":      round(score, 1),
        "buys":       insider_buys,
        "sells":      insider_sells,
        "buy_ratio":  round(buy_ratio * 100, 1),
    }


def _score_support_proximity(current_price: float, support_levels: List[dict]) -> Optional[dict]:
    """
    Volume Profile reuse: how close is current price to nearest historical support?
    Closer = higher score (well-positioned to bounce).
    """
    if not current_price or not support_levels:
        return None
    nearest = support_levels[0] if support_levels else None
    if not nearest or "price" not in nearest:
        return None
    sup_price = nearest["price"]
    if sup_price <= 0:
        return None
    distance_pct = ((current_price - sup_price) / current_price) * 100  # how far above support
    # 0% (at support) = 95, 2% above = 80, 5% = 60, 10% = 30, 15%+ = 10
    if distance_pct < 0:
        score = 95  # below support — could be even better entry
    elif distance_pct < 1:
        score = 95 - distance_pct * 5
    elif distance_pct < 5:
        score = 90 - (distance_pct - 1) * 7.5  # 90 → 60
    elif distance_pct < 10:
        score = 60 - (distance_pct - 5) * 6   # 60 → 30
    elif distance_pct < 15:
        score = 30 - (distance_pct - 10) * 4   # 30 → 10
    else:
        score = max(0, 10 - (distance_pct - 15) * 0.5)
    score = max(0, min(100, score))
    return {
        "score":         round(score, 1),
        "support_price": round(sup_price, 2),
        "distance_pct":  round(distance_pct, 2),
    }


# ─── TOP-LEVEL ──────────────────────────────────────────────────────────

def get_woodshed_signal(ticker: str, region: str = "US") -> dict:
    """
    Compute the full Woodshed Signal score for a ticker.
    """
    cache_key = f"{ticker.strip().upper()}:{region.upper()}"
    now = time.time()
    with _ws_lock:
        cached = _ws_cache.get(cache_key)
        if cached and (now - cached[0]) < _CACHE_TTL:
            return cached[1]

    # Fetch raw market data (1-year history for 52W + RSI + volume profile)
    def _fetch_market():
        try:
            tk = _safe_yahoo_ticker(ticker, region)
            if not tk:
                return None
            hist = tk.history(period="1y", interval="1d")
            info = tk.info or {}
            try:
                insider_tx = tk.insider_transactions
            except Exception:
                insider_tx = None
            return {"hist": hist, "info": info, "insider_tx": insider_tx}
        except Exception:
            return None

    raw = _fetch_with_timeout(_fetch_market, timeout_sec=8.0, default=None)

    if not raw or raw["hist"] is None or len(raw["hist"]) == 0:
        result = _empty_result(ticker, region, "Market history unavailable")
        with _ws_lock:
            _ws_cache[cache_key] = (now, result)
        return result

    hist = raw["hist"]
    info = raw["info"]

    closes = [float(c) for c in hist["Close"].tolist() if c == c]
    volumes = [int(v) for v in hist["Volume"].tolist() if v == v]
    highs = [float(h) for h in hist["High"].tolist() if h == h]
    lows = [float(l) for l in hist["Low"].tolist() if l == l]

    if not closes:
        result = _empty_result(ticker, region, "No price data")
        with _ws_lock:
            _ws_cache[cache_key] = (now, result)
        return result

    current_price = info.get("currentPrice") or info.get("regularMarketPrice") or closes[-1]
    high_52w = max(highs) if highs else max(closes)

    # ── COMPONENT 1: Drawdown
    dd = _score_drawdown(current_price, high_52w)

    # ── COMPONENT 2: RSI
    rsi_val = _compute_rsi(closes, period=14)
    rsi = _score_rsi_oversold(rsi_val)

    # ── COMPONENT 3: Volume climax pattern
    vol = _score_volume_climax(closes, volumes)

    # ── COMPONENT 4: Insider buying
    insider_buys = 0
    insider_sells = 0
    if raw["insider_tx"] is not None:
        try:
            df = raw["insider_tx"]
            if hasattr(df, "iterrows"):
                for _, row in df.head(30).iterrows():
                    tx_type = str(row.get("Transaction", "") or row.get("Action", "")).lower()
                    if "buy" in tx_type or "purchase" in tx_type:
                        insider_buys += 1
                    elif "sale" in tx_type or "sell" in tx_type:
                        insider_sells += 1
        except Exception:
            pass
    insider = _score_insider_buying(insider_buys, insider_sells)

    # ── COMPONENT 5: Volume Profile support proximity
    support = _compute_support_from_history(closes, highs, lows, volumes, current_price)

    # Composite (40/20/15/15/10)
    weights = [
        (dd,       0.40),
        (rsi,      0.20),
        (vol,      0.15),
        (insider,  0.15),
        (support,  0.10),
    ]
    score_sum = 0.0
    weight_used = 0.0
    components_present = 0
    for comp, w in weights:
        if comp and comp.get("score") is not None:
            score_sum += comp["score"] * w
            weight_used += w
            components_present += 1

    if weight_used > 0:
        composite = score_sum / weight_used
    else:
        composite = None

    # Verdict band
    verdict, verdict_color, verdict_label = _classify_woodshed(composite, components_present)

    # Price implication — depends on band
    pct_contribution = 0
    if verdict == "ELITE WOODSHED":
        pct_contribution = 25  # Strong bounce expected
    elif verdict == "STRONG WOODSHED":
        pct_contribution = 15
    elif verdict == "MILD WOODSHED":
        pct_contribution = 7
    else:
        pct_contribution = 0

    if pct_contribution > 5:
        direction = "bullish"
    elif pct_contribution < -5:
        direction = "bearish"
    else:
        direction = "neutral"

    if current_price > 0:
        target_band = {
            "low":  round(current_price * (1 + (pct_contribution - 5) / 100), 2),
            "high": round(current_price * (1 + (pct_contribution + 8) / 100), 2),
        }
    else:
        target_band = None

    # Headline
    if dd and dd.get("dd_pct"):
        dd_str = f"down {dd['dd_pct']:.0f}% from 52w high"
    else:
        dd_str = "drawdown unavailable"
    headline = f"{verdict} · {dd_str}"
    if rsi and rsi.get("rsi") is not None:
        headline += f" · RSI {rsi['rsi']:.0f}"
    if insider and insider.get("buys", 0) > 0:
        headline += f" · {insider['buys']} insider buys"

    # Layman explanation
    layman = _build_layman_narrative(verdict, composite, dd, rsi, vol, insider, support,
                                      current_price, target_band, pct_contribution)

    result = {
        "success":      True,
        "ticker":       ticker.strip().upper(),
        "region":       region.upper(),
        "section":      "woodshed_signal",
        "headline":     headline,
        "layman":       layman,
        "verdict":      verdict,
        "verdict_color": verdict_color,
        "verdict_label": verdict_label,
        "composite_score": round(composite, 1) if composite is not None else None,
        "components_present": components_present,
        "components": {
            "drawdown":    dd,
            "rsi":         rsi,
            "vol_climax":  vol,
            "insider":     insider,
            "support":     support,
        },
        "price_implication": {
            "direction":       direction,
            "pct_contribution": pct_contribution,
            "target_band":     target_band,
        },
        "current_price": round(current_price, 2),
        "confidence":   "high" if components_present >= 4 else "medium" if components_present >= 3 else "low",
        "data_sources": {"market": "yfinance"},
        "partial_data": components_present < 4,
    }

    with _ws_lock:
        _ws_cache[cache_key] = (now, result)
    return result


def _classify_woodshed(score: Optional[float], components_present: int):
    """Returns (verdict, color, label)."""
    if score is None or components_present < 2:
        return "INSUFFICIENT DATA", "#94a3b8", "Need more data to score"
    if score >= 80 and components_present >= 4:
        return "ELITE WOODSHED", "#7c3aed", "Historically the moment to buy"
    if score >= 60:
        return "STRONG WOODSHED", "#10b981", "Punishment looks overdone"
    if score >= 40:
        return "MILD WOODSHED", "#f59e0b", "Early signal, watch closely"
    return "NOT IN WOODSHED", "#94a3b8", "Stock is not actually beaten down"


def _compute_support_from_history(closes, highs, lows, volumes, current_price):
    """Quick volume profile to find nearest support level."""
    if len(closes) < 30:
        return None
    price_min = min(lows[-90:]) if len(lows) >= 90 else min(lows)
    price_max = max(highs[-90:]) if len(highs) >= 90 else max(highs)
    if price_max <= price_min:
        return None
    n = 10
    bucket = (price_max - price_min) / n
    buckets = [{"low": price_min + i * bucket, "vol": 0} for i in range(n)]
    for i in range(max(0, len(closes) - 90), len(closes)):
        if i >= len(volumes):
            break
        idx = int((closes[i] - price_min) / bucket)
        idx = max(0, min(n - 1, idx))
        buckets[idx]["vol"] += volumes[i]
    # Find highest-volume bucket BELOW current price
    support_buckets = [b for b in buckets if b["low"] + bucket / 2 < current_price]
    if not support_buckets:
        return None
    support_buckets.sort(key=lambda b: -b["vol"])
    s = support_buckets[0]
    support_price = s["low"] + bucket / 2
    return _score_support_proximity(current_price, [{"price": support_price, "volume_pct": 0}])


def _build_layman_narrative(verdict, composite, dd, rsi, vol, insider, support,
                             current_price, target_band, pct_contribution):
    """Plain-English explanation tied to the band."""
    parts = []

    # Drawdown
    if dd:
        parts.append(
            f"This stock is down {dd['dd_pct']:.0f}% from its 52-week high "
            f"(from ${dd['high_52w']:.2f} to ${dd['current']:.2f})."
        )

    # RSI
    if rsi and rsi.get("rsi") is not None:
        if rsi["rsi"] < 30:
            parts.append(f"RSI of {rsi['rsi']:.0f} is in oversold territory — technically extreme.")
        elif rsi["rsi"] < 40:
            parts.append(f"RSI of {rsi['rsi']:.0f} is approaching oversold.")
        elif rsi["rsi"] < 50:
            parts.append(f"RSI of {rsi['rsi']:.0f} is neutral-bearish.")
        else:
            parts.append(f"RSI of {rsi['rsi']:.0f} — not yet oversold.")

    # Volume climax
    if vol:
        if vol["capit_days_10"] >= 2:
            parts.append(f"{vol['capit_days_10']} capitulation days in last 10 sessions (>2% drops on heavy volume).")
        if vol["vol_drying"]:
            parts.append("Recent selling volume is drying up — exhaustion signal.")

    # Insider
    if insider:
        if insider["buys"] > insider["sells"]:
            parts.append(f"Insiders bought {insider['buys']} times vs sold {insider['sells']} times — they're stepping in.")
        elif insider["buys"] == 0 and insider["sells"] > 0:
            parts.append(f"No recent insider buying — {insider['sells']} insider sells instead.")

    # Verdict-tied call to action
    if verdict == "ELITE WOODSHED":
        parts.append(
            f"VERDICT: This is the classic 'taken to the woodshed' setup — punished hard, "
            f"oversold technicals, and ideally with smart money stepping in. "
            f"Historically these setups produce mean-reversion bounces. "
            f"Estimated fair value with mean reversion: ${target_band['low']:.2f}–${target_band['high']:.2f} ({pct_contribution:+d}% from here)."
        )
    elif verdict == "STRONG WOODSHED":
        parts.append(
            f"VERDICT: The stock has been meaningfully punished and is showing oversold signals. "
            f"Not as extreme as Elite, but worth considering on weakness. "
            f"Estimated fair value range: ${target_band['low']:.2f}–${target_band['high']:.2f} ({pct_contribution:+d}%)."
        )
    elif verdict == "MILD WOODSHED":
        parts.append(
            f"VERDICT: Some weakness signals, but not deep enough to be a classic woodshed setup. "
            f"Watch for further deterioration or volume capitulation before acting."
        )
    elif verdict == "NOT IN WOODSHED":
        parts.append(
            "VERDICT: This stock is NOT in the woodshed — it hasn't been punished enough "
            "or doesn't show the oversold/capitulation signals needed for a recovery setup."
        )
    else:
        parts.append("VERDICT: Insufficient data to score — try again when data sources are available.")

    return " ".join(parts)


def _empty_result(ticker, region, reason):
    return {
        "success":     True,
        "ticker":      ticker.strip().upper(),
        "region":      region.upper(),
        "section":     "woodshed_signal",
        "headline":    "Woodshed Signal unavailable",
        "layman":      f"{reason}. Try refreshing.",
        "verdict":     "INSUFFICIENT DATA",
        "verdict_color": "#94a3b8",
        "verdict_label": "Data unavailable",
        "composite_score": None,
        "components_present": 0,
        "components":  {},
        "price_implication": {"direction": "neutral", "pct_contribution": None, "target_band": None},
        "current_price": None,
        "confidence":  "low",
        "data_sources": {"market": "failed"},
        "partial_data": True,
    }
