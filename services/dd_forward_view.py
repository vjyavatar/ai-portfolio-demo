"""
r63.72.26 — DD Forward View module.

Three forward-looking analytical sections for the Deep DD report:

  1. DEMAND CURVE (7-year revenue trajectory)
       - Prior 3 years (real, from financials)
       - Current year (TTM)
       - Forward 3 years (analyst consensus where available, slope extrapolation otherwise)
       - Output: data series + classification + price implication

  2. OWNERSHIP ACTIVITY (insider + institutional over time)
       - Insider transactions trend (buys vs sells)
       - Institutional ownership % over recent quarters
       - Output: time series + verdict

  3. VOLUME PROFILE (VWAP-by-price — order book proxy)
       - Historical volume bucketed by price level
       - High-volume nodes = support/resistance
       - Output: price levels with traded volume + key levels

Each output uses the SAME schema:
  {
    success, ticker, region,
    headline: "<one-line summary>",
    layman: "<plain-English explanation>",
    price_implication: {direction, pct_contribution, target_band},
    chart_data: {...section specific...},
    confidence: "high|medium|low",
    data_sources, partial_data
  }

Design principles:
  - Hard timeouts on every external fetch (5-7s max)
  - Graceful degradation when sources fail
  - No LLM — all classification deterministic
  - No fake data — missing inputs surface as N/A
"""

import time
import threading
import statistics
import math
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime, timedelta

_dd_cache: Dict[str, tuple] = {}
_dd_lock = threading.Lock()
_CACHE_TTL = 3600  # 1 hour


# ─── SHARED HELPERS ─────────────────────────────────────────────────────

def _fetch_with_timeout(fn, timeout_sec: float, default=None):
    """Run a function with hard timeout. Return default on timeout/exception."""
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(fn)
        try:
            return fut.result(timeout=timeout_sec)
        except (FuturesTimeoutError, Exception):
            return default


def _safe_yahoo_ticker(ticker: str, region: str):
    """Construct yfinance Ticker handle with rate-limit respect. Returns None on failure."""
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


def _classify_growth(cagr_pct: float) -> dict:
    """Classify growth rate into band + color."""
    if cagr_pct >= 25:
        return {"label": "Hyper-Growth", "color": "#7c3aed", "magnitude": "extreme"}
    if cagr_pct >= 15:
        return {"label": "Strong Growth", "color": "#10b981", "magnitude": "strong"}
    if cagr_pct >= 8:
        return {"label": "Healthy Growth", "color": "#16a34a", "magnitude": "moderate"}
    if cagr_pct >= 3:
        return {"label": "Modest Growth", "color": "#3b82f6", "magnitude": "mild"}
    if cagr_pct >= -3:
        return {"label": "Flat", "color": "#94a3b8", "magnitude": "flat"}
    if cagr_pct >= -10:
        return {"label": "Declining", "color": "#f87171", "magnitude": "mild_neg"}
    return {"label": "Sharp Decline", "color": "#dc2626", "magnitude": "strong_neg"}


# ═════════════════════════════════════════════════════════════════════════
# SECTION 1 — DEMAND CURVE (revenue trajectory 7-year window)
# ═════════════════════════════════════════════════════════════════════════

