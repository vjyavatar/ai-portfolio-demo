"""
Celesys — Centralized Region-Aware Data Sources
================================================
ONE module. Every service uses it. No service writes fallback logic again.

Public API:
  data_sources.get_quote(symbol, region)             → dict | None
  data_sources.get_price_history(symbol, region, start, end) → dict | None
  data_sources.get_earnings_history(symbol, region)  → list | None
  data_sources.get_next_earnings(symbol, region)     → dict | None
  data_sources.get_quarterly_results(symbol, region) → list | None

Every return value carries `_source` (which provider answered) and
`_partial` (True if some fields missing).

Region routing (priority order, tries each until one succeeds):
  US:  yfinance → google_finance
  IN:  nse → yfinance(.NS) → google_finance

Integrates with existing infrastructure:
  • _cb_allow / _cb_record_success / _cb_record_failure (circuit breaker)
  • diag_log("FALLBACK", ...)                            (instrumentation)
  • _smart_cache_get / _smart_cache_set                  (caching)
  • _nse_get / fetch_google_finance                      (existing helpers)
  • _safe_float / _safe_int                              (numeric safety)

Per CDS v2.0 "no fake assumptions" rule:
  • Returns None when ALL sources fail for that capability+region
  • Sets _partial=True when a source answered but with gaps
  • Does NOT substitute defaults for missing fields
"""

from __future__ import annotations
import math
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Any
import finnhub_handlers as _fh  # r63.0: Finnhub primary for US

# Symbols imported from api.py at runtime. Standalone fallbacks for testing.
try:
    from api import (
        _safe_float, _safe_int,
        _smart_cache_get, _smart_cache_set,
        _cb_allow, _cb_record_success, _cb_record_failure,
        diag_log,
        _nse_get,
        fetch_google_finance,
    )
    import yfinance as yf
    _CELESYS_INTEGRATED = True
except ImportError:
    _CELESYS_INTEGRATED = False
    # Test fallbacks
    def _safe_float(v, default=0.0):
        try:
            f = float(v); return f if not (math.isnan(f) or math.isinf(f)) else default
        except (TypeError, ValueError): return default
    def _safe_int(v, default=0):
        try: return int(float(v))
        except (TypeError, ValueError): return default
    _local_cache = {}
    def _smart_cache_get(k):
        e = _local_cache.get(k)
        return e['data'] if e and time.time() - e['ts'] < e['ttl'] else None
    def _smart_cache_set(k, d, ttl=120): _local_cache[k] = {'data': d, 'ts': time.time(), 'ttl': ttl}
    def _cb_allow(p): return True
    def _cb_record_success(p): pass
    def _cb_record_failure(p, reason=""): pass
    def diag_log(ch, ev, meta=None): pass
    def _nse_get(url, retries=2): return None
    def fetch_google_finance(t): return None
    try: import yfinance as yf
    except ImportError: yf = None


# ─── Region capability matrix ─────────────────────────────────────────────
# For each (capability, region) — try sources in this priority order.
# Edit here to change fallback behavior for ALL services at once.
_CAPABILITIES = {
    # r63.0: Finnhub primary for US (Yahoo blocks Render IP). India unchanged.
    "quote": {
        "US": ["finnhub", "yfinance", "google_finance"],
        "IN": ["nse_quote", "yfinance", "google_finance"],
    },
    "price_history": {
        "US": ["finnhub", "yfinance", "google_finance"],
        "IN": ["yfinance", "nse_chart", "google_finance"],
    },
    "earnings_history": {
        "US": ["finnhub", "yfinance"],
        "IN": ["nse_corp_info", "yfinance"],
    },
    "next_earnings": {
        "US": ["yfinance"],  # finnhub free tier doesn't have this endpoint
        "IN": ["nse_event_calendar", "yfinance"],
    },
    "quarterly_results": {
        "US": ["finnhub", "yfinance"],
        "IN": ["nse_corp_info", "yfinance"],
    },
}

