# earnings_router.py
# ═══════════════════════════════════════════════════════════════════════════
# Earnings Calendar — drop-in FastAPI router module.
#
# DEPLOYMENT:
#   1. Save this file to your repo root, NEXT TO api.py.
#   2. In api.py, search (Ctrl-F) for `earnings-this-week`. If you find an
#      existing handler with that path, DELETE IT (the entire @app.get function).
#   3. Add 2 lines to api.py:
#        from earnings_router import router as earnings_router    # at top
#        app.include_router(earnings_router)                       # after `app = FastAPI(...)`
# ═══════════════════════════════════════════════════════════════════════════

import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import yfinance as yf
from fastapi import APIRouter

router = APIRouter()
logger = logging.getLogger(__name__)

_EARNINGS_TRACKED_US = [
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "NVDA", "TSLA",
    "AVGO", "ORCL", "ADBE", "CRM", "NFLX", "AMD", "INTC", "CSCO",
    "QCOM", "TXN", "IBM", "MU", "AMAT", "LRCX", "KLAC", "ADI",
    "NOW", "PANW", "SNPS", "INTU", "FI", "PYPL", "UBER", "SHOP",
    "PLTR", "SNOW", "DDOG", "CRWD", "ZS", "NET", "MDB", "TEAM",
    "JPM", "BAC", "WFC", "C", "GS", "MS", "BLK", "SCHW", "AXP",
    "V", "MA", "PGR", "MMC", "CB", "AIG", "MET", "PRU", "TRV",
    "UNH", "JNJ", "LLY", "PFE", "ABBV", "MRK", "TMO", "ABT", "DHR",
    "BMY", "AMGN", "GILD", "ISRG", "REGN", "VRTX", "ELV", "CVS", "CI",
    "WMT", "HD", "COST", "PG", "KO", "PEP", "MCD", "NKE", "SBUX",
    "DIS", "TGT", "LOW", "TJX", "BKNG", "MAR", "ABNB", "CMG", "DASH",
    "BA", "CAT", "GE", "HON", "RTX", "LMT", "DE", "UPS", "FDX",
    "XOM", "CVX", "COP", "SLB", "EOG", "PSX", "MPC",
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

_earnings_cache: dict = {}


def _earnings_week_bounds(today=None):
    if today is None:
        today = datetime.now(timezone.utc)
    this_mon = today - timedelta(days=today.weekday())
    this_sun = this_mon + timedelta(days=6)
    next_mon = this_mon + timedelta(days=7)
    next_sun = next_mon + timedelta(days=6)
    fmt = lambda d: d.strftime("%Y-%m-%d")
    return fmt(this_mon), fmt(this_sun), fmt(next_mon), fmt(next_sun)


def _fetch_one_earnings(ticker, region):
    try:
        yt = yf.Ticker(ticker)
        ed = yt.earnings_dates
        if ed is None or ed.empty:
            return None
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=7)
        window_end = now + timedelta(days=14)
        best = None
        for idx, row in ed.iterrows():
            try:
                dt = idx.to_pydatetime()
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if not (window_start <= dt <= window_end):
                    continue
                eps_estimate = row.get("EPS Estimate")
                eps_actual = row.get("Reported EPS")
                surprise = row.get("Surprise(%)")
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
        outcome = None
        if is_past and eps_actual is not None and eps_estimate is not None:
            outcome = "beat" if eps_actual > eps_estimate else ("miss" if eps_actual < eps_estimate else "reported")
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
            "in_universe": True,
            "is_past": is_past,
        }
    except Exception as e:
        logger.debug(f"[EARNINGS] {ticker} failed: {e}")
        return None


@router.get("/api/earnings-this-week")
def earnings_this_week(region: str = "US", email: str = ""):
    region = region.upper() if region else "US"
    cache_key = f"earnings:{region}"
    if cache_key in _earnings_cache:
        c = _earnings_cache[cache_key]
        if time.time() - c["t"] < 4 * 3600:
            return {**c["data"], "_cached": True, "_cache_age_sec": int(time.time() - c["t"])}
    universe = _EARNINGS_TRACKED_US if region == "US" else _EARNINGS_TRACKED_IN
    t0 = time.time()
    events = []
    with ThreadPoolExecutor(max_workers=12) as ex:
        futures = {ex.submit(_fetch_one_earnings, t, region): t for t in universe}
        for f in as_completed(futures):
            try:
                ev = f.result(timeout=30)
                if ev:
                    events.append(ev)
            except Exception:
                pass
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
            this_week_up.append(ev)
    declared.sort(key=lambda e: e["date"], reverse=True)
    this_week_up.sort(key=lambda e: e["date"])
    next_week_up.sort(key=lambda e: e["date"])
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


@router.get("/api/earnings-calendar")
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
        return {"success": True, "symbol": symbol, "company_name": info.get("longName") or symbol, "events": rows[:20]}
    except Exception as e:
        return {"success": False, "error": str(e), "symbol": symbol}
