"""
finnhub_handlers.py — r63.0
═══════════════════════════════════════════════════════════════════════
Finnhub data adapter. Built on the free tier API.

PRINCIPLE: Adapt Finnhub's response shape into yfinance-compatible dicts
so the rest of api.py works unchanged. The DD endpoint reads `info` like
yfinance gives it; we synthesize that shape from Finnhub endpoints.

FREE TIER endpoints we use:
  /quote                      — current price, day OHLC, prev close
  /stock/profile2             — name, industry, market cap, country
  /stock/metric               — basic_financials (PE, ROE, margins, etc)
  /stock/candle               — historical OHLCV (1Y on free tier)
  /stock/earnings             — earnings surprise history (last 4 quarters)

FREE TIER limitations (handled gracefully — fall through):
  - No insider transactions
  - No 13F institutional ownership
  - No analyst recommendations / price targets
  - 60 calls/minute rate limit (we cache aggressively)
  - US tickers only (we don't try Finnhub for IN tickers)

KILL SWITCH: env var FINNHUB_DISABLED=1 → all handlers return None instantly.
"""

import os
import time
import json
import urllib.request
import urllib.parse
from typing import Optional, Any

# Read API key from env (configured in Render by user)
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "").strip()
FINNHUB_DISABLED = os.getenv("FINNHUB_DISABLED", "").strip() in ("1", "true", "yes")
FINNHUB_BASE = "https://finnhub.io/api/v1"

# Internal rate-limit pacer (free tier is 60/min = 1/sec; we pace 1.2 sec for safety)
_finnhub_last_call_ts = [0.0]
_FINNHUB_MIN_INTERVAL_SEC = 1.2

# Health tracking — exposed via /api/version
_finnhub_stats = {
    "calls_total": 0,
    "calls_success": 0,
    "calls_failed": 0,
    "last_success_ts": None,
    "last_failure_ts": None,
    "last_error": None,
}


def _is_enabled() -> bool:
    """Should we try Finnhub at all?"""
    return bool(FINNHUB_API_KEY) and not FINNHUB_DISABLED


def _pace():
    """Throttle to stay under 60 calls/min on free tier."""
    now = time.time()
    elapsed = now - _finnhub_last_call_ts[0]
    if elapsed < _FINNHUB_MIN_INTERVAL_SEC:
        time.sleep(_FINNHUB_MIN_INTERVAL_SEC - elapsed)
    _finnhub_last_call_ts[0] = time.time()


def _safe_float(x, default=0.0) -> float:
    try:
        if x is None: return default
        return float(x)
    except (ValueError, TypeError):
        return default


def _safe_int(x, default=0) -> int:
    try:
        if x is None: return default
        return int(float(x))
    except (ValueError, TypeError):
        return default


def _fh_get(path: str, params: Optional[dict] = None, timeout: int = 8) -> Optional[Any]:
    """Make a Finnhub API call. Returns parsed JSON or None on any failure.
    Updates internal stats. Catches all exceptions — never raises."""
    if not _is_enabled():
        return None
    params = params or {}
    params["token"] = FINNHUB_API_KEY
    qs = urllib.parse.urlencode(params)
    url = f"{FINNHUB_BASE}{path}?{qs}"

    _pace()
    _finnhub_stats["calls_total"] += 1
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Celesys/4.63 (compatible; institutional research)"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if r.status != 200:
                _finnhub_stats["calls_failed"] += 1
                _finnhub_stats["last_failure_ts"] = time.time()
                _finnhub_stats["last_error"] = f"HTTP {r.status}"
                return None
            body = r.read().decode("utf-8", errors="replace")
        data = json.loads(body)
        _finnhub_stats["calls_success"] += 1
        _finnhub_stats["last_success_ts"] = time.time()
        return data
    except urllib.error.HTTPError as e:
        _finnhub_stats["calls_failed"] += 1
        _finnhub_stats["last_failure_ts"] = time.time()
        _finnhub_stats["last_error"] = f"HTTP {e.code}"
        return None
    except Exception as e:
        _finnhub_stats["calls_failed"] += 1
        _finnhub_stats["last_failure_ts"] = time.time()
        _finnhub_stats["last_error"] = f"{type(e).__name__}: {str(e)[:80]}"
        return None


