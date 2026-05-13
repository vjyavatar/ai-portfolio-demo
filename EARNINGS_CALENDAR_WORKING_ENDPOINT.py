# ═══════════════════════════════════════════════════════════════════════════
# EARNINGS CALENDAR — WORKING DROP-IN ENDPOINT
#
# User report: "today cisco didnt show up.. tomorrow nvda is not showing up..
# all important companies are not coming"
#
# Root cause: existing /api/earnings-this-week is missing major names because
# its universe is wrong, its data source is unreliable, or it filters out
# legitimate upcoming earnings. This drop-in replacement uses yfinance with a
# CURATED tracked universe of major US + India companies and returns the exact
# JSON shape the frontend expects.
#
# Drop into api.py (anywhere after `app = FastAPI(...)`). If you already have
# an /api/earnings-this-week handler, DELETE IT FIRST — FastAPI rejects
# duplicate routes at startup.
# ═══════════════════════════════════════════════════════════════════════════

import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import yfinance as yf

logger = logging.getLogger(__name__)


# ─── Tracked universe — major companies users care about ─────────────────
# Refresh quarterly. Cover S&P 100 + key tech + India NIFTY 50.
_EARNINGS_TRACKED_US = [
    # FAANG+ / Mega cap tech (HIGH PRIORITY — users notice if these are missing)
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "NVDA", "TSLA",
    "AVGO", "ORCL", "ADBE", "CRM", "NFLX", "AMD", "INTC", "CSCO",
    "QCOM", "TXN", "IBM", "MU", "AMAT", "LRCX", "KLAC", "ADI",
    "NOW", "PANW", "SNPS", "INTU", "FI", "PYPL", "UBER", "SHOP",
    "PLTR", "SNOW", "DDOG", "CRWD", "ZS", "NET", "MDB", "TEAM",
    # Banks & financials
    "JPM", "BAC", "WFC", "C", "GS", "MS", "BLK", "SCHW", "AXP",
    "V", "MA", "PGR", "MMC", "CB", "AIG", "MET", "PRU", "TRV",
    # Healthcare & pharma
    "UNH", "JNJ", "LLY", "PFE", "ABBV", "MRK", "TMO", "ABT", "DHR",
    "BMY", "AMGN", "GILD", "ISRG", "REGN", "VRTX", "ELV", "CVS", "CI",
    # Consumer
    "WMT", "HD", "COST", "PG", "KO", "PEP", "MCD", "NKE", "SBUX",
    "DIS", "TGT", "LOW", "TJX", "BKNG", "MAR", "ABNB", "CMG", "DASH",
    # Industrial & energy
    "BA", "CAT", "GE", "HON", "RTX", "LMT", "DE", "UPS", "FDX",
    "XOM", "CVX", "COP", "SLB", "EOG", "PSX", "MPC",
    # Communication & media
    "T", "VZ", "TMUS", "CMCSA", "WBD", "PARA", "SPOT",
]

_EARNINGS_TRACKED_IN = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "BHARTIARTL.NS", "ICICIBANK.NS",
    "INFY.NS", "SBIN.NS", "LT.NS", "ITC.NS", "HINDUNILVR.NS",
    "BAJFINANCE.NS", "MARUTI.NS", "AXISBANK.NS", "KOTAKBANK.NS",
    "HCLTECH.NS", "SUNPHARMA.NS", "TITAN.NS", "ASIANPAINT.NS", "ULTRACEMCO.NS",
    "TATAMOTORS.NS", "NESTLEIND.NS", "WIPRO.NS", "POWERGRID.NS", "ADANIENT.NS",
    "ONGC.NS", "BAJAJFINSV.NS", "JSWSTEEL.NS", "NTPC.NS", "TATASTEEL.NS",
    "INDUSINDBK.NS", "TECHM.NS", "HDFCLIFE.NS", "HINDALCO.NS", "ADANIPORTS.NS",
    "GRASIM.NS", "COALINDIA.NS", "DRREDDY.NS", "CIPLA.NS", "SBILIFE.NS",
    "BAJAJ-AUTO.NS", "BRITANNIA.NS", "EICHERMOT.NS", "TATACONSUM.NS", "DIVISLAB.NS",
    "HEROMOTOCO.NS", "APOLLOHOSP.NS", "BPCL.NS", "SHRIRAMFIN.NS", "TRENT.NS",
]

# 4-hour cache (key: region)
_earnings_cache: dict = {}


