# ═══════════════════════════════════════════════════════════════════════════
# SMART MONEY SCANNER — WORKING DROP-IN ENDPOINT
# Paste this entire file into api.py (anywhere after `app = FastAPI(...)`).
# No other dependencies on your existing code — fully self-contained.
# Uses yfinance only (no SEC EDGAR / paid APIs).
#
# What works immediately when deployed:
#   ✅ volume_quarterly_history  — derived from yfinance OHLCV bars (VOL 4Q cells)
#   ✅ insider_quarterly_history — derived from yfinance insider_transactions (INSIDER 4Q cells)
#   ⚠ ownership_history          — yfinance only gives current snapshot, returns []
#   ⚠ top_holders_delta          — needs prior-quarter 13F to compute Δ, returns []
#
# So 2 of the 4 SMI signals (VOL + INSIDER) light up immediately after this deploys.
# OWN 4Q + TOP HOLDERS need SEC EDGAR (US) / BSE-NSE shareholding pattern (India)
# integration — those show as "no quarterly data yet" placeholders until wired.
# ═══════════════════════════════════════════════════════════════════════════

import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from datetime import datetime, timedelta

import yfinance as yf

logger = logging.getLogger(__name__)

# ─── Universes (refresh quarterly — NSE rebalances Jan/Apr/Jul/Oct) ───
_US_UNIVERSES = {
    "large": [  # S&P 100 — top US blue chips. Refresh from Wikipedia quarterly.
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
    "mid": [  # S&P 400 sample — populate from spglobal.com (free CSV)
        "AAON", "ACM", "AGCO", "AIT", "AIZ", "ALK", "ALSN", "AYI", "WCC", "WBS",
        # ... add full S&P 400 list (400 tickers)
    ],
    "small": [  # S&P 600 sample
        # ... add full S&P 600 list
    ],
    "micro": [  # Russell Micro-Cap sample
        # ... add liquidity-filtered Russell Micro list
    ],
}

_INDIA_UNIVERSES = {
    "large": [  # NIFTY 50
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "BHARTIARTL.NS", "ICICIBANK.NS",
        "INFY.NS", "SBIN.NS", "LT.NS", "ITC.NS", "HINDUNILVR.NS",
        "BAJFINANCE.NS", "MARUTI.NS", "M&M.NS", "AXISBANK.NS", "KOTAKBANK.NS",
        "HCLTECH.NS", "SUNPHARMA.NS", "TITAN.NS", "ASIANPAINT.NS", "ULTRACEMCO.NS",
        "TATAMOTORS.NS", "NESTLEIND.NS", "WIPRO.NS", "POWERGRID.NS", "ADANIENT.NS",
        "ONGC.NS", "BAJAJFINSV.NS", "JSWSTEEL.NS", "NTPC.NS", "TATASTEEL.NS",
        "INDUSINDBK.NS", "TECHM.NS", "HDFCLIFE.NS", "HINDALCO.NS", "ADANIPORTS.NS",
        "GRASIM.NS", "COALINDIA.NS", "DRREDDY.NS", "CIPLA.NS", "SBILIFE.NS",
        "BAJAJ-AUTO.NS", "BRITANNIA.NS", "EICHERMOT.NS", "TATACONSUM.NS", "DIVISLAB.NS",
        "HEROMOTOCO.NS", "APOLLOHOSP.NS", "BPCL.NS", "SHRIRAMFIN.NS", "TRENT.NS",
    ],
    "mid": [],  # populate from niftyindices.com → MIDCAP 100
    "small": [],  # populate from niftyindices.com → SMALLCAP 100
    "micro": [],  # populate from niftyindices.com → MICROCAP 250
}

# ─── In-memory cache (4-hour TTL) ───
_smi_cache: dict = {}
_smi_per_ticker_cache: dict = {}


def _bucket_volume_by_quarter(df) -> list:
    """Bucket daily volume into calendar quarters, return last 5 quarters."""
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


def _bucket_insider_by_quarter(yt) -> list:
    """Aggregate yfinance insider_transactions into 4-quarter history."""
    try:
        ins = yt.insider_transactions
    except Exception:
        return []
    if ins is None or ins.empty:
        return []

    # yfinance columns: 'Shares', 'Value', 'URL', 'Text', 'Insider', 'Position',
    #                   'Transaction', 'Start Date', 'Ownership'
    # We want: net flow $ + count of buys vs sells per quarter
    by_q = defaultdict(lambda: {"n_buys": 0, "n_sells": 0, "buy_value_usd": 0, "sell_value_usd": 0})
    cutoff = datetime.now() - timedelta(days=370)  # last 4 quarters
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


def _derive_insider_trend(insider_q: list) -> str:
    """Compute ACCELERATING / STEADY / DECELERATING / NONE from quarterly history."""
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


def _compute_smi_signals(ticker: str, region: str) -> dict | None:
    """Per-ticker SMI signal aggregator. Returns the row payload for the scanner."""
    # Per-ticker cache (24-hour TTL) — saves yfinance hits on repeat scans
    cache_key = f"smi-row:{ticker}"
    if cache_key in _smi_per_ticker_cache:
        cached = _smi_per_ticker_cache[cache_key]
        if time.time() - cached["t"] < 24 * 3600:
            return cached["data"]

    try:
        yt = yf.Ticker(ticker)
        info = yt.info or {}
        if not info or not (info.get("regularMarketPrice") or info.get("currentPrice")):
            return None  # ticker delisted / no data

        # Volume history → drives VOL 4Q
        hist_df = yt.history(period="2y", interval="1d", auto_adjust=False)
        volume_quarterly_history = _bucket_volume_by_quarter(hist_df)

        # Insider history → drives INSIDER 4Q
        insider_quarterly_history = _bucket_insider_by_quarter(yt)
        insider_trend = _derive_insider_trend(insider_quarterly_history)

        # Ownership history — yfinance only has current snapshot.
        # To get quarterly history, integrate SEC EDGAR (US) or BSE-NSE
        # shareholding pattern (India). For now: empty array → frontend
        # shows "no quarterly data yet" placeholder for the OWN 4Q cells.
        ownership_history: list = []
        top_holders_delta: list = []
        top_holders_action = None

        # Verdict requires ownership_history to derive — stays INSUFFICIENT until wired
        smi_verdict = "INSUFFICIENT"
        smi_score = 50  # neutral baseline

        # Bump score from insider trend (since we have that)
        if insider_trend == "ACCELERATING":
            smi_score += 15
        elif insider_trend == "DECELERATING":
            smi_score -= 15

        # Live price
        px = info.get("currentPrice") or info.get("regularMarketPrice") or 0
        prev_close = info.get("previousClose") or px
        change_pct = ((px - prev_close) / prev_close * 100) if prev_close else 0

        row = {
            "ticker": ticker,
            "issuer_name": info.get("longName") or info.get("shortName") or ticker,
            "price": round(px, 2),
            "change_pct": round(change_pct, 2),
            "smi_verdict": smi_verdict,
            "smi_score": round(smi_score, 1),
            "ownership_history": ownership_history,
            "ownership_delta_8q": None,
            "volume_quarterly_history": volume_quarterly_history,
            "insider_quarterly_history": insider_quarterly_history,
            "top_holders_delta": top_holders_delta,
            "top_holders_action": top_holders_action,
            "insider_trend": insider_trend,
        }
        _smi_per_ticker_cache[cache_key] = {"t": time.time(), "data": row}
        return row
    except Exception as e:
        logger.warning(f"[SMI] {ticker} failed: {e}")
        return None


# ─── THE ENDPOINT ───
@app.get("/api/smart-money-scanner")
def smart_money_scanner(
    region: str = "US",
    mcap: str = "large",
    email: str = "",
    limit: int = 50,
):
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
            "error": f"{mcap.title()}-cap universe for {region} not populated. Add tickers to _US_UNIVERSES / _INDIA_UNIVERSES in api.py.",
        }

    # Full-payload cache (4-hour TTL)
    cache_key = f"smi:{region}:{mcap}"
    if cache_key in _smi_cache:
        cached = _smi_cache[cache_key]
        if time.time() - cached["t"] < 4 * 3600:
            return {
                **cached["data"],
                "_cached": True,
                "_cache_age_sec": int(time.time() - cached["t"]),
            }

    t0 = time.time()
    results = []

    # Parallel yfinance fetches (I/O bound — threads work fine)
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


# ═══════════════════════════════════════════════════════════════════════════
# NEXT STEPS to light up the remaining 2 columns (OWN 4Q + TOP HOLDERS):
#
# For US tickers — SEC EDGAR 13F integration:
#   pip install sec-edgar-downloader  (or roll your own using EDGAR full-text search)
#   For each ticker:
#     1. Get the CIK from yfinance (info.get('cik') or look it up)
#     2. Pull last 8 13F-HR filings via EDGAR API
#     3. For each filing, sum total holdings as % of shares outstanding
#     4. Compute Q/Q delta for top-10 holders
#   Cache by (ticker, quarter) — historical filings never change
#
# For India tickers — BSE-NSE shareholding pattern:
#   Quarterly XBRL files at:
#     NSE: https://www.nseindia.com/companies-listing/corporate-filings-shareholding-pattern
#     BSE: https://www.bseindia.com/corporates/shp.html
#   Parse FII %, DII %, top public holders %
#   Note: NSE rate-limits direct API calls from datacenters (Render outbound IP
#   72.180.65.28 is banned by NSE). Route through nseindia.com archives instead.
#
# Both data sources are FREE — just need the integration code.
# ═══════════════════════════════════════════════════════════════════════════