def get_stats() -> dict:
    """For /api/version diagnostics."""
    return {
        "enabled": _is_enabled(),
        "has_key": bool(FINNHUB_API_KEY),
        "key_prefix": (FINNHUB_API_KEY[:6] + "...") if FINNHUB_API_KEY else None,
        "disabled": FINNHUB_DISABLED,
        **dict(_finnhub_stats),
    }


# ═══════════════════════════════════════════════════════════════════════
# Public capability handlers
# ═══════════════════════════════════════════════════════════════════════

def get_quote(symbol: str, region: str, **kwargs) -> Optional[dict]:
    """Return {price, prev_close, currency, _source} or None.
    Format matches data_sources.py expected shape.
    """
    if region != "US":
        return None  # Free tier US-only
    if not _is_enabled():
        return None

    data = _fh_get("/quote", {"symbol": symbol})
    if not data:
        return None
    price = _safe_float(data.get("c"))
    if price <= 0:
        return None
    return {
        "symbol": symbol,
        "region": region,
        "price": price,
        "prev_close": _safe_float(data.get("pc")) or price,
        "open": _safe_float(data.get("o")),
        "high": _safe_float(data.get("h")),
        "low": _safe_float(data.get("l")),
        "currency": "USD",
    }


def get_yfinance_shaped_info(symbol: str, region: str = "US") -> Optional[dict]:
    """KEY ADAPTER — returns a dict shaped like yfinance Ticker.info,
    populated from Finnhub. The DD endpoint reads `info` like yfinance gives it,
    so synthesizing that shape lets the rest of the code work unchanged.

    Free tier coverage (~30 of yfinance's 80 fields):
      regularMarketPrice, previousClose, dayHigh, dayLow, open
      marketCap, sharesOutstanding
      longName, shortName, sector, industry, country
      currency, exchange
      trailingPE, forwardPE, priceToBook, priceToSalesTrailing12Months
      profitMargins, operatingMargins, grossMargins
      returnOnAssets, returnOnEquity
      revenueGrowth, earningsGrowth
      totalCash, totalDebt, bookValue
      fiftyDayAverage, twoHundredDayAverage
      averageVolume

    NOT covered by free tier (fields will be missing — caller falls back gracefully):
      heldPercentInsiders, heldPercentInstitutions
      shortPercentOfFloat
      analyst targets, recommendations
      detailed insider transactions
    """
    if region != "US":
        return None
    if not _is_enabled():
        return None

    info = {}

    # 1. Quote endpoint — current price + OHLC
    quote = _fh_get("/quote", {"symbol": symbol})
    if quote and _safe_float(quote.get("c")) > 0:
        info["regularMarketPrice"] = _safe_float(quote.get("c"))
        info["previousClose"] = _safe_float(quote.get("pc")) or info["regularMarketPrice"]
        info["open"] = _safe_float(quote.get("o"))
        info["dayHigh"] = _safe_float(quote.get("h"))
        info["dayLow"] = _safe_float(quote.get("l"))
        info["currency"] = "USD"
    else:
        # No quote = no point continuing
        return None

    # 2. Profile — name/sector/industry/marketCap
    profile = _fh_get("/stock/profile2", {"symbol": symbol})
    if profile:
        info["longName"] = profile.get("name") or symbol
        info["shortName"] = profile.get("name") or symbol
        info["sector"] = profile.get("finnhubIndustry") or "Unknown"
        info["industry"] = profile.get("finnhubIndustry") or "Unknown"
        info["country"] = profile.get("country", "US")
        info["exchange"] = profile.get("exchange", "")
        info["website"] = profile.get("weburl", "")
        info["logo_url"] = profile.get("logo", "")
        # marketCapitalization is in millions on Finnhub; yfinance uses raw dollars
        mcap_m = _safe_float(profile.get("marketCapitalization"))
        if mcap_m > 0:
            info["marketCap"] = int(mcap_m * 1_000_000)
        # shareOutstanding also in millions
        shares_m = _safe_float(profile.get("shareOutstanding"))
        if shares_m > 0:
            info["sharesOutstanding"] = int(shares_m * 1_000_000)

    # 3. Basic financials — ratios and margins (single call, all metrics)
    metric = _fh_get("/stock/metric", {"symbol": symbol, "metric": "all"})
    if metric and isinstance(metric.get("metric"), dict):
        m = metric["metric"]
        # Map Finnhub field names → yfinance field names
        # Finnhub returns ratios as percentages (15 = 15%); yfinance uses decimals (0.15)
        # We convert to decimal for consistency with yfinance shape
        def _pct_to_dec(x):
            v = _safe_float(x)
            return v / 100.0 if v else None

        info["trailingPE"] = _safe_float(m.get("peNormalizedAnnual")) or _safe_float(m.get("peExclExtraAnnual")) or None
        info["forwardPE"] = _safe_float(m.get("peInclExtraTTM")) or None
        info["priceToBook"] = _safe_float(m.get("pbAnnual")) or None
        info["priceToSalesTrailing12Months"] = _safe_float(m.get("psTTM")) or None
        info["profitMargins"] = _pct_to_dec(m.get("netProfitMarginTTM"))
        info["operatingMargins"] = _pct_to_dec(m.get("operatingMarginTTM"))
        info["grossMargins"] = _pct_to_dec(m.get("grossMarginTTM"))
        info["returnOnAssets"] = _pct_to_dec(m.get("roaTTM"))
        info["returnOnEquity"] = _pct_to_dec(m.get("roeTTM"))
        info["revenueGrowth"] = _pct_to_dec(m.get("revenueGrowthTTMYoy"))
        info["earningsGrowth"] = _pct_to_dec(m.get("epsGrowthTTMYoy"))
        info["bookValue"] = _safe_float(m.get("bookValuePerShareAnnual")) or None
        info["totalCash"] = _safe_float(m.get("cashPerSharePerShareAnnual")) or None
        info["totalDebt"] = _safe_float(m.get("totalDebt/totalEquityAnnual")) or None
        info["fiftyDayAverage"] = _safe_float(m.get("50DayAverage")) or None
        info["twoHundredDayAverage"] = _safe_float(m.get("200DayAverage")) or None
        info["fiftyTwoWeekHigh"] = _safe_float(m.get("52WeekHigh")) or None
        info["fiftyTwoWeekLow"] = _safe_float(m.get("52WeekLow")) or None
        info["averageVolume"] = _safe_int(m.get("10DayAverageTradingVolume"))
        if info["averageVolume"]:
            info["averageVolume"] = info["averageVolume"] * 1000  # finnhub returns in thousands
        info["beta"] = _safe_float(m.get("beta")) or None
        info["dividendYield"] = _pct_to_dec(m.get("dividendYieldIndicatedAnnual"))

    # Mark this info dict as Finnhub-sourced for downstream awareness
    info["_finnhub_source"] = True
    info["_partial_fields"] = [
        "heldPercentInsiders",
        "heldPercentInstitutions",
        "shortPercentOfFloat",
        "targetMeanPrice",
        "recommendationMean",
    ]
    return info