_CACHE_TTL = {
    "quote":              60,        # 1 min
    "price_history":      300,       # 5 min
    "earnings_history":   900,       # 15 min
    "next_earnings":      900,       # 15 min
    "quarterly_results":  900,       # 15 min
}


# ─── Symbol mapping helpers ───────────────────────────────────────────────
def _yf_symbol(symbol: str, region: str) -> str:
    """Map Celesys ticker → yfinance ticker."""
    s = (symbol or "").upper().strip()
    if not s: return s
    if region.upper() == "IN" and not s.endswith(".NS") and not s.endswith(".BO"):
        idx_map = {
            "NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK", "SENSEX": "^BSESN",
            "FINNIFTY": "NIFTY_FIN_SERVICE.NS", "MIDCPNIFTY": "NIFTY_MID_SELECT.NS",
        }
        return idx_map.get(s, f"{s}.NS")
    return s


def _strip_in_suffix(symbol: str) -> str:
    """RELIANCE.NS → RELIANCE for NSE direct API calls."""
    s = (symbol or "").upper().strip()
    return s.replace(".NS", "").replace(".BO", "")


def _is_index(symbol: str) -> bool:
    s = (symbol or "").upper().strip()
    return s in {"NIFTY", "BANKNIFTY", "SENSEX", "FINNIFTY", "MIDCPNIFTY",
                 "NIFTYIT", "SPX", "NDX", "RUT", "DJI", "VIX",
                 "^NSEI", "^NSEBANK", "^BSESN"}


# ─── Source handlers ──────────────────────────────────────────────────────
# Each handler: (symbol, region, **kwargs) → result dict | None
# Handlers should NOT catch their own exceptions — the dispatcher does that.

def _yf_quote(symbol: str, region: str, **kw) -> Optional[dict]:
    if yf is None: return None
    yf_sym = _yf_symbol(symbol, region)
    t = yf.Ticker(yf_sym)
    info = t.fast_info if hasattr(t, 'fast_info') else {}
    last = _safe_float(info.get('last_price') or info.get('lastPrice'))
    if last <= 0:
        # Fallback to history
        h = t.history(period="2d", interval="1d")
        if h is None or h.empty: return None
        last = _safe_float(h["Close"].iloc[-1])
    if last <= 0: return None
    prev = _safe_float(info.get('previous_close') or info.get('previousClose'))
    return {
        "symbol": symbol, "region": region,
        "price": last, "prev_close": prev or last,
        "currency": "INR" if region == "IN" else "USD",
    }


def _gf_quote(symbol: str, region: str, **kw) -> Optional[dict]:
    yf_sym = _yf_symbol(symbol, region)
    info = fetch_google_finance(yf_sym)
    if not info: return None
    price = _safe_float(info.get("currentPrice"))
    if price <= 0: return None
    return {
        "symbol": symbol, "region": region,
        "price": price, "prev_close": _safe_float(info.get("previousClose")) or price,
        "currency": info.get("currency", "USD"),
        "_partial": True,  # GF doesn't have intraday change details
    }


def _nse_quote(symbol: str, region: str, **kw) -> Optional[dict]:
    if region != "IN": return None
    sym = _strip_in_suffix(symbol)
    data = _nse_get(f"https://www.nseindia.com/api/quote-equity?symbol={sym}")
    if not data: return None
    pi = data.get("priceInfo", {}) or {}
    last = _safe_float(pi.get("lastPrice"))
    if last <= 0: return None
    return {
        "symbol": symbol, "region": "IN",
        "price": last,
        "prev_close": _safe_float(pi.get("previousClose")) or last,
        "currency": "INR",
        "change": _safe_float(pi.get("change")),
        "change_pct": _safe_float(pi.get("pChange")),
    }


