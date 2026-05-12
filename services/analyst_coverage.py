"""
r63.72.30 — Analyst Coverage & Ratings Explorer.

Aggregates analyst ratings + price targets across the tracked universe and
exposes a searchable/filterable feed.

PRIMARY DATA SOURCE: yfinance
  - ticker.recommendations         → DataFrame of recent rating actions (date, firm, to_grade, from_grade, action)
  - ticker.analyst_price_targets   → dict of {low, high, mean, current, median}
  - ticker.recommendations_summary → quick consensus rollup

DATA HONESTY:
  - yfinance is rate-limited on Render. We mitigate by:
      * Scheduled background prefetch every 30 min (cron-style via _last_prefetch_ts)
      * Caching results 30 min per ticker
      * Universe limited to ~100 tracked tickers per region
      * Each fetch has a 6-second hard timeout
  - Coverage is best for US large-caps; sparse for small-caps and Indian names
  - Some firms/analysts may show as "" if yfinance returns truncated data
  - Action types: 'init', 'up', 'down', 'reit', 'main' (yfinance uses these abbreviations)

Output schema for /api/analyst-coverage:
  {
    success: bool,
    region: "US" | "IN",
    actions: [
      {
        date: "2026-05-10",
        ticker: "NVDA",
        sector: "Technology",
        firm: "Morgan Stanley",
        action: "up",       # init|up|down|reit|main
        from_grade: "Hold",
        to_grade: "Buy",
        price_target: 1200,
        prior_target: 950,
        target_change_pct: 26.3,
      },
      ...
    ],
    universe_size: int,
    fetched_count: int,
    failed_tickers: [list],
    last_refresh_ts: float,
    data_note: str,
    partial_data: bool,
  }
"""

import time
import threading
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
from datetime import datetime, timedelta

# In-memory store keyed by (region) → {ticker: rating_data}
_coverage_store: Dict[str, Dict[str, dict]] = {"US": {}, "IN": {}}
_coverage_store_lock = threading.Lock()
_last_refresh_ts: Dict[str, float] = {"US": 0.0, "IN": 0.0}
_refresh_in_progress: Dict[str, bool] = {"US": False, "IN": False}

# Refresh cadence: full universe re-scan every 30 min
_REFRESH_INTERVAL_SEC = 1800

# Cap universe size per region (each ticker = one yfinance call)
_MAX_UNIVERSE_US = 100
_MAX_UNIVERSE_IN = 50


# ─── ACTION CLASSIFICATION ──────────────────────────────────────────────

_GRADE_RANK = {
    # Higher = more bullish
    "strong buy":    5, "buy": 4, "overweight": 4, "outperform": 4,
    "accumulate": 4, "long-term buy": 4, "positive": 4,
    "hold": 3, "neutral": 3, "market perform": 3, "equal-weight": 3,
    "sector perform": 3, "in-line": 3, "perform": 3,
    "underperform": 2, "underweight": 2, "negative": 2, "reduce": 2,
    "sell": 1, "strong sell": 1,
}


def _classify_action(from_grade: str, to_grade: str, action_raw: str) -> str:
    """
    Return one of: 'up', 'down', 'init', 'reit', 'main' (target change only).
    yfinance's 'action' field is sometimes 'up' / 'down' / 'init' / 'main' / 'reit'
    directly; we use it when available and fall back to grade comparison.
    """
    a = (action_raw or "").lower().strip()
    if a in ("up", "down", "init", "reit", "main"):
        return a
    # Fall back to grade comparison
    if not from_grade and to_grade:
        return "init"
    if from_grade and to_grade:
        f_rank = _GRADE_RANK.get(from_grade.lower().strip(), 0)
        t_rank = _GRADE_RANK.get(to_grade.lower().strip(), 0)
        if t_rank > f_rank:
            return "up"
        if t_rank < f_rank:
            return "down"
        return "reit"
    return "main"


def _action_label(action: str) -> dict:
    """Return display dict {label, color, icon}."""
    if action == "up":   return {"label": "UPGRADE",     "color": "#10b981", "icon": "↑"}
    if action == "down": return {"label": "DOWNGRADE",   "color": "#dc2626", "icon": "↓"}
    if action == "init": return {"label": "INITIATE",    "color": "#7c3aed", "icon": "★"}
    if action == "reit": return {"label": "REITERATE",   "color": "#94a3b8", "icon": "="}
    if action == "main": return {"label": "MAINTAIN",    "color": "#94a3b8", "icon": "·"}
    return {"label": "OTHER", "color": "#94a3b8", "icon": "?"}


