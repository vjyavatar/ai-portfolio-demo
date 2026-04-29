"""
Celesys — Earnings Move Intelligence (v2 — uses central data_sources)
=====================================================================
Computes:
  • Next earnings date + days until
  • Last 8 quarters: beat/miss + next-session % move
  • Avg/median absolute move; max up; max down
  • Beat rate (% of last 8 that beat)
  • Hit-implied rate (% of historical moves that exceeded current implied)
  • Implied move (from ATM straddle, if caller passes spot/atm_call/atm_put)
  • Verdict: BUY_PREMIUM | SELL_PREMIUM | NEUTRAL | INCOMPLETE_DATA

This version does NOT contain any data-source logic. It calls
`data_sources.get_*()` and trusts the central fallback chain.

If yfinance is rate-limited (US) or NSE is blocked (IN), the central
layer transparently rolls to the next source. This module never knows.
"""

from __future__ import annotations
import math
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import data_sources as ds  # ← THE central layer

try:
    from api import _safe_float, _smart_cache_get, _smart_cache_set
except ImportError:
    def _safe_float(v, default=0.0):
        try:
            f = float(v); return f if not (math.isnan(f) or math.isinf(f)) else default
        except (TypeError, ValueError): return default
    _local_cache = {}
    def _smart_cache_get(k):
        e = _local_cache.get(k)
        return e['data'] if e and time.time() - e['ts'] < e['ttl'] else None
    def _smart_cache_set(k, d, ttl=120): _local_cache[k] = {'data': d, 'ts': time.time(), 'ttl': ttl}


_CACHE_TTL = 900           # 15 min
_LOOKBACK_QUARTERS = 8
_INCOMPLETE_THRESHOLD = 3  # missing fields ≥ this → INCOMPLETE_DATA


# ─── Helpers ──────────────────────────────────────────────────────────────
def _is_index_ticker(ticker: str) -> bool:
    t = (ticker or "").upper().strip()
    return t in {"NIFTY", "BANKNIFTY", "SENSEX", "FINNIFTY", "MIDCPNIFTY",
                 "NIFTYIT", "SPX", "NDX", "RUT", "DJI", "VIX"}


def _pct_move(after: float, before: float) -> Optional[float]:
    if before <= 0 or after <= 0: return None
    return round((after - before) / before * 100, 2)


def _compute_implied_move(spot, call, put) -> Optional[float]:
    spot = _safe_float(spot); call = _safe_float(call); put = _safe_float(put)
    if spot <= 0 or call <= 0 or put <= 0: return None
    return round((call + put) / spot * 100, 2)


def _next_session_move(closes_map: dict, earnings_dt) -> Optional[float]:
    """
    Given price-history closes (iso_date → close) and an earnings datetime,
    find close[date-1] and close[date+1], compute pct move. Returns None if
    either side is missing.

    r63.3: Defensive — coerce strings to datetime so we don't crash on
    'str' object has no attribute 'tzinfo' (different data sources have
    different date formats; this layer normalizes).
    """
    if not closes_map: return None
    # r63.3: handle string input (Finnhub) AND datetime (yfinance)
    if isinstance(earnings_dt, str):
        try:
            earnings_dt = datetime.strptime(earnings_dt[:10], "%Y-%m-%d")
        except (ValueError, TypeError):
            return None
    if earnings_dt is None:
        return None
    if not hasattr(earnings_dt, "tzinfo"):
        return None  # not a datetime, skip
    ed_naive = earnings_dt.replace(tzinfo=None) if earnings_dt.tzinfo else earnings_dt
    ed_date = ed_naive.date()
    sorted_dates = sorted(closes_map.keys())  # iso strings sort correctly

    before = None
    for d_iso in reversed(sorted_dates):
        d = datetime.strptime(d_iso, "%Y-%m-%d").date()
        if d < ed_date:
            before = closes_map[d_iso]; break

    after = None
    for d_iso in sorted_dates:
        d = datetime.strptime(d_iso, "%Y-%m-%d").date()
        if d > ed_date:
            after = closes_map[d_iso]; break

    if before is None or after is None: return None
    return _pct_move(_safe_float(after), _safe_float(before))


