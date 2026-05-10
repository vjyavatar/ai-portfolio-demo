"""
r63.72.5 — Price/market data enrichment for the Positioning Scanner.

Bulk-fetches current price + 52-week range + market cap for a list of
tickers with a 5-minute in-process cache. Handles yfinance 401-block on
Render by graceful degradation — if yfinance fails the row is returned
without enrichment rather than failing the whole scan.

Public:
    enrich_with_quotes(tickers: List[str]) -> Dict[str, dict]
        Returns {ticker: {"price", "prev_close", "change_pct",
                          "low_52w", "high_52w", "pct_in_range",
                          "market_cap", "shares_outstanding"}}
"""

import threading
import time
from typing import List, Dict, Optional

# Cache: {ticker: (timestamp, dict_or_none)}
_quote_cache: Dict[str, tuple] = {}
_cache_lock = threading.Lock()
_CACHE_TTL = 300  # 5 minutes


def _safe_float(v) -> float:
    try:
        f = float(v)
        if f != f or f in (float("inf"), float("-inf")):
            return 0.0
        return f
    except (TypeError, ValueError):
        return 0.0


def _fetch_one_quote_gf(ticker: str) -> Optional[dict]:
    """
    r63.72.8: Google Finance fallback for when yfinance is blocked (Render).
    Returns price + prev_close + market_cap; 52W data not available from GF.
    """
    try:
        # Reuse existing Google Finance scraper from data_sources
        from data_sources import fetch_google_finance
        info = fetch_google_finance(ticker)
        if not info:
            return None
        price = _safe_float(info.get("currentPrice"))
        if price <= 0:
            return None
        prev = _safe_float(info.get("previousClose")) or price
        change_pct = 100.0 * (price - prev) / prev if prev > 0 else 0.0
        market_cap = _safe_float(info.get("marketCap"))
        return {
            "price": round(price, 2),
            "prev_close": round(prev, 2),
            "change_pct": round(change_pct, 2),
            "low_52w": 0.0,
            "high_52w": 0.0,
            "pct_in_range": -1.0,  # not available from GF
            "market_cap": int(market_cap) if market_cap > 0 else 0,
            "shares_outstanding": 0,
            "_source": "gf",
        }
    except Exception:
        return None


def _fetch_one_quote(ticker: str) -> Optional[dict]:
    """
    Single-ticker quote fetch. Uses yfinance fast_info first (cheap, fast).
    r63.72.8: Falls back to Google Finance if yfinance returns no data
    (handles Render Yahoo 401-block).
    """
    # Try yfinance first
    yf_result = _fetch_one_quote_yf(ticker)
    if yf_result is not None:
        return yf_result
    # Fall back to Google Finance
    return _fetch_one_quote_gf(ticker)


def _fetch_one_quote_yf(ticker: str) -> Optional[dict]:
    """yfinance-only fetch. Returns None on any failure (including Render block)."""
    try:
        import yfinance as yf
    except ImportError:
        return None

    try:
        t = yf.Ticker(ticker)
        fi = t.fast_info if hasattr(t, "fast_info") else {}

        price = _safe_float(
            getattr(fi, "last_price", None) or
            (fi.get("last_price") if isinstance(fi, dict) else None) or
            (fi.get("lastPrice") if isinstance(fi, dict) else None)
        )
        if price <= 0:
            return None

        prev = _safe_float(
            getattr(fi, "previous_close", None) or
            (fi.get("previous_close") if isinstance(fi, dict) else None) or
            (fi.get("previousClose") if isinstance(fi, dict) else None)
        )

        low_52w = _safe_float(
            getattr(fi, "year_low", None) or
            (fi.get("year_low") if isinstance(fi, dict) else None) or
            (fi.get("yearLow") if isinstance(fi, dict) else None)
        )
        high_52w = _safe_float(
            getattr(fi, "year_high", None) or
            (fi.get("year_high") if isinstance(fi, dict) else None) or
            (fi.get("yearHigh") if isinstance(fi, dict) else None)
        )

        market_cap = _safe_float(
            getattr(fi, "market_cap", None) or
            (fi.get("market_cap") if isinstance(fi, dict) else None) or
            (fi.get("marketCap") if isinstance(fi, dict) else None)
        )
        shares = _safe_float(
            getattr(fi, "shares", None) or
            (fi.get("shares") if isinstance(fi, dict) else None)
        )

        change_pct = 0.0
        if prev > 0:
            change_pct = 100.0 * (price - prev) / prev

        pct_in_range = 50.0
        if high_52w > 0 and low_52w > 0 and high_52w > low_52w:
            pct_in_range = 100.0 * (price - low_52w) / (high_52w - low_52w)
            pct_in_range = max(0.0, min(100.0, pct_in_range))

        return {
            "price": round(price, 2),
            "prev_close": round(prev or price, 2),
            "change_pct": round(change_pct, 2),
            "low_52w": round(low_52w, 2),
            "high_52w": round(high_52w, 2),
            "pct_in_range": round(pct_in_range, 1),
            "market_cap": int(market_cap) if market_cap > 0 else 0,
            "shares_outstanding": int(shares) if shares > 0 else 0,
            "_source": "yf",
        }
    except Exception:
        return None