# ─── PER-TICKER FETCH ───────────────────────────────────────────────────

def _fetch_one_ticker(ticker: str, region: str) -> Optional[dict]:
    """
    Fetch yfinance recommendations for one ticker. Hard 6s timeout via caller.
    Returns dict with actions list + targets, or None on failure.
    """
    try:
        import yfinance as yf
        try:
            from api import _yahoo_rate_wait
            _yahoo_rate_wait()
        except Exception:
            pass

        yf_sym = ticker if region.upper() == "US" else f"{ticker}.NS"
        tk = yf.Ticker(yf_sym)

        # 1. Recommendations history
        recs = None
        try:
            recs = tk.upgrades_downgrades
        except Exception:
            recs = None
        if recs is None or len(recs) == 0:
            try:
                recs = tk.recommendations  # fallback
            except Exception:
                recs = None

        actions = []
        if recs is not None and hasattr(recs, "iterrows"):
            try:
                # Only last 90 days
                cutoff = datetime.utcnow() - timedelta(days=90)
                for idx, row in recs.head(30).iterrows():
                    # idx might be the date OR there's a 'GradeDate' column
                    date_val = None
                    try:
                        if hasattr(idx, "to_pydatetime"):
                            date_val = idx.to_pydatetime()
                        elif "GradeDate" in row:
                            date_val = row["GradeDate"]
                    except Exception:
                        date_val = None

                    if not date_val:
                        continue

                    # Drop tz if present
                    try:
                        if hasattr(date_val, "tzinfo") and date_val.tzinfo is not None:
                            date_val = date_val.replace(tzinfo=None)
                    except Exception:
                        pass

                    try:
                        if date_val < cutoff:
                            continue
                    except Exception:
                        pass

                    firm        = str(row.get("Firm", "") or "").strip()
                    to_grade    = str(row.get("ToGrade", "") or "").strip()
                    from_grade  = str(row.get("FromGrade", "") or "").strip()
                    action_raw  = str(row.get("Action", "") or "").strip()

                    action = _classify_action(from_grade, to_grade, action_raw)

                    actions.append({
                        "date":          date_val.strftime("%Y-%m-%d"),
                        "date_ts":       int(date_val.timestamp()),
                        "ticker":        ticker.upper(),
                        "firm":          firm,
                        "action":        action,
                        "from_grade":    from_grade or None,
                        "to_grade":      to_grade or None,
                        "action_raw":    action_raw,
                    })
            except Exception:
                pass

        # 2. Info for sector + current price + targets
        info = {}
        try:
            info = tk.info or {}
        except Exception:
            info = {}

        sector       = (info.get("sector")        or "").strip()
        industry     = (info.get("industry")      or "").strip()
        current_px   = info.get("currentPrice")    or info.get("regularMarketPrice")
        target_mean  = info.get("targetMeanPrice") or info.get("targetMedianPrice")
        target_low   = info.get("targetLowPrice")
        target_high  = info.get("targetHighPrice")
        target_count = info.get("numberOfAnalystOpinions")
        rec_mean     = info.get("recommendationMean")        # 1=Buy, 5=Sell scale
        rec_key      = (info.get("recommendationKey") or "").strip()

        # Compute upside if both available
        upside_pct = None
        if current_px and target_mean and current_px > 0:
            upside_pct = round(((target_mean - current_px) / current_px) * 100, 2)

        # Decorate actions with sector + current target
        for a in actions:
            a["sector"]   = sector
            a["industry"] = industry

        return {
            "ticker":         ticker.upper(),
            "yf_symbol":      yf_sym,
            "sector":         sector,
            "industry":       industry,
            "current_price":  current_px,
            "target_mean":    target_mean,
            "target_low":     target_low,
            "target_high":    target_high,
            "target_count":   target_count,
            "upside_pct":     upside_pct,
            "rec_mean":       rec_mean,
            "rec_key":        rec_key,
            "actions":        actions,
        }
    except Exception:
        return None


def _fetch_one_with_timeout(ticker: str, region: str, timeout_sec: float = 6.0) -> Optional[dict]:
    """Run _fetch_one_ticker with a hard timeout."""
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(_fetch_one_ticker, ticker, region)
        try:
            return fut.result(timeout=timeout_sec)
        except (FuturesTimeoutError, Exception):
            return None