def _earnings_week_bounds(today: datetime | None = None):
    """Return (this_week_start, this_week_end, next_week_start, next_week_end) as date strings.
    A week runs Monday → Sunday. 'This week' = the week containing today.
    """
    if today is None:
        today = datetime.now(timezone.utc)
    # Monday of this week (weekday() returns 0=Mon ... 6=Sun)
    this_mon = today - timedelta(days=today.weekday())
    this_sun = this_mon + timedelta(days=6)
    next_mon = this_mon + timedelta(days=7)
    next_sun = next_mon + timedelta(days=6)
    fmt = lambda d: d.strftime("%Y-%m-%d")
    return fmt(this_mon), fmt(this_sun), fmt(next_mon), fmt(next_sun)


def _fetch_one_earnings(ticker: str, region: str) -> dict | None:
    """Return the most-relevant earnings event for `ticker` in the [-7, +14] day window.

    Strategy: pull yfinance.Ticker(t).earnings_dates, filter to recent window,
    prefer the soonest event. Returns None if no event in window.
    """
    try:
        yt = yf.Ticker(ticker)
        ed = yt.earnings_dates  # DataFrame indexed by date
        if ed is None or ed.empty:
            return None

        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=7)
        window_end = now + timedelta(days=14)

        # Filter to window
        best = None
        for idx, row in ed.iterrows():
            try:
                # yfinance gives tz-aware Timestamps; normalize
                dt = idx.to_pydatetime()
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if not (window_start <= dt <= window_end):
                    continue

                eps_estimate = row.get("EPS Estimate")
                eps_actual = row.get("Reported EPS")
                surprise = row.get("Surprise(%)")

                # Pick the most relevant: prefer event closest to today (forward or backward)
                priority = abs((dt - now).total_seconds())
                if best is None or priority < best["_priority"]:
                    best = {
                        "_priority": priority,
                        "_datetime": dt,
                        "eps_estimate": float(eps_estimate) if eps_estimate is not None and str(eps_estimate) != "nan" else None,
                        "eps_actual": float(eps_actual) if eps_actual is not None and str(eps_actual) != "nan" else None,
                        "surprise_pct": round(float(surprise), 2) if surprise is not None and str(surprise) != "nan" else None,
                    }
            except Exception:
                continue

        if not best:
            return None

        info = yt.info or {}
        px = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose") or 0
        prev_close = info.get("previousClose") or px
        change_pct = ((px - prev_close) / prev_close * 100) if prev_close else 0

        event_dt = best["_datetime"]
        is_past = event_dt < datetime.now(timezone.utc)
        eps_actual = best["eps_actual"]
        eps_estimate = best["eps_estimate"]
        surprise = best["surprise_pct"]

        # Outcome: only meaningful for past events with reported EPS
        outcome = None
        if is_past and eps_actual is not None and eps_estimate is not None:
            if eps_actual > eps_estimate:
                outcome = "beat"
            elif eps_actual < eps_estimate:
                outcome = "miss"
            else:
                outcome = "reported"
        elif is_past and eps_actual is not None:
            outcome = "reported"

        return {
            "symbol": ticker,
            "company_name": info.get("longName") or info.get("shortName") or ticker,
            "price": round(px, 2) if px else None,
            "change_pct": round(change_pct, 2) if px else None,
            "date": event_dt.strftime("%Y-%m-%d"),
            "datetime_utc": event_dt.isoformat(),
            "eps_estimate": eps_estimate,
            "eps_actual": eps_actual,
            "surprise_pct": surprise,
            "outcome": outcome,
            "in_universe": True,  # all in our tracked list
            "is_past": is_past,
        }
    except Exception as e:
        logger.debug(f"[EARNINGS] {ticker} failed: {e}")
        return None