def _yf_price_history(symbol: str, region: str, start=None, end=None, **kw) -> Optional[dict]:
    if yf is None: return None
    yf_sym = _yf_symbol(symbol, region)
    kwargs = {"interval": "1d", "auto_adjust": False}
    if start: kwargs["start"] = start.strftime("%Y-%m-%d") if hasattr(start, 'strftime') else start
    if end:   kwargs["end"]   = end.strftime("%Y-%m-%d")   if hasattr(end, 'strftime')   else end
    if not start and not end: kwargs["period"] = "2y"
    t = yf.Ticker(yf_sym)
    h = t.history(**kwargs)
    if h is None or h.empty: return None
    h.index = h.index.tz_localize(None) if h.index.tz is not None else h.index
    closes = {dt.date().isoformat(): _safe_float(c) for dt, c in h["Close"].dropna().items()}
    if not closes: return None
    return {"symbol": symbol, "region": region, "closes": closes}


def _nse_chart_history(symbol: str, region: str, start=None, end=None, **kw) -> Optional[dict]:
    if region != "IN": return None
    sym = _strip_in_suffix(symbol)
    # NSE historical endpoint
    if not start: start = datetime.now() - timedelta(days=730)
    if not end:   end = datetime.now()
    s_str = start.strftime("%d-%m-%Y") if hasattr(start, 'strftime') else start
    e_str = end.strftime("%d-%m-%Y")   if hasattr(end, 'strftime')   else end
    url = (f"https://www.nseindia.com/api/historical/cm/equity?symbol={sym}"
           f"&from={s_str}&to={e_str}")
    data = _nse_get(url)
    if not data: return None
    rows = data.get("data") or []
    if not rows: return None
    closes = {}
    for r in rows:
        try:
            dt_str = r.get("CH_TIMESTAMP") or r.get("mTIMESTAMP")
            close = _safe_float(r.get("CH_CLOSING_PRICE") or r.get("mClose"))
            if dt_str and close > 0:
                # NSE returns YYYY-MM-DD or DD-MMM-YYYY — normalize
                try:
                    if "-" in dt_str and len(dt_str.split("-")[0]) == 4:
                        d_iso = dt_str
                    else:
                        d_iso = datetime.strptime(dt_str, "%d-%b-%Y").date().isoformat()
                except ValueError:
                    continue
                closes[d_iso] = close
        except Exception:
            continue
    if not closes: return None
    return {"symbol": symbol, "region": "IN", "closes": closes}


def _yf_earnings_history(symbol: str, region: str, **kw) -> Optional[list]:
    if yf is None: return None
    yf_sym = _yf_symbol(symbol, region)
    t = yf.Ticker(yf_sym)
    df = t.earnings_dates
    if df is None or df.empty: return None
    rows = []
    for idx, row in df.iterrows():
        try:
            dt = idx.to_pydatetime() if hasattr(idx, 'to_pydatetime') else idx
            raw_est = row.get("EPS Estimate") if "EPS Estimate" in df.columns else None
            raw_act = row.get("Reported EPS") if "Reported EPS" in df.columns else None
            est = None if (raw_est is None or (isinstance(raw_est, float) and math.isnan(raw_est))) \
                  else _safe_float(raw_est)
            act = None if (raw_act is None or (isinstance(raw_act, float) and math.isnan(raw_act))) \
                  else _safe_float(raw_act)
            beat = bool(act > est) if (est is not None and act is not None) else None
            rows.append({"date": dt, "eps_estimate": est, "eps_actual": act, "beat": beat})
        except Exception:
            continue
    rows.sort(key=lambda r: r["date"], reverse=True)
    return rows or None


def _nse_corp_info_earnings(symbol: str, region: str, **kw) -> Optional[list]:
    """
    NSE corporate-info endpoint returns quarterlyResults with EPS data.
    This is the primary India source — yfinance is unreliable for .NS tickers.
    """
    if region != "IN": return None
    sym = _strip_in_suffix(symbol)
    url = f"https://www.nseindia.com/api/top-corp-info?symbol={sym}&market=equities"
    data = _nse_get(url)
    if not data: return None
    fin = data.get("financial_results", {}) or {}
    qr = fin.get("quarterly_results") or fin.get("quarterlyResults") or []
    if not qr: return None
    rows = []
    for q in qr:
        try:
            # NSE shape varies; try multiple key names
            from_dt = q.get("toDate") or q.get("to_date") or q.get("toDt") or q.get("date")
            eps = _safe_float(q.get("basicEps") or q.get("basic_eps") or q.get("eps"), default=None)
            if from_dt and eps is not None:
                # Parse DD-MMM-YYYY or YYYY-MM-DD
                parsed = None
                for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d-%m-%Y"):
                    try: parsed = datetime.strptime(from_dt, fmt); break
                    except ValueError: continue
                if parsed:
                    rows.append({
                        "date": parsed,
                        "eps_estimate": None,  # NSE doesn't surface consensus estimates
                        "eps_actual": eps,
                        "beat": None,
                    })
        except Exception:
            continue
    rows.sort(key=lambda r: r["date"], reverse=True)
    return rows or None