def get_demand_curve(ticker: str, region: str = "US") -> dict:
    """
    Build 7-year revenue trajectory:
      - 3 prior fiscal years (actual)
      - Current TTM
      - 3 forward years (analyst estimates if available, else slope extrapolation)
    """
    def _fetch_financials():
        try:
            tk = _safe_yahoo_ticker(ticker, region)
            if not tk:
                return None
            info = tk.info or {}
            # Annual financials (last 4 fiscal years typically available)
            try:
                fin = tk.financials  # DataFrame, columns = fiscal years
            except Exception:
                fin = None
            try:
                analyst_growth = info.get("revenueGrowth")  # next year growth estimate
            except Exception:
                analyst_growth = None
            try:
                earnings_estimate = tk.analyst_price_targets  # if available
            except Exception:
                earnings_estimate = None
            return {
                "financials": fin,
                "info": info,
                "analyst_growth": analyst_growth,
            }
        except Exception:
            return None

    raw = _fetch_with_timeout(_fetch_financials, timeout_sec=7.0, default=None)

    if not raw or raw.get("financials") is None:
        return {
            "success": True,
            "ticker": ticker,
            "section": "demand_curve",
            "headline": "Revenue history unavailable",
            "layman": "We couldn't fetch the company's revenue data — try refreshing in a few minutes (data sources are rate-limited).",
            "price_implication": {"direction": "neutral", "pct_contribution": None, "target_band": None},
            "chart_data": {},
            "confidence": "low",
            "data_sources": {"financials": "failed"},
            "partial_data": True,
        }

    fin = raw["financials"]
    info = raw["info"]
    analyst_growth = raw["analyst_growth"]  # 0.0-1.0 fraction

    # Extract historical revenue series (sorted oldest to newest)
    historical_years = []
    try:
        # yfinance financials: rows are line items; columns are dates
        if hasattr(fin, "loc") and "Total Revenue" in fin.index:
            revenue_row = fin.loc["Total Revenue"]
            # Sort by date column ascending
            sorted_cols = sorted(revenue_row.index)
            for col in sorted_cols:
                val = revenue_row[col]
                if val is not None and not (isinstance(val, float) and (val != val)):
                    historical_years.append({
                        "year": col.year if hasattr(col, "year") else int(str(col)[:4]),
                        "revenue": float(val),
                        "actual": True,
                    })
    except Exception:
        historical_years = []

    # If we got 0 historical, fall back to info-based TTM only
    current_year = datetime.utcnow().year
    if not historical_years:
        ttm = info.get("totalRevenue")
        if ttm:
            historical_years.append({"year": current_year, "revenue": float(ttm), "actual": True, "ttm": True})

    if not historical_years:
        return {
            "success": True,
            "ticker": ticker,
            "section": "demand_curve",
            "headline": "Revenue data unavailable",
            "layman": "Couldn't extract revenue history from the data source.",
            "price_implication": {"direction": "neutral", "pct_contribution": None, "target_band": None},
            "chart_data": {},
            "confidence": "low",
            "data_sources": {"financials": "no_data"},
            "partial_data": True,
        }

    # Keep last 4 historical (3 prior + current/TTM)
    historical_years = historical_years[-4:]
    last_year = historical_years[-1]["year"]
    last_revenue = historical_years[-1]["revenue"]

    # Compute historical CAGR
    if len(historical_years) >= 2:
        first = historical_years[0]["revenue"]
        n_years = historical_years[-1]["year"] - historical_years[0]["year"]
        if first > 0 and n_years > 0:
            historical_cagr = ((last_revenue / first) ** (1 / n_years) - 1) * 100
        else:
            historical_cagr = 0
    else:
        historical_cagr = 0

    # Forward 3 years — use analyst growth for Y+1, slope extrapolation Y+2/Y+3
    forward_years = []
    if analyst_growth is not None and -0.5 <= analyst_growth <= 1.0:
        # Year +1: analyst consensus
        y1_growth = analyst_growth * 100
        y1_rev = last_revenue * (1 + analyst_growth)
        forward_years.append({"year": last_year + 1, "revenue": y1_rev, "actual": False,
                              "growth_pct": y1_growth, "source": "analyst_consensus"})
        # Year +2, Y+3: decay analyst estimate toward historical avg (regression to mean)
        decay_growth = (analyst_growth + (historical_cagr / 100)) / 2  # blend
        y2_rev = y1_rev * (1 + decay_growth)
        forward_years.append({"year": last_year + 2, "revenue": y2_rev, "actual": False,
                              "growth_pct": decay_growth * 100, "source": "blended_consensus_historical"})
        y3_growth = historical_cagr / 100  # full reversion
        y3_rev = y2_rev * (1 + y3_growth)
        forward_years.append({"year": last_year + 3, "revenue": y3_rev, "actual": False,
                              "growth_pct": y3_growth * 100, "source": "historical_extrapolation"})
    else:
        # No analyst growth — use historical CAGR for all 3 forward years
        g = historical_cagr / 100
        rev = last_revenue
        for i in range(1, 4):
            rev = rev * (1 + g)
            forward_years.append({"year": last_year + i, "revenue": rev, "actual": False,
                                  "growth_pct": historical_cagr, "source": "historical_extrapolation"})

    full_series = historical_years + forward_years

    # Forward CAGR (last historical → last forward)
    if len(forward_years) > 0:
        forward_final = forward_years[-1]["revenue"]
        n_fwd = forward_years[-1]["year"] - last_year
        if last_revenue > 0 and n_fwd > 0:
            forward_cagr = ((forward_final / last_revenue) ** (1 / n_fwd) - 1) * 100
        else:
            forward_cagr = 0
    else:
        forward_cagr = 0

    # Classify
    hist_class = _classify_growth(historical_cagr)
    fwd_class = _classify_growth(forward_cagr)

    # Price implication
    # Simple model: revenue growth premium/discount over GDP-like baseline (5%)
    # Each pp above/below baseline → ~1% fair-value adjustment (rough multiples expansion)
    pp_above = forward_cagr - 5
    pct_contribution = round(pp_above * 1.0, 1)  # bounded between -25 and +50
    pct_contribution = max(-25, min(50, pct_contribution))

    # Direction
    if pct_contribution > 5:
        direction = "bullish"
    elif pct_contribution < -5:
        direction = "bearish"
    else:
        direction = "neutral"

    # Current price for target band
    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    if current_price:
        # Conservative band: ±5% noise around contribution
        low_target = current_price * (1 + (pct_contribution - 5) / 100)
        high_target = current_price * (1 + (pct_contribution + 5) / 100)
        target_band = {"low": round(low_target, 2), "high": round(high_target, 2)}
    else:
        target_band = None

    # Headline
    if forward_cagr >= historical_cagr * 1.2:
        headline = f"Demand accelerating: {historical_cagr:.1f}% historical → {forward_cagr:.1f}% projected forward"
    elif forward_cagr <= historical_cagr * 0.7:
        headline = f"Demand decelerating: {historical_cagr:.1f}% historical → {forward_cagr:.1f}% projected forward"
    else:
        headline = f"Steady demand: {forward_cagr:.1f}% forward CAGR aligns with {historical_cagr:.1f}% historical pace"

    # Layman
    layman_parts = []
    rev_unit = "billion" if last_revenue >= 1e9 else "million"
    last_rev_display = last_revenue / 1e9 if rev_unit == "billion" else last_revenue / 1e6
    proj_final = forward_years[-1]["revenue"] if forward_years else last_revenue
    proj_final_display = proj_final / 1e9 if rev_unit == "billion" else proj_final / 1e6
    layman_parts.append(
        f"This company's sales were ${last_rev_display:.1f}{rev_unit[0].upper()} last year. "
    )
    layman_parts.append(
        f"Based on its historical growth pace of {historical_cagr:.1f}% per year"
    )
    if analyst_growth is not None:
        layman_parts.append(f" and analyst forecasts of {(analyst_growth * 100):.1f}% for next year,")
    else:
        layman_parts.append(",")
    layman_parts.append(
        f" sales should reach roughly ${proj_final_display:.1f}{rev_unit[0].upper()} in 3 years. "
    )
    if direction == "bullish":
        layman_parts.append(
            f"That's strong enough growth to support a higher stock price — typically worth about +{pct_contribution:.0f}% fair-value premium over current levels."
        )
    elif direction == "bearish":
        layman_parts.append(
            f"That growth pace is below average — typically worth about {pct_contribution:.0f}% discount to current levels."
        )
    else:
        layman_parts.append(
            "That's roughly average growth — doesn't argue strongly for either premium or discount on this signal alone."
        )

    layman = "".join(layman_parts)

    return {
        "success": True,
        "ticker": ticker,
        "section": "demand_curve",
        "headline": headline,
        "layman": layman,
        "price_implication": {
            "direction": direction,
            "pct_contribution": pct_contribution,
            "target_band": target_band,
        },
        "chart_data": {
            "series": full_series,
            "historical_cagr": round(historical_cagr, 2),
            "forward_cagr": round(forward_cagr, 2),
            "historical_class": hist_class,
            "forward_class": fwd_class,
            "current_price": current_price,
            "has_analyst_estimate": analyst_growth is not None,
        },
        "confidence": "high" if (len(historical_years) >= 3 and analyst_growth is not None) else "medium" if len(historical_years) >= 2 else "low",
        "data_sources": {"financials": "yfinance"},
        "partial_data": False,
    }