@app.get("/api/earnings-this-week")
def earnings_this_week(region: str = "US", email: str = ""):
    region = region.upper() if region else "US"
    cache_key = f"earnings:{region}"

    # 4-hour TTL
    if cache_key in _earnings_cache:
        cached = _earnings_cache[cache_key]
        if time.time() - cached["t"] < 4 * 3600:
            return {**cached["data"], "_cached": True, "_cache_age_sec": int(time.time() - cached["t"])}

    universe = _EARNINGS_TRACKED_US if region == "US" else _EARNINGS_TRACKED_IN
    t0 = time.time()
    events: list = []

    # Parallel yfinance fetches
    with ThreadPoolExecutor(max_workers=12) as ex:
        futures = {ex.submit(_fetch_one_earnings, t, region): t for t in universe}
        for f in as_completed(futures):
            try:
                ev = f.result(timeout=30)
                if ev:
                    events.append(ev)
            except Exception as e:
                logger.debug(f"[EARNINGS] {futures[f]} timeout: {e}")

    # Bucketize
    this_mon, this_sun, next_mon, next_sun = _earnings_week_bounds()
    declared, this_week_up, next_week_up = [], [], []

    for ev in events:
        d = ev["date"]
        if ev["is_past"] and ev.get("eps_actual") is not None:
            declared.append(ev)
        elif this_mon <= d <= this_sun and not ev["is_past"]:
            this_week_up.append(ev)
        elif next_mon <= d <= next_sun:
            next_week_up.append(ev)
        elif d >= this_mon and not ev["is_past"]:
            # Catch any future events that fell outside both week ranges
            # but are still in our 14-day window
            this_week_up.append(ev)

    # Sort: declared by date desc, upcoming by date asc
    declared.sort(key=lambda e: e["date"], reverse=True)
    this_week_up.sort(key=lambda e: e["date"])
    next_week_up.sort(key=lambda e: e["date"])

    # Strip private fields
    for lst in (declared, this_week_up, next_week_up):
        for ev in lst:
            ev.pop("_priority", None)
            ev.pop("_datetime", None)
            ev.pop("is_past", None)

    payload = {
        "success": True,
        "declared": declared,
        "this_week_upcoming": this_week_up,
        "next_week_upcoming": next_week_up,
        "this_week_range": [this_mon, this_sun],
        "next_week_range": [next_mon, next_sun],
        "totals": {
            "declared": len(declared),
            "this_week_upcoming": len(this_week_up),
            "next_week_upcoming": len(next_week_up),
            "tracked_total": len(universe),
        },
        "scan_time_sec": round(time.time() - t0, 1),
        "region": region,
    }
    _earnings_cache[cache_key] = {"t": time.time(), "data": payload}
    return payload


# Also expose /api/earnings-calendar?symbol=X for single-ticker drill-downs
# (used by the row-click in the modal). Returns next 4 quarters of upcoming
# earnings + last 4 reported.
@app.get("/api/earnings-calendar")
def earnings_calendar(symbol: str, region: str = "US", email: str = ""):
    try:
        yt = yf.Ticker(symbol.upper())
        ed = yt.earnings_dates
        if ed is None or ed.empty:
            return {"success": False, "error": "No earnings history for " + symbol, "symbol": symbol}

        now = datetime.now(timezone.utc)
        rows = []
        for idx, row in ed.iterrows():
            try:
                dt = idx.to_pydatetime()
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                eps_est = row.get("EPS Estimate")
                eps_act = row.get("Reported EPS")
                surp = row.get("Surprise(%)")
                is_past = dt < now
                outcome = None
                if is_past and eps_act is not None and str(eps_act) != "nan":
                    if eps_est is not None and str(eps_est) != "nan":
                        outcome = "beat" if eps_act > eps_est else ("miss" if eps_act < eps_est else "reported")
                    else:
                        outcome = "reported"
                rows.append({
                    "date": dt.strftime("%Y-%m-%d"),
                    "datetime_utc": dt.isoformat(),
                    "eps_estimate": float(eps_est) if eps_est is not None and str(eps_est) != "nan" else None,
                    "eps_actual": float(eps_act) if eps_act is not None and str(eps_act) != "nan" else None,
                    "surprise_pct": round(float(surp), 2) if surp is not None and str(surp) != "nan" else None,
                    "outcome": outcome,
                    "is_past": is_past,
                })
            except Exception:
                continue
        rows.sort(key=lambda r: r["date"], reverse=True)
        info = yt.info or {}
        return {
            "success": True,
            "symbol": symbol,
            "company_name": info.get("longName") or symbol,
            "events": rows[:20],
        }
    except Exception as e:
        return {"success": False, "error": str(e), "symbol": symbol}


# ═══════════════════════════════════════════════════════════════════════════
# Notes / common pitfalls:
#
# 1. yfinance throttles aggressive requests. First scan takes ~30-60 seconds
#    for ~100 tickers. Cache hits afterward are instant. If you see rate-limit
#    errors, lower max_workers from 12 to 4.
#
# 2. NVDA's earnings are typically late February / late May / late August /
#    late November (the WEDNESDAY of the last week). CSCO's are typically the
#    Wednesday after AAPL (mid-Feb / mid-May / mid-Aug / mid-Nov). If you
#    expect a name on a specific date and it's not appearing, check on Yahoo
#    Finance directly: https://finance.yahoo.com/quote/NVDA/calendar/
#    yfinance reads from the same data — if Yahoo shows it, this endpoint will.
#
# 3. If you ALREADY have an /api/earnings-this-week handler in api.py, you
#    MUST DELETE IT FIRST. FastAPI throws "Multiple matching paths" at startup.
#    Use Ctrl-F in api.py for `earnings-this-week` and remove the old handler.
#
# 4. Render outbound IP (72.180.65.28) is banned by NSE for direct API calls.
#    yfinance routes through query1.finance.yahoo.com which is NOT NSE-direct,
#    so .NS tickers work fine from Render.
# ═══════════════════════════════════════════════════════════════════════════