def enrich_with_quotes(tickers: List[str], parallel: int = 8) -> Dict[str, dict]:
    """
    Batch-fetch current quotes for tickers, with cache + thread parallelism.

    Args:
        tickers: list of US tickers
        parallel: max concurrent yf fetches (yfinance is I/O bound, threads OK)

    Returns:
        {ticker: quote_dict_or_empty} — every ticker has an entry.
        Failed lookups return {} rather than missing keys.
    """
    if not tickers:
        return {}

    now = time.time()
    out: Dict[str, dict] = {}
    needed: List[str] = []

    # Read cache
    with _cache_lock:
        for t in tickers:
            cached = _quote_cache.get(t)
            if cached and (now - cached[0]) < _CACHE_TTL:
                out[t] = cached[1] or {}
            else:
                needed.append(t)

    # Fetch missing in parallel
    if needed:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        results: Dict[str, Optional[dict]] = {}
        with ThreadPoolExecutor(max_workers=min(parallel, len(needed))) as ex:
            future_to_ticker = {ex.submit(_fetch_one_quote, t): t for t in needed}
            for fut in as_completed(future_to_ticker):
                t = future_to_ticker[fut]
                try:
                    results[t] = fut.result(timeout=10)
                except Exception:
                    results[t] = None

        # Persist to cache
        with _cache_lock:
            for t, r in results.items():
                _quote_cache[t] = (now, r)
                out[t] = r or {}

    return out


def build_plain_english_reasoning(metrics: dict, quote: dict) -> str:
    """
    Generate a single-sentence trader-speak narrative explaining WHY this
    ticker scored where it did. Pattern-based, not LLM. Predictable enough
    to ship; rich enough to be useful.

    metrics: output from _compute_metrics
    quote: output from _fetch_one_quote (may be empty {})
    """
    parts = []

    persistence = metrics.get("persistence_quarters", 0)
    share_d = metrics.get("share_delta_pct", 0)
    filer_d = metrics.get("filer_count_delta", 0)
    val_b = metrics.get("latest_value_usd", 0) / 1e9
    n_holders = metrics.get("latest_filer_count", 0)
    pct_in_range = quote.get("pct_in_range", -1)
    market_cap_b = quote.get("market_cap", 0) / 1e9 if quote else 0

    # Lead phrase: persistence + scale
    if persistence >= 4:
        if val_b >= 50:
            lead = f"Sustained multi-quarter accumulation in a major institutional holding"
        elif val_b >= 5:
            lead = f"{persistence} consecutive quarters of net buying"
        else:
            lead = f"{persistence}Q accumulation streak"
    elif persistence >= 2:
        lead = f"Multi-quarter accumulation pattern emerging"
    elif share_d >= 50:
        lead = f"Large single-quarter position build"
    elif share_d >= 10:
        lead = f"Notable Q-over-Q accumulation"
    elif share_d > 0:
        lead = f"Modest net accumulation"
    else:
        lead = f"Mixed flow"

    parts.append(lead)

    # Breadth detail
    if filer_d >= 30:
        parts.append(f"with broad +{filer_d} new institutional buyers")
    elif filer_d >= 10:
        parts.append(f"with +{filer_d} net new holders")
    elif filer_d >= 3:
        parts.append(f"with steady new entrants (+{filer_d})")
    elif filer_d <= -10:
        parts.append(f"despite {filer_d} holders exiting")

    # Position scale (latest value, not market cap — institutional dollars)
    if val_b >= 50:
        parts.append(f"on a ${val_b:,.0f}B aggregate position")
    elif val_b >= 5:
        parts.append(f"on a ${val_b:,.1f}B base")

    # Price context if we have it
    if pct_in_range >= 0:
        if pct_in_range >= 80:
            parts.append("near 52-week highs")
        elif pct_in_range <= 20:
            parts.append("from 52-week-low levels")
        elif pct_in_range >= 60:
            parts.append("trading in the upper range")
        elif pct_in_range <= 35:
            parts.append("with price still suppressed vs. 52W range")

    # Action implication
    if persistence >= 4 and filer_d >= 10:
        parts.append("— textbook stealth accumulation")
    elif persistence >= 4 and filer_d <= 0:
        parts.append("— existing institutions adding aggressively while no broad re-rating yet")
    elif share_d >= 50 and persistence == 1:
        parts.append("— single-quarter spike, watch for confirmation next quarter")

    text = ", ".join(parts[:1] + parts[1:]).rstrip(",")
    # Clean up "comma before em-dash" artifact
    text = text.replace(", —", " —")
    if not text.endswith((".", "—")):
        text += "."
    # Capitalize first letter
    text = text[0].upper() + text[1:] if text else text
    return text