# ─── Verdict logic ────────────────────────────────────────────────────────
def _build_verdict(d: dict) -> dict:
    """BUY_PREMIUM / SELL_PREMIUM / NEUTRAL based on history vs implied."""
    out = dict(d)
    stats = out.get("stats") or {}
    impl = out.get("implied_move_pct")
    hit_rate = stats.get("hit_implied_rate_pct")
    avg_abs = stats.get("avg_abs_move_pct")
    n = stats.get("n_quarters_analyzed", 0)

    if not impl or hit_rate is None or avg_abs is None or n < 4:
        out["verdict"] = "NEUTRAL"
        out["verdict_reason"] = "Insufficient data for premium-pricing verdict (need ≥4 historical quarters with moves and a current implied move)"
        return out

    if hit_rate >= 60 and avg_abs > impl:
        out["verdict"] = "BUY_PREMIUM"
        out["verdict_reason"] = (
            f"History beat implied move {hit_rate:.0f}% of last {n} quarters. "
            f"Avg historical move {avg_abs:.1f}% > current implied {impl:.1f}%. "
            f"Options appear under-priced relative to actual reaction history."
        )
    elif hit_rate <= 30 and avg_abs < impl * 0.7:
        out["verdict"] = "SELL_PREMIUM"
        out["verdict_reason"] = (
            f"History stayed inside implied move {100-hit_rate:.0f}% of last {n} quarters. "
            f"Avg historical move {avg_abs:.1f}% << current implied {impl:.1f}%. "
            f"Options appear over-priced; theta/vega seller's edge."
        )
    else:
        out["verdict"] = "NEUTRAL"
        out["verdict_reason"] = (
            f"Mixed signal — historical avg {avg_abs:.1f}% vs implied {impl:.1f}%, "
            f"hit rate {hit_rate:.0f}%. No clear premium-pricing edge."
        )
    return out