# ─── BACKGROUND PREFETCH ────────────────────────────────────────────────

def _refresh_universe(region: str, universe: List[str], max_workers: int = 4) -> dict:
    """
    Fetch ratings for the entire universe. Stores results in _coverage_store.
    Returns summary stats.
    """
    region_u = region.upper()

    if _refresh_in_progress.get(region_u):
        return {"skipped": "already in progress"}

    _refresh_in_progress[region_u] = True
    try:
        cap = _MAX_UNIVERSE_US if region_u == "US" else _MAX_UNIVERSE_IN
        universe = universe[:cap]

        fetched_count = 0
        failed = []
        new_store: Dict[str, dict] = {}

        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(_fetch_one_with_timeout, t, region_u, 6.0): t for t in universe}
            for fut in as_completed(futures, timeout=180):
                t = futures[fut]
                try:
                    res = fut.result()
                    if res:
                        new_store[t] = res
                        fetched_count += 1
                    else:
                        failed.append(t)
                except Exception:
                    failed.append(t)

        with _coverage_store_lock:
            _coverage_store[region_u] = new_store
            _last_refresh_ts[region_u] = time.time()

        return {
            "fetched_count":  fetched_count,
            "failed_count":   len(failed),
            "failed_tickers": failed[:20],
            "universe_size":  len(universe),
            "refreshed_at":   time.time(),
        }
    finally:
        _refresh_in_progress[region_u] = False


def _maybe_refresh(region: str, universe: List[str]) -> None:
    """If our store is stale, kick off a refresh in the background (non-blocking)."""
    region_u = region.upper()
    now = time.time()
    if (now - _last_refresh_ts.get(region_u, 0)) > _REFRESH_INTERVAL_SEC:
        if not _refresh_in_progress.get(region_u):
            # Spawn in background thread so the API call returns quickly
            t = threading.Thread(target=_refresh_universe, args=(region_u, universe), daemon=True)
            t.start()


# ─── PUBLIC API ─────────────────────────────────────────────────────────

def get_analyst_coverage(
    region: str,
    universe: List[str],
    *,
    days_back: int = 30,
    action_filter: str = "all",       # all | up | down | init | reit
    sector_filter: str = "",          # case-insensitive substring
    ticker_filter: str = "",          # case-insensitive exact match
    firm_filter: str = "",            # case-insensitive substring
    min_target_change_pct: Optional[float] = None,
    sort_by: str = "date_desc",       # date_desc | date_asc | target_change_desc | ticker
    limit: int = 200,
) -> dict:
    """
    Return filtered list of analyst actions from the in-memory store.
    Triggers background refresh if store is stale.
    """
    region_u = region.upper()

    # Trigger background refresh if stale
    _maybe_refresh(region_u, universe)

    with _coverage_store_lock:
        store = dict(_coverage_store.get(region_u, {}))
        last_refresh = _last_refresh_ts.get(region_u, 0.0)

    # Build the flat actions list across all tickers in store
    all_actions: List[dict] = []
    cutoff_ts = int((datetime.utcnow() - timedelta(days=days_back)).timestamp())

    for ticker, data in store.items():
        for a in data.get("actions", []):
            if a.get("date_ts", 0) < cutoff_ts:
                continue
            # Decorate with current price + target if not present
            a2 = dict(a)
            a2["current_price"] = data.get("current_price")
            a2["target_mean"]   = data.get("target_mean")
            a2["upside_pct"]    = data.get("upside_pct")
            a2["action_meta"]   = _action_label(a2.get("action", ""))
            all_actions.append(a2)

    # Apply filters
    def passes(a):
        if action_filter and action_filter != "all" and a.get("action") != action_filter:
            return False
        if sector_filter and sector_filter.lower() not in (a.get("sector", "").lower()):
            return False
        if ticker_filter and ticker_filter.upper() != a.get("ticker", "").upper():
            return False
        if firm_filter and firm_filter.lower() not in (a.get("firm", "").lower()):
            return False
        if min_target_change_pct is not None:
            tc = a.get("target_change_pct")
            if tc is None or abs(tc) < min_target_change_pct:
                return False
        return True

    filtered = [a for a in all_actions if passes(a)]

    # Sort
    if sort_by == "date_desc":
        filtered.sort(key=lambda x: x.get("date_ts", 0), reverse=True)
    elif sort_by == "date_asc":
        filtered.sort(key=lambda x: x.get("date_ts", 0))
    elif sort_by == "ticker":
        filtered.sort(key=lambda x: x.get("ticker", ""))
    elif sort_by == "target_change_desc":
        filtered.sort(key=lambda x: abs(x.get("target_change_pct") or 0), reverse=True)

    # Limit
    capped = filtered[:limit]

    # Per-region universe of sectors (for filter dropdown)
    sectors_in_store = sorted({d.get("sector", "") for d in store.values() if d.get("sector")})

    return {
        "success":         True,
        "region":          region_u,
        "actions":         capped,
        "total_filtered":  len(filtered),
        "total_in_store":  len(all_actions),
        "universe_size":   len(store),
        "tracked_tickers": sorted(store.keys()),
        "sectors":         sectors_in_store,
        "last_refresh_ts": last_refresh,
        "refresh_age_sec": int(time.time() - last_refresh) if last_refresh else None,
        "store_warming":   last_refresh == 0.0,
        "data_note":       (
            f"Coverage limited to top {_MAX_UNIVERSE_US if region_u == 'US' else _MAX_UNIVERSE_IN} tracked "
            f"{region_u} tickers (yfinance). Background refresh every 30 min."
        ),
        "partial_data":    last_refresh == 0.0 or len(store) == 0,
    }