def get_price_history(symbol: str, region: str = "US", period_days: int = 730, **kwargs) -> Optional[dict]:
    """Return historical OHLCV. Free tier supports up to 1 year of daily data per call."""
    if region != "US":
        return None
    if not _is_enabled():
        return None

    # Free tier max ~365 days of daily data per call
    days = min(period_days, 365)
    end = int(time.time())
    start = end - (days * 86400)

    data = _fh_get("/stock/candle", {
        "symbol": symbol,
        "resolution": "D",
        "from": start,
        "to": end,
    })
    if not data or data.get("s") != "ok":
        return None

    closes = data.get("c") or []
    highs = data.get("h") or []
    lows = data.get("l") or []
    opens = data.get("o") or []
    volumes = data.get("v") or []
    timestamps = data.get("t") or []

    if not closes or len(closes) != len(timestamps):
        return None

    return {
        "closes": closes,
        "highs": highs,
        "lows": lows,
        "opens": opens,
        "volumes": volumes,
        "timestamps": timestamps,
        "_source": "finnhub",
    }


def get_earnings_history(symbol: str, region: str = "US", **kwargs) -> Optional[dict]:
    """Return last 4 quarters of earnings surprises.
    r63.3: convert string dates → datetime to match yfinance schema.
    Callers (earnings_intel.py) call .tzinfo on these — must be datetime.
    """
    from datetime import datetime as _dt
    if region != "US":
        return None
    if not _is_enabled():
        return None
    data = _fh_get("/stock/earnings", {"symbol": symbol, "limit": 8})
    if not data or not isinstance(data, list):
        return None
    rows = []
    for d in data:
        # r63.3: parse "2024-10-23" → datetime to match yfinance shape
        date_str = d.get("period")
        date_obj = None
        if date_str:
            try:
                date_obj = _dt.strptime(date_str, "%Y-%m-%d")
            except (ValueError, TypeError):
                # try alternate formats just in case
                try:
                    date_obj = _dt.strptime(date_str[:10], "%Y-%m-%d")
                except (ValueError, TypeError):
                    date_obj = None
        # Skip rows with unparseable dates rather than passing strings downstream
        if date_obj is None:
            continue
        # "beat" is a derived bool yfinance provides — Finnhub gives surprisePercent
        surprise_pct = _safe_float(d.get("surprisePercent"))
        beat = surprise_pct > 0 if surprise_pct is not None else None
        rows.append({
            "date":          date_obj,
            "eps_estimate":  _safe_float(d.get("estimate")),
            "eps_actual":    _safe_float(d.get("actual")),
            "surprise":      _safe_float(d.get("surprise")),
            "surprise_pct":  surprise_pct,
            "beat":          beat,
        })
    if not rows:
        return None
    return {"data": rows, "_source": "finnhub"}


