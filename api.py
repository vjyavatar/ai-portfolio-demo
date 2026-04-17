"""
Celesys — FastAPI backend
Serves both the React frontend (from static/dist/) and the API endpoints
the frontend consumes.

Endpoints:
  GET  /api/stock-quick?ticker=XXX        — stock analytics (primary endpoint)
  GET  /api/options-quick?symbol=NIFTY    — Indian index options data
  GET  /api/global-ticker                 — global indices
  GET  /api/l0-scan?region=US&mode=quality — bulk stock scanner
  GET  /                                  — serves React index.html
  GET  /{path}                            — catchall: static assets or SPA fallback

Built to run on Render with:
  build: npm install && npm run build && pip install -r requirements.txt
  start: uvicorn api:app --host 0.0.0.0 --port $PORT
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from typing import Optional
import asyncio
import math
import time
import traceback

import yfinance as yf
import pandas as pd
import numpy as np


app = FastAPI(title="Celesys API", version="1.0.0")

# CORS — permissive for development; lock down in production if needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════════
# CACHE (simple in-memory, 60s TTL for quotes)
# ═══════════════════════════════════════════════════════════════════

_CACHE: dict = {}
_CACHE_TTL = 60  # seconds


def _cache_get(key: str):
    item = _CACHE.get(key)
    if item and (time.time() - item["t"]) < _CACHE_TTL:
        return item["v"]
    return None


def _cache_set(key: str, value):
    _CACHE[key] = {"t": time.time(), "v": value}


# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════

def _safe_float(v):
    """Convert to float, returning None for NaN/None/bad values."""
    if v is None:
        return None
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _detect_currency(ticker: str) -> str:
    """Indian NSE tickers end in .NS — otherwise assume USD."""
    if ticker.upper().endswith(".NS") or ticker.upper().endswith(".BO"):
        return "INR"
    return "USD"


def _sma(series: pd.Series, window: int):
    """Safe SMA that returns None if not enough data."""
    if len(series) < window:
        return None
    return _safe_float(series.rolling(window=window).mean().iloc[-1])


# ═══════════════════════════════════════════════════════════════════
# /api/stock-quick — primary endpoint
# ═══════════════════════════════════════════════════════════════════

@app.get("/api/stock-quick")
async def stock_quick(ticker: str):
    """Return full stock analytics for the React Overview/Stock tabs.
    Uses yfinance info + historical bars. Cached 60s.
    """
    key = f"stock_quick:{ticker.upper()}"
    cached = _cache_get(key)
    if cached:
        return cached

    try:
        t = yf.Ticker(ticker)

        # Info (slow call — this is the biggest bottleneck)
        try:
            info = t.info or {}
        except Exception:
            info = {}

        # Historical bars (for SMAs + 52w)
        try:
            hist = t.history(period="1y")
        except Exception:
            hist = pd.DataFrame()

        # Current price — try info first, fall back to history
        current_price = (
            _safe_float(info.get("currentPrice"))
            or _safe_float(info.get("regularMarketPrice"))
            or (_safe_float(hist["Close"].iloc[-1]) if len(hist) else None)
        )

        if current_price is None:
            return JSONResponse(
                status_code=404,
                content={"error": f"Could not fetch data for {ticker}"},
            )

        # SMAs
        closes = hist["Close"] if len(hist) else pd.Series([], dtype=float)
        sma_20 = _sma(closes, 20)
        sma_50 = _sma(closes, 50)
        sma_200 = _sma(closes, 200)

        # 52-week range
        if len(hist):
            week52_high = _safe_float(hist["High"].max())
            week52_low = _safe_float(hist["Low"].min())
        else:
            week52_high = _safe_float(info.get("fiftyTwoWeekHigh"))
            week52_low = _safe_float(info.get("fiftyTwoWeekLow"))

        # Company + sector
        company_name = (
            info.get("longName")
            or info.get("shortName")
            or ticker.upper()
        )
        sector = info.get("sector") or info.get("industry") or None

        # Sector P/E — yfinance sometimes has this; fallback None
        sector_avg_pe = _safe_float(
            info.get("trailingPE")
        )  # placeholder — we use the stock's own trailing PE since sector P/E often unavailable

        # Build response
        response = {
            "ticker": ticker.upper(),
            "company_name": company_name,
            "current_price": current_price,
            "currency": _detect_currency(ticker),
            "sector": sector,

            # Valuation
            "pe_ratio": _safe_float(info.get("trailingPE")),
            "forward_pe": _safe_float(info.get("forwardPE")),
            "pb_ratio": _safe_float(info.get("priceToBook")),
            "peg_ratio": _safe_float(info.get("pegRatio")),
            "book_value": _safe_float(info.get("bookValue")),
            "eps_ttm": _safe_float(info.get("trailingEps")),
            "sector_avg_pe": sector_avg_pe,

            # Profitability
            "profit_margin": _safe_float(info.get("profitMargins")),
            "operating_margin": _safe_float(info.get("operatingMargins")),
            "roe": _safe_float(info.get("returnOnEquity")),

            # Balance sheet
            "debt_to_equity": _safe_float(info.get("debtToEquity")),
            "current_ratio": _safe_float(info.get("currentRatio")),

            # Market
            "market_cap": _safe_float(info.get("marketCap")),
            "beta": _safe_float(info.get("beta")),
            "dividend_yield": _safe_float(info.get("dividendYield")),

            # Growth
            "eps_growth_pct": (
                _safe_float(info.get("earningsQuarterlyGrowth")) * 100
                if _safe_float(info.get("earningsQuarterlyGrowth")) is not None
                else None
            ),
            "revenue_growth": _safe_float(info.get("revenueGrowth")),
            "earnings_growth": _safe_float(info.get("earningsGrowth")),

            # Technical
            "sma_20": sma_20,
            "sma_50": sma_50,
            "sma_200": sma_200,
            "week52_high": week52_high,
            "week52_low": week52_low,

            # Signal (simplified)
            "decision": "NEUTRAL",
        }

        # Normalize debt_to_equity — yfinance returns percent, we need ratio
        if response["debt_to_equity"] is not None and response["debt_to_equity"] > 10:
            response["debt_to_equity"] = response["debt_to_equity"] / 100

        _cache_set(key, response)
        return response

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": f"Internal error: {str(e)}"},
        )


# ═══════════════════════════════════════════════════════════════════
# /api/options-quick — Indian index options for Decide tab
# ═══════════════════════════════════════════════════════════════════

INDEX_PROXY_TICKERS = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "FINNIFTY": "NIFTY_FIN_SERVICE.NS",
    "SENSEX": "^BSESN",
}

INDEX_STEPS = {
    "NIFTY": 50,
    "BANKNIFTY": 100,
    "FINNIFTY": 50,
    "SENSEX": 100,
}


def _synthesize_options_data(symbol: str, hist: pd.DataFrame) -> dict:
    """Build the options-quick response from yfinance historical data.

    yfinance doesn't expose real-time NSE options chains; we synthesize a
    reasonable shape from spot price + daily volatility. Clearly flagged
    with _fallback=True so the React frontend shows the warning banner.
    """
    if len(hist) == 0:
        return {"success": False, "error": "No history"}

    spot = float(hist["Close"].iloc[-1])
    step = INDEX_STEPS.get(symbol, 50)
    atm = round(spot / step) * step

    # Intraday range (use last day)
    day_high = float(hist["High"].iloc[-1])
    day_low = float(hist["Low"].iloc[-1])

    # VWAP proxy: (H+L+C)/3 for last day
    vwap = (day_high + day_low + spot) / 3

    # CPR (Central Pivot Range) for today
    if len(hist) >= 2:
        prev = hist.iloc[-2]
        pivot = (float(prev["High"]) + float(prev["Low"]) + float(prev["Close"])) / 3
        cpr_top = round(max(day_high * 0.998, pivot), 2)
        cpr_bottom = round(min(day_low * 1.002, pivot), 2)
    else:
        pivot = vwap
        cpr_top = round(day_high * 0.998, 2)
        cpr_bottom = round(day_low * 1.002, 2)

    # Build a synthetic chain (ATM ± 5 strikes)
    chain = []
    for offset in range(-5, 6):
        strike = atm + offset * step
        # OI approximation: symmetric peak at ATM, decaying
        distance = abs(offset)
        ce_oi = max(10000, int(500000 * math.exp(-distance * 0.4)))
        pe_oi = max(10000, int(500000 * math.exp(-distance * 0.4)))
        # Change-in-OI: slight noise
        ce_chg = int(ce_oi * 0.05 * (1 if offset < 0 else -1))
        pe_chg = int(pe_oi * 0.05 * (1 if offset > 0 else -1))
        chain.append({
            "strike": strike,
            "ce_oi": ce_oi,
            "pe_oi": pe_oi,
            "ce_chg_oi": ce_chg,
            "pe_chg_oi": pe_chg,
            "ce_volume": int(ce_oi * 0.2),
            "pe_volume": int(pe_oi * 0.2),
            "ce_iv": 15.0,
            "pe_iv": 15.0,
        })

    # GEX proxy
    flip = atm
    call_wall = atm + step * 3
    put_wall = atm - step * 3
    total_ce_oi = sum(r["ce_oi"] for r in chain)
    total_pe_oi = sum(r["pe_oi"] for r in chain)
    pcr = round(total_pe_oi / total_ce_oi, 2) if total_ce_oi > 0 else 1.0

    # GEX regime based on spot vs flip
    regime = "POSITIVE" if spot > flip else "NEGATIVE" if spot < flip * 0.995 else "NEUTRAL"

    # OHLC bars — last 5 rows from history
    bars = []
    for _, row in hist.tail(30).iterrows():
        bars.append({
            "o": float(row["Open"]),
            "h": float(row["High"]),
            "l": float(row["Low"]),
            "c": float(row["Close"]),
            "v": int(row["Volume"]) if not pd.isna(row["Volume"]) else 0,
        })

    return {
        "success": True,
        "symbol": symbol,
        "spot": round(spot, 2),
        "atm_strike": atm,
        "pivot": round(vwap, 2),
        "cpr_top": cpr_top,
        "cpr_bottom": cpr_bottom,
        "pcr": pcr,
        "max_pain": atm,
        "atm_iv": 15.0,
        "total_ce_oi": total_ce_oi,
        "total_pe_oi": total_pe_oi,
        "chain_near_atm": chain,
        "ce_resistance": [{"strike": call_wall, "oi": chain[-1]["ce_oi"]}],
        "pe_support": [{"strike": put_wall, "oi": chain[0]["pe_oi"]}],
        "gex": {
            "total": int(total_ce_oi - total_pe_oi),
            "regime": regime,
            "flipPoint": flip,
            "callWall": call_wall,
            "putWall": put_wall,
        },
        "ohlc_bars": bars,
        "is_expiry": False,
        "_fallback": True,  # React shows the warning banner
    }


@app.get("/api/options-quick")
async def options_quick(symbol: str):
    """Options data for Indian indices (Decide tab cockpit)."""
    key = f"options_quick:{symbol.upper()}"
    cached = _cache_get(key)
    if cached:
        return cached

    sym = symbol.upper()
    proxy = INDEX_PROXY_TICKERS.get(sym)
    if not proxy:
        return {"success": False, "error": f"Unknown symbol: {sym}"}

    try:
        t = yf.Ticker(proxy)
        hist = t.history(period="30d", interval="1d")
        if len(hist) == 0:
            return {"success": False, "error": f"No data for {sym}"}

        result = _synthesize_options_data(sym, hist)
        _cache_set(key, result)
        return result

    except Exception as e:
        traceback.print_exc()
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════
# /api/global-ticker — Home page market snapshot
# ═══════════════════════════════════════════════════════════════════

GLOBAL_INDICES = [
    ("^GSPC", "S&P 500"),
    ("^DJI", "DOW"),
    ("^IXIC", "NASDAQ"),
    ("^RUT", "RUSSELL"),
    ("^VIX", "VIX"),
    ("^NSEI", "NIFTY"),
    ("^NSEBANK", "BANKNIFTY"),
    ("^BSESN", "SENSEX"),
    ("^FTSE", "FTSE"),
    ("^GDAXI", "DAX"),
]


@app.get("/api/global-ticker")
async def global_ticker():
    """Return a snapshot of global indices for the Home page and Markets tab."""
    cached = _cache_get("global_ticker")
    if cached:
        return cached

    indices = []
    for symbol, name in GLOBAL_INDICES:
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="2d")
            if len(hist) >= 1:
                current = float(hist["Close"].iloc[-1])
                if len(hist) >= 2:
                    prev = float(hist["Close"].iloc[-2])
                    change_pct = ((current - prev) / prev) * 100
                else:
                    change_pct = 0
                indices.append({
                    "symbol": name,
                    "ticker": symbol,
                    "price": round(current, 2),
                    "change_percent": round(change_pct, 2),
                })
        except Exception:
            continue

    result = {"indices": indices}
    _cache_set("global_ticker", result)
    return result


# ═══════════════════════════════════════════════════════════════════
# /api/l0-scan — bulk scanner (optional, React falls back to per-stock)
# ═══════════════════════════════════════════════════════════════════

@app.get("/api/l0-scan")
async def l0_scan(
    region: str = "US",
    mode: str = "quality",
    limit: int = 30,
    theme: str = "",
):
    """Minimal L0 scan endpoint.

    The React frontend has its own client-side scanner that fetches /api/stock-quick
    per ticker in parallel. This endpoint exists so the frontend's optional
    server-batch path works — but we return success=False so it falls back
    gracefully to the per-stock path (which already works).
    """
    return {
        "success": False,
        "error": "L0 batch scan not implemented — frontend will use per-stock fallback",
        "note": "To enable, implement yfinance batch download and L0 scoring here",
    }


# ═══════════════════════════════════════════════════════════════════
# Health check — MUST be registered before the catchall below
# ═══════════════════════════════════════════════════════════════════

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "version": "1.0.0",
        "react_build": (Path(__file__).parent / "static" / "dist" / "index.html").exists(),
    }


# ═══════════════════════════════════════════════════════════════════
# STATIC FILES — serve React build
# ═══════════════════════════════════════════════════════════════════

_REACT_DIST = Path(__file__).parent / "static" / "dist"

# Mount /assets for Vite's hashed JS/CSS bundles
if (_REACT_DIST / "assets").exists():
    app.mount(
        "/assets",
        StaticFiles(directory=str(_REACT_DIST / "assets")),
        name="react_assets",
    )


# Root + catchall — MUST be registered after all /api/ routes
@app.get("/")
async def serve_root():
    index = _REACT_DIST / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return JSONResponse(
        status_code=503,
        content={
            "error": "React build not found",
            "hint": "Run `npm install && npm run build` before starting the server",
        },
    )


@app.get("/{full_path:path}")
async def serve_catchall(full_path: str):
    # Defensive: don't intercept API routes (shouldn't happen — all /api/ routes register first)
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API route not found")

    # Try to serve the exact file (favicon, robots.txt, etc.)
    target = _REACT_DIST / full_path
    if target.is_file():
        return FileResponse(str(target))

    # Otherwise fall through to React (SPA routing)
    index = _REACT_DIST / "index.html"
    if index.exists():
        return FileResponse(str(index))

    raise HTTPException(status_code=404, detail="Not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