def get_ticker_coverage(ticker: str, region: str = "US") -> dict:
    """Return per-ticker coverage detail (used in DD report panel)."""
    region_u = region.upper()
    t = ticker.strip().upper()

    with _coverage_store_lock:
        cached = _coverage_store.get(region_u, {}).get(t)

    if cached and (time.time() - _last_refresh_ts.get(region_u, 0)) < _REFRESH_INTERVAL_SEC:
        return _format_ticker_coverage(cached, from_cache=True)

    # On-demand fetch (small + fast for one ticker)
    fresh = _fetch_one_with_timeout(t, region_u, timeout_sec=6.0)
    if fresh:
        with _coverage_store_lock:
            _coverage_store.setdefault(region_u, {})[t] = fresh
        return _format_ticker_coverage(fresh, from_cache=False)

    return {
        "success":      False,
        "ticker":       t,
        "region":       region_u,
        "reason":       "No coverage data available (yfinance returned nothing or timed out).",
        "partial_data": True,
    }


def _format_ticker_coverage(data: dict, from_cache: bool) -> dict:
    actions = data.get("actions", [])
    # Sort by date desc
    actions = sorted(actions, key=lambda x: x.get("date_ts", 0), reverse=True)
    for a in actions:
        a["action_meta"] = _action_label(a.get("action", ""))

    # Consensus from rec_mean: 1=Buy → 5=Sell
    rec_mean = data.get("rec_mean")
    rec_key  = data.get("rec_key")
    consensus_label = None
    consensus_color = None
    if rec_mean is not None:
        if rec_mean <= 1.5:
            consensus_label, consensus_color = "STRONG BUY", "#059669"
        elif rec_mean <= 2.5:
            consensus_label, consensus_color = "BUY", "#10b981"
        elif rec_mean <= 3.5:
            consensus_label, consensus_color = "HOLD", "#94a3b8"
        elif rec_mean <= 4.5:
            consensus_label, consensus_color = "UNDERPERFORM", "#dc2626"
        else:
            consensus_label, consensus_color = "SELL", "#991b1b"

    return {
        "success":         True,
        "ticker":          data["ticker"],
        "sector":          data.get("sector"),
        "industry":        data.get("industry"),
        "current_price":   data.get("current_price"),
        "target_mean":     data.get("target_mean"),
        "target_low":      data.get("target_low"),
        "target_high":     data.get("target_high"),
        "target_count":    data.get("target_count"),
        "upside_pct":      data.get("upside_pct"),
        "rec_mean":        rec_mean,
        "rec_key":         rec_key,
        "consensus_label": consensus_label,
        "consensus_color": consensus_color,
        "actions":         actions,
        "action_count":    len(actions),
        "from_cache":      from_cache,
    }


def force_refresh(region: str, universe: List[str]) -> dict:
    """Force a synchronous refresh — used for manual 'refresh now' button."""
    return _refresh_universe(region, universe)
