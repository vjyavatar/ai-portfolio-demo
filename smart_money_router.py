# smart_money_router.py
# ═══════════════════════════════════════════════════════════════════════════
# Smart Money Scanner — drop-in FastAPI router module.
#
# DEPLOYMENT (2 STEPS):
#   1. Save this file to your repo root, NEXT TO api.py.
#   2. Add these 2 lines to the TOP of api.py (after `from fastapi import FastAPI`):
#
#        from smart_money_router import router as smart_money_router
#
#   And after `app = FastAPI(...)`:
#
#        app.include_router(smart_money_router)
#
# That's it. Commit, push, redeploy.
# ═══════════════════════════════════════════════════════════════════════════

import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from datetime import datetime, timedelta

import yfinance as yf
from fastapi import APIRouter

router = APIRouter()
logger = logging.getLogger(__name__)

# ─── Universes ─────────────────────────────────────────────────────────────
_US_UNIVERSES = {
    "large": [
        "AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "AMZN", "META", "BRK-B", "LLY", "TSLA",
        "AVGO", "JPM", "WMT", "XOM", "V", "UNH", "MA", "PG", "JNJ", "HD",
        "COST", "ORCL", "BAC", "ABBV", "NFLX", "KO", "CRM", "CVX", "MRK", "TMO",
        "AMD", "PEP", "ADBE", "LIN", "CSCO", "ACN", "MCD", "WFC", "ABT", "DHR",
        "GE", "TXN", "VZ", "DIS", "NOW", "PM", "INTU", "AMGN", "IBM", "QCOM",
        "ISRG", "CAT", "BX", "AMAT", "GS", "UBER", "BKNG", "AXP", "T", "RTX",
        "NEE", "BLK", "PFE", "SCHW", "SPGI", "TJX", "C", "LOW", "PGR", "ELV",
        "DE", "BSX", "VRTX", "HON", "PLD", "REGN", "MS", "BMY", "ETN", "ADP",
        "MDT", "MU", "LRCX", "MDLZ", "ADI", "GILD", "FI", "TMUS", "PANW", "CB",
        "MMC", "KLAC", "CI", "SO", "ICE", "BA", "DUK", "SNPS", "MO", "NKE",
    ],
    "mid": [],
    "small": [],
    "micro": [],
}

_INDIA_UNIVERSES = {
    "large": [
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
    ],
    "mid": [],
    "small": [],
    "micro": [],
}

_smi_cache: dict = {}
_smi_per_ticker_cache: dict = {}


def _bucket_volume_by_quarter(df):
    if df is None or df.empty or "Volume" not in df.columns:
        return []
    by_q = defaultdict(list)
    for idx, vol in zip(df.index, df["Volume"].values):
        q = (idx.month - 1) // 3 + 1
        by_q[f"Q{q} {idx.year}"].append(int(vol) if vol > 0 else 0)
    quarters = sorted(by_q.keys(), key=lambda q: (int(q.split()[-1]), int(q[1:2])))
    return [
        {"quarter": q, "avg_daily_volume": int(sum(by_q[q]) / max(1, len(by_q[q])))}
        for q in quarters[-5:]
    ]


def _bucket_insider_by_quarter(yt):
    try:
        ins = yt.insider_transactions
    except Exception:
        return []
    if ins is None or ins.empty:
        return []
    by_q = defaultdict(lambda: {"n_buys": 0, "n_sells": 0, "buy_value_usd": 0, "sell_value_usd": 0})
    cutoff = datetime.now() - timedelta(days=370)
    for _, row in ins.iterrows():
        try:
            dt = row.get("Start Date") or row.get("startDate")
            if not dt:
                continue
            if hasattr(dt, "to_pydatetime"):
                dt = dt.to_pydatetime()
            if dt < cutoff:
                continue
            q_key = f"Q{(dt.month - 1)//3 + 1} {dt.year}"
            txn = str(row.get("Transaction", "")).lower()
            val = float(row.get("Value") or 0)
            if "purchase" in txn or "buy" in txn or "acquir" in txn:
                by_q[q_key]["n_buys"] += 1
                by_q[q_key]["buy_value_usd"] += val
            elif "sale" in txn or "sell" in txn or "dispos" in txn:
                by_q[q_key]["n_sells"] += 1
                by_q[q_key]["sell_value_usd"] += val
        except Exception:
            continue
    quarters = sorted(by_q.keys(), key=lambda q: (int(q.split()[-1]), int(q[1:2])))
    return [
        {
            "quarter": q,
            "n_buys": by_q[q]["n_buys"],
            "n_sells": by_q[q]["n_sells"],
            "buy_value_usd": by_q[q]["buy_value_usd"],
            "sell_value_usd": by_q[q]["sell_value_usd"],
            "net_flow_usd": by_q[q]["buy_value_usd"] - by_q[q]["sell_value_usd"],
        }
        for q in quarters[-4:]
    ]