# ─── Public API ───────────────────────────────────────────────────────────
def get_earnings_intel(ticker: str, region: str = "US",
                       spot: Optional[float] = None,
                       atm_call: Optional[float] = None,
                       atm_put: Optional[float] = None) -> dict:
    """Main entry. See README for return schema."""
    ticker = (ticker or "").upper().strip()
    region = (region or "").upper().strip()

    # Indexes don't have company earnings
    if _is_index_ticker(ticker):
        return {
            "success": False, "ticker": ticker, "region": region,
            "verdict": "INCOMPLETE_DATA",
            "verdict_reason": "Index tickers do not have earnings reports",
            "data_quality": "INCOMPLETE",
            "missing_fields": ["earnings_dates"],
            "_source_chain": [],
        }

    cache_key = f"earnings_intel:{ticker}:{region}"
    cached = _smart_cache_get(cache_key)
    if cached is not None:
        # Recompute implied + verdict if live straddle prices supplied
        if spot and atm_call and atm_put:
            cached = dict(cached)
            cached["implied_move_pct"] = _compute_implied_move(spot, atm_call, atm_put)
            cached = _build_verdict(cached)
        return cached

    out = {
        "success": True, "ticker": ticker, "region": region,
        "next_earnings": None, "last_8_quarters": [], "stats": {},
        "implied_move_pct": None, "verdict": "NEUTRAL", "verdict_reason": "",
        "missing_fields": [], "data_quality": "FULL",
        "_source_chain": {},  # which provider answered each capability
    }

    # ─── 1. Earnings history (via central fallback chain) ───
    eh = ds.get_earnings_history(ticker, region)
    history = eh.get("data") if eh else []
    if eh: out["_source_chain"]["earnings_history"] = eh.get("_source")
    if not history:
        out["missing_fields"].append("earnings_history")

    # ─── 2. Next earnings ───
    ne = ds.get_next_earnings(ticker, region)
    if ne:
        out["next_earnings"] = {
            "date":        ne["date"],
            "date_iso":    ne["date_iso"],
            "days_until":  ne["days_until"],
            "weeks_until": round(ne["days_until"] / 7, 1),
        }
        out["_source_chain"]["next_earnings"] = ne.get("_source")
    else:
        out["missing_fields"].append("next_earnings_date")

    # ─── 3. Past 8 quarters ───
    now_utc = datetime.now(timezone.utc)
    past = []
    for r in history:
        d = r["date"]
        # r63.3: defensive — d may be string from Finnhub, coerce
        if isinstance(d, str):
            try:
                d = datetime.strptime(d[:10], "%Y-%m-%d")
            except (ValueError, TypeError):
                continue
        if not hasattr(d, "tzinfo"):
            continue
        d_aware = d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        if d_aware <= now_utc:
            past.append(r)
    past_recent = past[:_LOOKBACK_QUARTERS]

    # ─── 4. Price history for post-earnings move calc ───
    moves_filled = 0
    if past_recent:
        oldest = min(r["date"] for r in past_recent)
        newest = max(r["date"] for r in past_recent)
        ph = ds.get_price_history(
            ticker, region,
            start=(oldest - timedelta(days=10)),
            end=(newest + timedelta(days=10)),
        )
        if ph:
            out["_source_chain"]["price_history"] = ph.get("_source")
        closes = ph.get("closes") if ph else {}
        quarters = []
        for r in past_recent:
            move = _next_session_move(closes, r["date"]) if closes else None
            if move is not None: moves_filled += 1
            quarters.append({
                "date":                  r["date"].strftime("%Y-%m-%d"),
                "beat":                  r.get("beat"),
                "surprise_pct":          None,  # NSE may add this; yf doesn't reliably
                "next_session_move_pct": move,
            })
        out["last_8_quarters"] = quarters
        if moves_filled == 0:
            out["missing_fields"].append("post_earnings_moves")
    else:
        out["missing_fields"].append("post_earnings_moves")

    # ─── 5. Stats ───
    if out["last_8_quarters"] and moves_filled > 0:
        moves = [q["next_session_move_pct"] for q in out["last_8_quarters"]
                 if q["next_session_move_pct"] is not None]
        beats = [q["beat"] for q in out["last_8_quarters"] if q["beat"] is not None]
        abs_moves = sorted([abs(m) for m in moves])
        mid = len(abs_moves) // 2
        median_abs = abs_moves[mid] if len(abs_moves) % 2 == 1 \
                     else (abs_moves[mid - 1] + abs_moves[mid]) / 2
        out["stats"] = {
            "n_quarters_analyzed": len(moves),
            "n_beats":             sum(1 for b in beats if b is True),
            "n_misses":            sum(1 for b in beats if b is False),
            "beat_rate_pct":       (round(sum(1 for b in beats if b is True) /
                                          len(beats) * 100, 1) if beats else None),
            "avg_abs_move_pct":    round(sum(abs_moves) / len(abs_moves), 2),
            "median_abs_move_pct": round(median_abs, 2),
            "max_up_move_pct":     round(max(moves), 2),
            "max_down_move_pct":   round(min(moves), 2),
        }
    else:
        out["stats"] = {"n_quarters_analyzed": 0}

    # ─── 6. Implied move (live, doesn't go through central layer) ───
    if spot and atm_call and atm_put:
        out["implied_move_pct"] = _compute_implied_move(spot, atm_call, atm_put)
    else:
        out["missing_fields"].append("implied_move_inputs")

    # ─── 7. Hit-implied rate ───
    if out["implied_move_pct"] and out["last_8_quarters"]:
        moves = [abs(q["next_session_move_pct"]) for q in out["last_8_quarters"]
                 if q["next_session_move_pct"] is not None]
        if moves:
            hit = sum(1 for m in moves if m > out["implied_move_pct"])
            out["stats"]["hit_implied_rate_pct"] = round(hit / len(moves) * 100, 1)

    # ─── 8. Verdict + data-quality classification ───
    out = _build_verdict(out)
    n_missing = len(out["missing_fields"])
    if n_missing >= _INCOMPLETE_THRESHOLD:
        out["data_quality"] = "INCOMPLETE"
        out["verdict"] = "INCOMPLETE_DATA"
        # r61.5: human-readable reason instead of technical field names
        missing = set(out["missing_fields"])
        if "next_earnings_date" in missing and "implied_move_inputs" in missing:
            out["verdict_reason"] = (
                "No upcoming earnings catalyst on the calendar. "
                "Either the company recently reported (next earnings ~3 months away) "
                "or our data provider hasn't published the next confirmed date yet. "
                "Check back closer to the typical reporting cycle."
            )
        elif "next_earnings_date" in missing:
            out["verdict_reason"] = (
                "Next earnings date unavailable. The earnings calendar provider "
                "doesn't have a confirmed date for this ticker yet."
            )
        elif "implied_move_inputs" in missing:
            out["verdict_reason"] = (
                "Options chain unavailable for implied-move estimate. "
                "Either no options trade on this ticker or strike data is missing."
            )
        elif "earnings_history" in missing:
            out["verdict_reason"] = (
                "Earnings history unavailable. The data provider doesn't have past "
                "EPS or post-earnings move records for this ticker."
            )
        else:
            out["verdict_reason"] = f"Earnings analytics incomplete — missing: {', '.join(out['missing_fields'])}"
        # Always store technical detail for debugging
        out["_missing_technical"] = list(out["missing_fields"])
    elif n_missing > 0:
        out["data_quality"] = "PARTIAL"

    _smart_cache_set(cache_key, out, ttl=_CACHE_TTL)
    return out