# ═════════════════════════════════════════════════════════════════════════
# SECTION 2 — OWNERSHIP ACTIVITY (insider + institutional over time)
# ═════════════════════════════════════════════════════════════════════════

def get_ownership_activity(ticker: str, region: str = "US") -> dict:
    """
    Insider transactions + institutional ownership trend.
    """
    def _fetch_ownership():
        try:
            tk = _safe_yahoo_ticker(ticker, region)
            if not tk:
                return None
            info = tk.info or {}
            inst_pct = info.get("heldPercentInstitutions")  # 0.0-1.0
            insider_pct = info.get("heldPercentInsiders")
            # Insider transactions (last 6 months from yfinance)
            try:
                insider_tx = tk.insider_transactions
            except Exception:
                insider_tx = None
            try:
                insider_purchases = tk.insider_purchases  # 6-month summary
            except Exception:
                insider_purchases = None
            try:
                major_holders = tk.major_holders
            except Exception:
                major_holders = None
            return {
                "info": info,
                "inst_pct": inst_pct,
                "insider_pct": insider_pct,
                "insider_tx": insider_tx,
                "insider_purchases": insider_purchases,
                "major_holders": major_holders,
            }
        except Exception:
            return None

    raw = _fetch_with_timeout(_fetch_ownership, timeout_sec=7.0, default=None)

    if not raw:
        return {
            "success": True,
            "ticker": ticker,
            "section": "ownership_activity",
            "headline": "Ownership data unavailable",
            "layman": "We couldn't fetch ownership data right now.",
            "price_implication": {"direction": "neutral", "pct_contribution": None, "target_band": None},
            "chart_data": {},
            "confidence": "low",
            "data_sources": {"ownership": "failed"},
            "partial_data": True,
        }

    info = raw["info"]
    inst_pct = raw["inst_pct"]
    insider_pct = raw["insider_pct"]

    # Parse insider transactions for 6-month buys vs sells
    insider_buys_count = 0
    insider_sells_count = 0
    insider_net_shares = 0
    insider_recent_tx = []

    if raw["insider_tx"] is not None:
        try:
            df = raw["insider_tx"]
            if hasattr(df, "iterrows"):
                for _, row in df.head(30).iterrows():
                    tx_type = str(row.get("Transaction", "") or row.get("Action", "")).lower()
                    shares = row.get("Shares", 0) or 0
                    try:
                        shares = int(shares)
                    except Exception:
                        shares = 0
                    insider_name = row.get("Insider", "") or row.get("Filer", "")
                    if "buy" in tx_type or "purchase" in tx_type:
                        insider_buys_count += 1
                        insider_net_shares += abs(shares)
                    elif "sale" in tx_type or "sell" in tx_type:
                        insider_sells_count += 1
                        insider_net_shares -= abs(shares)
                    insider_recent_tx.append({
                        "type": "buy" if ("buy" in tx_type or "purchase" in tx_type) else "sell",
                        "shares": int(shares),
                        "name": str(insider_name)[:50],
                    })
        except Exception:
            pass

    # Net direction
    total_tx = insider_buys_count + insider_sells_count
    if total_tx >= 5:
        buy_ratio = insider_buys_count / total_tx
        if buy_ratio >= 0.7:
            insider_signal = "STRONG_BUYING"
            insider_color = "#10b981"
        elif buy_ratio >= 0.55:
            insider_signal = "MILD_BUYING"
            insider_color = "#16a34a"
        elif buy_ratio >= 0.45:
            insider_signal = "BALANCED"
            insider_color = "#94a3b8"
        elif buy_ratio >= 0.30:
            insider_signal = "MILD_SELLING"
            insider_color = "#f87171"
        else:
            insider_signal = "STRONG_SELLING"
            insider_color = "#dc2626"
    elif total_tx > 0:
        insider_signal = "LIGHT_ACTIVITY"
        insider_color = "#94a3b8"
        buy_ratio = (insider_buys_count / max(1, total_tx))
    else:
        insider_signal = "NO_ACTIVITY"
        insider_color = "#cbd5e1"
        buy_ratio = 0.5

    # Institutional level classification
    if inst_pct is not None:
        inst_pct_val = inst_pct * 100
        if inst_pct_val >= 80:
            inst_class = "HEAVY_INSTITUTIONAL"
        elif inst_pct_val >= 60:
            inst_class = "STRONG_INSTITUTIONAL"
        elif inst_pct_val >= 40:
            inst_class = "MODERATE_INSTITUTIONAL"
        elif inst_pct_val >= 20:
            inst_class = "LIGHT_INSTITUTIONAL"
        else:
            inst_class = "RETAIL_DOMINATED"
    else:
        inst_pct_val = None
        inst_class = "UNKNOWN"

    # Price implication
    # Insider strong buying = +5-10%, strong selling = -5-10%
    pct_contribution = 0
    if insider_signal == "STRONG_BUYING":
        pct_contribution = 10
    elif insider_signal == "MILD_BUYING":
        pct_contribution = 5
    elif insider_signal == "MILD_SELLING":
        pct_contribution = -5
    elif insider_signal == "STRONG_SELLING":
        pct_contribution = -10

    # Institutional level adjustment: high institutional ownership + insider buying = stronger signal
    if inst_pct_val and inst_pct_val >= 70 and insider_signal in ("STRONG_BUYING", "MILD_BUYING"):
        pct_contribution += 3
    elif inst_pct_val and inst_pct_val >= 70 and insider_signal in ("STRONG_SELLING", "MILD_SELLING"):
        pct_contribution -= 3

    pct_contribution = max(-20, min(15, pct_contribution))

    if pct_contribution > 3:
        direction = "bullish"
    elif pct_contribution < -3:
        direction = "bearish"
    else:
        direction = "neutral"

    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    if current_price:
        target_band = {
            "low":  round(current_price * (1 + (pct_contribution - 3) / 100), 2),
            "high": round(current_price * (1 + (pct_contribution + 3) / 100), 2),
        }
    else:
        target_band = None

    # Headline
    if insider_signal == "STRONG_BUYING":
        headline = f"⚡ Strong insider buying ({insider_buys_count} buys vs {insider_sells_count} sells)"
    elif insider_signal == "STRONG_SELLING":
        headline = f"⚠ Strong insider selling ({insider_sells_count} sells vs {insider_buys_count} buys)"
    elif insider_signal == "MILD_BUYING":
        headline = f"Mild insider buying tilt ({insider_buys_count} buys vs {insider_sells_count} sells)"
    elif insider_signal == "MILD_SELLING":
        headline = f"Mild insider selling tilt ({insider_sells_count} sells vs {insider_buys_count} buys)"
    elif insider_signal == "BALANCED":
        headline = f"Balanced insider activity ({insider_buys_count} buys, {insider_sells_count} sells)"
    elif insider_signal == "LIGHT_ACTIVITY":
        headline = f"Light insider activity ({total_tx} transactions in 6 months)"
    else:
        headline = "No recent insider transactions reported"
    if inst_pct_val is not None:
        headline += f" · Institutions hold {inst_pct_val:.0f}%"

    # Layman
    if insider_signal in ("STRONG_BUYING", "MILD_BUYING"):
        layman = (
            f"Company insiders (executives, directors, large shareholders) have been BUYING the stock — "
            f"{insider_buys_count} buy transactions vs {insider_sells_count} sells in the past 6 months. "
            f"Insider buying is generally a positive signal: people closest to the business are putting their own money in. "
        )
    elif insider_signal in ("STRONG_SELLING", "MILD_SELLING"):
        layman = (
            f"Company insiders have been SELLING — {insider_sells_count} sell transactions vs {insider_buys_count} buys in the past 6 months. "
            f"Caveat: insider selling isn't always bearish (tax planning, diversification, vested options), but heavy selling is worth understanding. "
        )
    elif insider_signal == "BALANCED":
        layman = (
            f"Insider transactions are roughly balanced ({insider_buys_count} buys vs {insider_sells_count} sells). No strong directional signal from insiders. "
        )
    else:
        layman = f"Limited insider transaction activity recently ({total_tx} transactions). "

    if inst_pct_val is not None:
        if inst_pct_val >= 80:
            layman += f"Institutions own {inst_pct_val:.0f}% of shares — a 'crowded' name with heavy professional investor presence."
        elif inst_pct_val >= 60:
            layman += f"Institutions own {inst_pct_val:.0f}% — strong professional ownership."
        elif inst_pct_val >= 40:
            layman += f"Institutions own {inst_pct_val:.0f}% — moderate institutional presence."
        else:
            layman += f"Institutions own only {inst_pct_val:.0f}% — this is more of a retail-driven stock."

    if direction == "bullish":
        layman += f" Net contribution to fair value: +{pct_contribution:.0f}% from this signal."
    elif direction == "bearish":
        layman += f" Net contribution to fair value: {pct_contribution:.0f}% from this signal."
    else:
        layman += " Net contribution to fair value: neutral from this signal."

    return {
        "success": True,
        "ticker": ticker,
        "section": "ownership_activity",
        "headline": headline,
        "layman": layman,
        "price_implication": {
            "direction": direction,
            "pct_contribution": pct_contribution,
            "target_band": target_band,
        },
        "chart_data": {
            "insider_buys_6mo":  insider_buys_count,
            "insider_sells_6mo": insider_sells_count,
            "insider_buy_ratio_pct": round(buy_ratio * 100, 0),
            "insider_signal": insider_signal,
            "insider_color":  insider_color,
            "insider_net_shares": int(insider_net_shares),
            "insider_recent_tx": insider_recent_tx[:10],
            "inst_pct":       round(inst_pct_val, 1) if inst_pct_val is not None else None,
            "inst_class":     inst_class,
            "insider_pct":    round(insider_pct * 100, 2) if insider_pct is not None else None,
        },
        "confidence": "high" if (total_tx >= 5 and inst_pct_val is not None) else "medium" if (total_tx > 0 or inst_pct_val is not None) else "low",
        "data_sources": {"ownership": "yfinance"},
        "partial_data": (total_tx == 0 or inst_pct_val is None),
    }