def _yf_next_earnings(symbol: str, region: str, **kw) -> Optional[dict]:
    if yf is None: return None
    yf_sym = _yf_symbol(symbol, region)
    t = yf.Ticker(yf_sym)
    df = t.earnings_dates
    if df is None or df.empty: return None
    now = datetime.now(timezone.utc)
    upcoming = []
    for idx in df.index:
        dt = idx.to_pydatetime() if hasattr(idx, 'to_pydatetime') else idx
        dt_aware = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        if dt_aware > now:
            upcoming.append(dt_aware)
    if not upcoming: return None
    nxt = min(upcoming)
    return {
        "date": nxt.strftime("%Y-%m-%d"),
        "date_iso": nxt.isoformat(),
        "days_until": max(0, (nxt - now).days),
    }


def _nse_event_calendar(symbol: str, region: str, **kw) -> Optional[dict]:
    if region != "IN": return None
    sym = _strip_in_suffix(symbol)
    url = f"https://www.nseindia.com/api/event-calendar?index=equities&symbol={sym}"
    data = _nse_get(url)
    if not data: return None
    rows = data if isinstance(data, list) else data.get("data") or []
    now = datetime.now()
    upcoming = []
    for r in rows:
        try:
            purpose = (r.get("purpose") or "").upper()
            if "RESULT" not in purpose and "EARNING" not in purpose: continue
            dt_str = r.get("date") or r.get("bm_desc")
            if not dt_str: continue
            for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d-%m-%Y"):
                try:
                    parsed = datetime.strptime(dt_str, fmt)
                    if parsed > now:
                        upcoming.append(parsed)
                    break
                except ValueError: continue
        except Exception: continue
    if not upcoming: return None
    nxt = min(upcoming)
    return {
        "date": nxt.strftime("%Y-%m-%d"),
        "date_iso": nxt.isoformat(),
        "days_until": max(0, (nxt - now).days),
    }


# ─── Source registry ──────────────────────────────────────────────────────
# Maps source-id → {capability: handler}
_HANDLERS = {
    # r63.0: Finnhub free tier — US only, ~30 of yfinance's fields covered
    "finnhub": {
        "quote":              _fh.get_quote,
        "price_history":      _fh.get_price_history,
        "earnings_history":   _fh.get_earnings_history,
        "quarterly_results":  _fh.get_earnings_history,
    },
    "yfinance": {
        "quote":              _yf_quote,
        "price_history":      _yf_price_history,
        "earnings_history":   _yf_earnings_history,
        "next_earnings":      _yf_next_earnings,
        "quarterly_results":  _yf_earnings_history,  # same shape
    },
    "google_finance": {
        "quote": _gf_quote,
        # GF doesn't surface earnings or historical OHLC in our scraper
    },
    "nse_quote":          { "quote": _nse_quote },
    "nse_chart":          { "price_history": _nse_chart_history },
    "nse_corp_info":      {
        "earnings_history":  _nse_corp_info_earnings,
        "quarterly_results": _nse_corp_info_earnings,
    },
    "nse_event_calendar": { "next_earnings": _nse_event_calendar },
}