def get_earnings_calendar(symbol: str = None, from_date: str = None, to_date: str = None,
                          region: str = "US", **kwargs):
    """r63.8: Earnings calendar (forward + recent dates).
    
    Args:
        symbol: Optional ticker filter. None = all upcoming earnings.
        from_date: ISO date "YYYY-MM-DD" (default: today)
        to_date:   ISO date "YYYY-MM-DD" (default: today + 90 days)
        region: "US" only on free tier; India returns None.
    
    Returns:
        {"data": [{"symbol", "date", "epsEstimate", "epsActual",
                   "revenueEstimate", "revenueActual", "hour"}], "_source": "finnhub"}
        or None on failure / unsupported region.
    
    Free tier limitations:
        - US tickers only (free tier doesn't cover NSE/BSE earnings)
        - Forward coverage: ~30-90 days, ticker-dependent
        - "hour" indicates BMO/AMC/DMH (Before Market Open / After Market Close / During Market Hours)
    """
    from datetime import datetime as _dt2, timedelta as _td2
    if region != "US":
        return None
    if not _is_enabled():
        return None
    
    if not from_date:
        from_date = _dt2.utcnow().strftime("%Y-%m-%d")
    if not to_date:
        to_date = (_dt2.utcnow() + _td2(days=90)).strftime("%Y-%m-%d")
    
    params = {"from": from_date, "to": to_date}
    if symbol:
        params["symbol"] = symbol.upper()
    
    data = _fh_get("/calendar/earnings", params)
    if not data or not isinstance(data, dict):
        return None
    
    rows = data.get("earningsCalendar") or []
    if not isinstance(rows, list):
        return None
    
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        date_str = r.get("date")
        if not date_str:
            continue
        out.append({
            "symbol":           (r.get("symbol") or "").upper(),
            "date":             date_str,            # "YYYY-MM-DD" string
            "epsEstimate":      _safe_float(r.get("epsEstimate")),
            "epsActual":        _safe_float(r.get("epsActual")),
            "revenueEstimate":  _safe_float(r.get("revenueEstimate")),
            "revenueActual":    _safe_float(r.get("revenueActual")),
            "hour":             (r.get("hour") or "").lower(),   # bmo / amc / dmh
            "year":             _safe_int(r.get("year")),
            "quarter":          _safe_int(r.get("quarter")),
        })
    
    return {"data": out, "_source": "finnhub", "from_date": from_date, "to_date": to_date}