def _derive_insider_trend(insider_q):
    if not insider_q or len(insider_q) < 4:
        return "NONE"
    first_half = sum(q.get("buy_value_usd", 0) for q in insider_q[-4:-2])
    second_half = sum(q.get("buy_value_usd", 0) for q in insider_q[-2:])
    if first_half == 0 and second_half == 0:
        return "NONE"
    if first_half == 0 or second_half > first_half * 1.5:
        return "ACCELERATING"
    if second_half < first_half * 0.5:
        return "DECELERATING"
    return "STEADY"


def _compute_smi_signals(ticker, region):
    cache_key = f"smi-row:{ticker}"
    if cache_key in _smi_per_ticker_cache:
        c = _smi_per_ticker_cache[cache_key]
        if time.time() - c["t"] < 24 * 3600:
            return c["data"]
    try:
        yt = yf.Ticker(ticker)
        info = yt.info or {}
        if not info or not (info.get("regularMarketPrice") or info.get("currentPrice")):
            return None
        hist_df = yt.history(period="2y", interval="1d", auto_adjust=False)
        volume_quarterly_history = _bucket_volume_by_quarter(hist_df)
        insider_quarterly_history = _bucket_insider_by_quarter(yt)
        insider_trend = _derive_insider_trend(insider_quarterly_history)
        smi_score = 50
        if insider_trend == "ACCELERATING":
            smi_score += 15
        elif insider_trend == "DECELERATING":
            smi_score -= 15
        px = info.get("currentPrice") or info.get("regularMarketPrice") or 0
        prev_close = info.get("previousClose") or px
        change_pct = ((px - prev_close) / prev_close * 100) if prev_close else 0
        row = {
            "ticker": ticker,
            "issuer_name": info.get("longName") or info.get("shortName") or ticker,
            "price": round(px, 2),
            "change_pct": round(change_pct, 2),
            "smi_verdict": "INSUFFICIENT",
            "smi_score": round(smi_score, 1),
            "ownership_history": [],
            "ownership_delta_8q": None,
            "volume_quarterly_history": volume_quarterly_history,
            "insider_quarterly_history": insider_quarterly_history,
            "top_holders_delta": [],
            "top_holders_action": None,
            "insider_trend": insider_trend,
        }
        _smi_per_ticker_cache[cache_key] = {"t": time.time(), "data": row}
        return row
    except Exception as e:
        logger.warning(f"[SMI] {ticker} failed: {e}")
        return None


@router.get("/api/smart-money-scanner")
def smart_money_scanner(region: str = "US", mcap: str = "large", email: str = "", limit: int = 50):
    if mcap not in ("large", "mid", "small", "micro"):
        mcap = "large"
    universe_map = _US_UNIVERSES if region == "US" else _INDIA_UNIVERSES
    universe = universe_map.get(mcap, [])
    if not universe:
        return {
            "success": False,
            "universe_size": 0,
            "results": [],
            "scan_time_sec": 0,
            "error": f"{mcap.title()}-cap universe for {region} not populated.",
        }
    cache_key = f"smi:{region}:{mcap}"
    if cache_key in _smi_cache:
        c = _smi_cache[cache_key]
        if time.time() - c["t"] < 4 * 3600:
            return {**c["data"], "_cached": True, "_cache_age_sec": int(time.time() - c["t"])}
    t0 = time.time()
    results = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(_compute_smi_signals, t, region): t for t in universe[:limit]}
        for f in as_completed(futures):
            try:
                r = f.result(timeout=45)
                if r:
                    results.append(r)
            except Exception as e:
                logger.warning(f"[SMI] {futures[f]} timeout/error: {e}")
    payload = {
        "success": True,
        "universe_size": len(universe),
        "results": results,
        "scan_time_sec": round(time.time() - t0, 1),
        "region": region,
        "mcap": mcap,
    }
    _smi_cache[cache_key] = {"t": time.time(), "data": payload}
    return payload