# ═════════════════════════════════════════════════════════════════════════
# SECTION 3 — VOLUME PROFILE (VWAP-by-price; order book proxy)
# ═════════════════════════════════════════════════════════════════════════

def get_volume_profile(ticker: str, region: str = "US") -> dict:
    """
    Volume-by-price profile from 90-day OHLCV history.
    Buckets price into ~15 levels, sums volume traded near each level.
    Output: levels + key support/resistance + price implication.
    """
    def _fetch_history():
        try:
            tk = _safe_yahoo_ticker(ticker, region)
            if not tk:
                return None
            hist = tk.history(period="90d", interval="1d")
            info = tk.info or {}
            return {"hist": hist, "info": info}
        except Exception:
            return None

    raw = _fetch_with_timeout(_fetch_history, timeout_sec=6.0, default=None)
    if not raw or raw["hist"] is None or len(raw["hist"]) == 0:
        return {
            "success": True,
            "ticker": ticker,
            "section": "volume_profile",
            "headline": "Price/volume history unavailable",
            "layman": "Couldn't fetch price history needed for the volume profile.",
            "price_implication": {"direction": "neutral", "pct_contribution": None, "target_band": None},
            "chart_data": {},
            "confidence": "low",
            "data_sources": {"history": "failed"},
            "partial_data": True,
        }

    hist = raw["hist"]
    info = raw["info"]
    current_price = info.get("currentPrice") or info.get("regularMarketPrice") or float(hist["Close"].iloc[-1])

    # Compute typical price per bar and bucket
    closes = [float(c) for c in hist["Close"].tolist() if c == c]
    highs  = [float(h) for h in hist["High"].tolist()  if h == h]
    lows   = [float(l) for l in hist["Low"].tolist()   if l == l]
    vols   = [int(v) for v in hist["Volume"].tolist()  if v == v]

    if not closes:
        return {
            "success": True,
            "ticker": ticker,
            "section": "volume_profile",
            "headline": "No price data",
            "layman": "Volume profile requires price history.",
            "price_implication": {"direction": "neutral", "pct_contribution": None, "target_band": None},
            "chart_data": {},
            "confidence": "low",
            "data_sources": {"history": "no_data"},
            "partial_data": True,
        }

    price_min = min(lows) if lows else min(closes)
    price_max = max(highs) if highs else max(closes)
    if price_max <= price_min:
        price_max = price_min * 1.01

    # 15 buckets
    n_buckets = 15
    bucket_size = (price_max - price_min) / n_buckets
    buckets = [{"low": price_min + i * bucket_size, "high": price_min + (i + 1) * bucket_size, "volume": 0} for i in range(n_buckets)]

    # Allocate each day's volume to the bucket containing its typical price
    for i in range(len(closes)):
        if i >= len(vols):
            break
        typical = (highs[i] + lows[i] + closes[i]) / 3 if i < len(highs) and i < len(lows) else closes[i]
        idx = int((typical - price_min) / bucket_size)
        idx = max(0, min(n_buckets - 1, idx))
        buckets[idx]["volume"] += vols[i]

    # Find Point of Control (highest-volume bucket) and Value Area (70% of volume)
    total_vol = sum(b["volume"] for b in buckets)
    if total_vol == 0:
        return {
            "success": True,
            "ticker": ticker,
            "section": "volume_profile",
            "headline": "Volume data empty",
            "layman": "No volume data available.",
            "price_implication": {"direction": "neutral", "pct_contribution": None, "target_band": None},
            "chart_data": {},
            "confidence": "low",
            "data_sources": {"history": "no_volume"},
            "partial_data": True,
        }

    poc_idx = max(range(n_buckets), key=lambda i: buckets[i]["volume"])
    poc_price = (buckets[poc_idx]["low"] + buckets[poc_idx]["high"]) / 2

    # Value Area: expand from POC outward until 70% of volume captured
    va_indices = {poc_idx}
    va_vol = buckets[poc_idx]["volume"]
    target_vol = total_vol * 0.7
    expand_low = poc_idx - 1
    expand_high = poc_idx + 1
    while va_vol < target_vol and (expand_low >= 0 or expand_high < n_buckets):
        low_v = buckets[expand_low]["volume"] if expand_low >= 0 else 0
        high_v = buckets[expand_high]["volume"] if expand_high < n_buckets else 0
        if low_v >= high_v and expand_low >= 0:
            va_indices.add(expand_low)
            va_vol += low_v
            expand_low -= 1
        elif expand_high < n_buckets:
            va_indices.add(expand_high)
            va_vol += high_v
            expand_high += 1
        else:
            break

    va_low = min(buckets[i]["low"] for i in va_indices)
    va_high = max(buckets[i]["high"] for i in va_indices)

    # Classify current price vs profile
    if current_price > va_high:
        position = "ABOVE_VA"
        position_label = "above value area (extended)"
    elif current_price < va_low:
        position = "BELOW_VA"
        position_label = "below value area (oversold relative to historical demand)"
    else:
        position = "IN_VA"
        position_label = "inside value area (fair price by historical demand)"

    # Identify nearest support/resistance from profile
    sorted_buckets = sorted(buckets, key=lambda b: b["volume"], reverse=True)
    significant_levels = sorted_buckets[:5]
    support_levels = sorted([b for b in significant_levels if (b["low"] + b["high"]) / 2 < current_price],
                             key=lambda b: -(b["low"] + b["high"]) / 2)[:2]
    resistance_levels = sorted([b for b in significant_levels if (b["low"] + b["high"]) / 2 > current_price],
                                key=lambda b: (b["low"] + b["high"]) / 2)[:2]

    # Build human-readable levels
    def _mid(b): return round((b["low"] + b["high"]) / 2, 2)

    support_list = [{"price": _mid(b), "volume_pct": round((b["volume"] / total_vol) * 100, 1)} for b in support_levels]
    resistance_list = [{"price": _mid(b), "volume_pct": round((b["volume"] / total_vol) * 100, 1)} for b in resistance_levels]

    # Price implication
    # - Above VA: stretched; modest downside pressure to VA high
    # - Below VA: undervalued; modest upside pressure to VA low
    # - In VA: fair; no contribution
    pct_contribution = 0
    if position == "BELOW_VA":
        upside_to_va_low = ((va_low - current_price) / current_price) * 100
        pct_contribution = round(min(upside_to_va_low, 15), 1)  # cap at +15
    elif position == "ABOVE_VA":
        downside_to_va_high = ((va_high - current_price) / current_price) * 100
        pct_contribution = round(max(downside_to_va_high, -10), 1)

    if pct_contribution > 2:
        direction = "bullish"
    elif pct_contribution < -2:
        direction = "bearish"
    else:
        direction = "neutral"

    target_band = {
        "low":  round(va_low, 2),
        "high": round(va_high, 2),
    }

    # Headline
    poc_pct_vol = round((buckets[poc_idx]["volume"] / total_vol) * 100, 0)
    headline = f"Point of Control ${poc_price:.2f} (heaviest 90d volume) · Current ${current_price:.2f} {position_label.split('(')[0].strip()}"

    # Layman
    layman = (
        f"Think of this like a heatmap of where buyers and sellers have been most active over the past 90 days. "
        f"The 'point of control' — the price level where the heaviest trading has happened — is ${poc_price:.2f}. "
        f"Most of the trading volume ({va_vol/total_vol*100:.0f}%) has occurred between ${va_low:.2f} and ${va_high:.2f}. "
    )
    if position == "BELOW_VA":
        layman += (
            f"The current price ${current_price:.2f} is BELOW that historical 'fair zone' — "
            f"there's a natural pull back up toward ${va_low:.2f} (the bottom of the dense zone). "
            f"Contribution to fair value: +{pct_contribution:.0f}% from this signal alone."
        )
    elif position == "ABOVE_VA":
        layman += (
            f"The current price ${current_price:.2f} is ABOVE that historical 'fair zone' — "
            f"prices this far above the dense zone tend to pull back toward ${va_high:.2f}. "
            f"Contribution to fair value: {pct_contribution:.0f}% from this signal alone."
        )
    else:
        layman += (
            f"The current price ${current_price:.2f} is inside that fair zone — no strong push toward either edge from volume profile alone. "
            f"Key support at ${support_list[0]['price'] if support_list else '—'}, resistance at ${resistance_list[0]['price'] if resistance_list else '—'}."
        )

    return {
        "success": True,
        "ticker": ticker,
        "section": "volume_profile",
        "headline": headline,
        "layman": layman,
        "price_implication": {
            "direction": direction,
            "pct_contribution": pct_contribution,
            "target_band": target_band,
        },
        "chart_data": {
            "buckets":         [{"low": round(b["low"], 2), "high": round(b["high"], 2),
                                  "mid": round((b["low"] + b["high"]) / 2, 2), "volume": b["volume"],
                                  "volume_pct": round((b["volume"] / total_vol) * 100, 2),
                                  "in_value_area": (i in va_indices)} for i, b in enumerate(buckets)],
            "poc_price":       round(poc_price, 2),
            "poc_volume_pct":  poc_pct_vol,
            "value_area":      {"low": round(va_low, 2), "high": round(va_high, 2)},
            "current_price":   round(current_price, 2),
            "position":        position,
            "support_levels":  support_list,
            "resistance_levels": resistance_list,
            "days_analyzed":   len(closes),
        },
        "confidence": "high" if len(closes) >= 60 else "medium" if len(closes) >= 30 else "low",
        "data_sources": {"history": "yfinance"},
        "partial_data": False,
    }


# ═════════════════════════════════════════════════════════════════════════
# CACHED ORCHESTRATOR
# ═════════════════════════════════════════════════════════════════════════

def _cached(key: str, fn, *args, **kwargs):
    now = time.time()
    with _dd_lock:
        cached = _dd_cache.get(key)
        if cached and (now - cached[0]) < _CACHE_TTL:
            return cached[1]
    result = fn(*args, **kwargs)
    with _dd_lock:
        _dd_cache[key] = (now, result)
    return result


def get_demand_curve_cached(ticker: str, region: str = "US"):
    return _cached(f"demand:{ticker}:{region}", get_demand_curve, ticker, region)


def get_ownership_activity_cached(ticker: str, region: str = "US"):
    return _cached(f"owner:{ticker}:{region}", get_ownership_activity, ticker, region)


def get_volume_profile_cached(ticker: str, region: str = "US"):
    return _cached(f"vol:{ticker}:{region}", get_volume_profile, ticker, region)