# ─── Central dispatcher ───────────────────────────────────────────────────
def _dispatch(capability: str, symbol: str, region: str, **kwargs) -> Optional[dict]:
    """
    Try sources in priority order until one returns non-empty.
    Records circuit-breaker outcomes and emits diag_log per attempt.
    """
    region = (region or "").upper()
    cache_key = f"ds:{capability}:{symbol}:{region}"
    if not kwargs:  # only cache when no per-call params
        cached = _smart_cache_get(cache_key)
        if cached is not None:
            return cached

    sources = _CAPABILITIES.get(capability, {}).get(region, [])
    if not sources:
        diag_log("FALLBACK", "no_sources", {"cap": capability, "reg": region, "sym": symbol})
        return None

    last_error = None
    for src in sources:
        if not _cb_allow(src):
            diag_log("FALLBACK", "skip_breaker_open",
                     {"cap": capability, "src": src, "sym": symbol})
            continue
        handler = _HANDLERS.get(src, {}).get(capability)
        if handler is None:
            continue
        try:
            t0 = time.time()
            result = handler(symbol, region, **kwargs)
            ms = int((time.time() - t0) * 1000)
            if result:
                # Wrap in envelope
                if isinstance(result, dict):
                    result["_source"] = src
                else:  # list
                    result = {"data": result, "_source": src}
                _cb_record_success(src)
                diag_log("FALLBACK", "ok",
                         {"cap": capability, "src": src, "sym": symbol, "ms": ms})
                ttl = _CACHE_TTL.get(capability, 120)
                if not kwargs:
                    _smart_cache_set(cache_key, result, ttl=ttl)
                return result
            else:
                _cb_record_failure(src, reason="empty_result")
                diag_log("FALLBACK", "empty",
                         {"cap": capability, "src": src, "sym": symbol, "ms": ms})
        except Exception as e:
            err = str(e)[:120]
            last_error = err
            _cb_record_failure(src, reason=err)
            diag_log("FALLBACK", "error",
                     {"cap": capability, "src": src, "sym": symbol, "err": err})

    diag_log("FALLBACK", "exhausted",
             {"cap": capability, "reg": region, "sym": symbol, "last_err": last_error})
    return None


# ─── Public API ───────────────────────────────────────────────────────────
def get_quote(symbol: str, region: str) -> Optional[dict]:
    """Return {price, prev_close, currency, _source} or None."""
    return _dispatch("quote", symbol, region)


def get_price_history(symbol: str, region: str,
                      start: Optional[Any] = None,
                      end: Optional[Any] = None) -> Optional[dict]:
    """Return {closes: {iso_date: float}, _source} or None."""
    return _dispatch("price_history", symbol, region, start=start, end=end)


def get_earnings_history(symbol: str, region: str) -> Optional[dict]:
    """Return {data: [{date, eps_estimate, eps_actual, beat}, ...], _source} or None."""
    if _is_index(symbol):
        return None
    return _dispatch("earnings_history", symbol, region)


def get_next_earnings(symbol: str, region: str) -> Optional[dict]:
    """Return {date, days_until, _source} or None."""
    if _is_index(symbol):
        return None
    return _dispatch("next_earnings", symbol, region)


def get_quarterly_results(symbol: str, region: str) -> Optional[dict]:
    """Return {data: [{date, eps_actual, ...}, ...], _source} or None."""
    if _is_index(symbol):
        return None
    return _dispatch("quarterly_results", symbol, region)


# ─── Diagnostics ──────────────────────────────────────────────────────────
def get_source_status() -> dict:
    """Snapshot of which sources are healthy. Hit /api/data-sources-status to expose."""
    statuses = {}
    for src in _HANDLERS.keys():
        try:
            from api import _cb_state
            cb = _cb_state.get(src, {})
            statuses[src] = {
                "state":               cb.get("state", "CLOSED"),
                "consecutive_failures": cb.get("consecutive_failures", 0),
                "total_successes":      cb.get("total_successes", 0),
                "total_failures":       cb.get("total_failures", 0),
                "last_success_ts":      cb.get("last_success_ts"),
                "last_failure_ts":      cb.get("last_failure_ts"),
            }
        except Exception:
            statuses[src] = {"state": "UNKNOWN"}
    return {
        "sources":      statuses,
        "capabilities": _CAPABILITIES,
        "ts":           time.time(),
    }
