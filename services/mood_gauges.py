"""
r63.72.28 — Mood Gauges (Market / Sector / Stock).

Three 0-100 sentiment scores rendered as semi-circle gauges in the DD report.

  MARKET MOOD: Fear & Greed Index for the broad market (S&P 500 / NIFTY)
    Components: index momentum, volatility (VIX), market breadth proxy

  SECTOR MOOD: Same formula applied to the stock's sector ETF
    For US: stock sector → XL* ETF (XLK tech, XLF financials, etc.)
    For IN: stock sector → NIFTY sector index (NIFTY IT, NIFTY BANK, etc.)

  STOCK MOOD: Stock-specific sentiment
    Components: today's move, 5d momentum, RSI(14), relative strength vs sector

Score bands (universal):
   0-25   EXTREME FEAR    deep red    panic-level
  25-45   FEAR            red         bearish
  45-55   NEUTRAL         gray        sideways
  55-75   GREED           green       bullish
  75-100  EXTREME GREED   bright grn  euphoric

Design:
  - Hard timeouts (4s per fetch)
  - Graceful degradation — missing component → still produce score from rest
  - Reuses existing app cache where possible (cached_yahoo_history, _pulse_cache)
  - 5-minute cache per (region, ticker)
"""

import time
import threading
import statistics
import math
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

_mood_cache: Dict[str, tuple] = {}
_mood_lock = threading.Lock()
_CACHE_TTL = 300  # 5 min


# ─── SECTOR ETF MAPPING ─────────────────────────────────────────────────

# US: GICS sectors → SPDR sector ETF
_US_SECTOR_ETF = {
    "technology":              ("XLK",  "Technology"),
    "information technology":  ("XLK",  "Technology"),
    "communication services":  ("XLC",  "Communication Services"),
    "communications":          ("XLC",  "Communication Services"),
    "consumer cyclical":       ("XLY",  "Consumer Cyclical"),
    "consumer discretionary":  ("XLY",  "Consumer Discretionary"),
    "consumer defensive":      ("XLP",  "Consumer Defensive"),
    "consumer staples":        ("XLP",  "Consumer Staples"),
    "energy":                  ("XLE",  "Energy"),
    "financial":               ("XLF",  "Financials"),
    "financials":              ("XLF",  "Financials"),
    "financial services":      ("XLF",  "Financials"),
    "healthcare":              ("XLV",  "Healthcare"),
    "health care":             ("XLV",  "Healthcare"),
    "industrials":             ("XLI",  "Industrials"),
    "industrial":              ("XLI",  "Industrials"),
    "materials":               ("XLB",  "Materials"),
    "basic materials":         ("XLB",  "Materials"),
    "real estate":             ("XLRE", "Real Estate"),
    "utilities":               ("XLU",  "Utilities"),
    "semiconductors":          ("SMH",  "Semiconductors"),
}

# India: sectors → NIFTY sector index (used with .NS suffix in yfinance)
_IN_SECTOR_ETF = {
    "technology":              ("^CNXIT",        "NIFTY IT"),
    "information technology":  ("^CNXIT",        "NIFTY IT"),
    "it":                      ("^CNXIT",        "NIFTY IT"),
    "financial":               ("^NSEBANK",      "NIFTY BANK"),
    "financials":              ("^NSEBANK",      "NIFTY BANK"),
    "financial services":      ("^NSEBANK",      "NIFTY BANK"),
    "banking":                 ("^NSEBANK",      "NIFTY BANK"),
    "auto":                    ("^CNXAUTO",      "NIFTY AUTO"),
    "automobile":              ("^CNXAUTO",      "NIFTY AUTO"),
    "pharmaceutical":          ("^CNXPHARMA",    "NIFTY PHARMA"),
    "healthcare":              ("^CNXPHARMA",    "NIFTY PHARMA"),
    "fmcg":                    ("^CNXFMCG",      "NIFTY FMCG"),
    "consumer":                ("^CNXFMCG",      "NIFTY FMCG"),
    "energy":                  ("^CNXENERGY",    "NIFTY ENERGY"),
    "oil":                     ("^CNXENERGY",    "NIFTY ENERGY"),
    "infrastructure":          ("^CNXINFRA",     "NIFTY INFRA"),
    "metal":                   ("^CNXMETAL",     "NIFTY METAL"),
    "realty":                  ("^CNXREALTY",    "NIFTY REALTY"),
    "real estate":             ("^CNXREALTY",    "NIFTY REALTY"),
}

# Broad market index per region
_MARKET_INDEX = {
    "US": ("^GSPC", "S&P 500"),
    "IN": ("^NSEI", "NIFTY 50"),
}

_VIX_INDEX = {
    "US": ("^VIX",      "VIX"),
    "IN": ("^INDIAVIX", "India VIX"),
}


def _map_sector_to_etf(sector: str, region: str) -> Tuple[Optional[str], Optional[str]]:
    """Map a sector name to (etf_ticker, etf_label). Returns (None, None) if no match."""
    if not sector:
        return None, None
    s = sector.lower().strip()
    mapping = _IN_SECTOR_ETF if region.upper() == "IN" else _US_SECTOR_ETF
    for keyword, (etf, label) in mapping.items():
        if keyword in s:
            return etf, label
    return None, None


# ─── DATA FETCHERS ──────────────────────────────────────────────────────

def _fetch_with_timeout(fn, timeout_sec: float, default=None):
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(fn)
        try:
            return fut.result(timeout=timeout_sec)
        except (FuturesTimeoutError, Exception):
            return default


def _fetch_ticker_history(yf_symbol: str, period: str = "60d") -> Optional[dict]:
    """Fetch closes + volumes for an index/ETF/stock. Hard 4s timeout."""
    def _go():
        try:
            import yfinance as yf
            try:
                from api import _yahoo_rate_wait
                _yahoo_rate_wait()
            except Exception:
                pass
            tk = yf.Ticker(yf_symbol)
            hist = tk.history(period=period, interval="1d")
            if hist is None or len(hist) == 0:
                return None
            closes = [float(c) for c in hist["Close"].tolist() if c == c]
            volumes = [int(v) for v in hist["Volume"].tolist() if v == v]
            return {"closes": closes, "volumes": volumes, "yf_symbol": yf_symbol}
        except Exception:
            return None
    return _fetch_with_timeout(_go, timeout_sec=4.0, default=None)


def _fetch_vix(region: str) -> Optional[float]:
    """Fetch latest VIX value. Hard 3s timeout. Returns None on failure."""
    vix_sym = _VIX_INDEX.get(region.upper(), ("^VIX", "VIX"))[0]
    def _go():
        try:
            import yfinance as yf
            try:
                from api import _yahoo_rate_wait
                _yahoo_rate_wait()
            except Exception:
                pass
            tk = yf.Ticker(vix_sym)
            hist = tk.history(period="5d", interval="1d")
            if hist is None or len(hist) == 0:
                return None
            closes = [float(c) for c in hist["Close"].tolist() if c == c]
            return closes[-1] if closes else None
        except Exception:
            return None
    return _fetch_with_timeout(_go, timeout_sec=3.0, default=None)


# ─── SCORING COMPONENTS ─────────────────────────────────────────────────

def _score_momentum(closes: List[float]) -> Tuple[Optional[float], dict]:
    """
    Price momentum score 0-100:
      Combines: position vs 20-day MA, position vs 50-day MA, 5-day return.
      Higher = more bullish.
    """
    if not closes or len(closes) < 20:
        return None, {}
    current = closes[-1]
    ma20 = sum(closes[-20:]) / 20
    ma50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else ma20
    
    # Position vs MAs
    pct_above_ma20 = ((current - ma20) / ma20) * 100 if ma20 > 0 else 0
    pct_above_ma50 = ((current - ma50) / ma50) * 100 if ma50 > 0 else 0
    
    # 5d return
    ret_5d = ((current - closes[-5]) / closes[-5]) * 100 if len(closes) >= 5 and closes[-5] > 0 else 0
    
    # Score each (0-100), then average
    # Position vs MA20: -10% = 0, 0% = 50, +10% = 100
    s1 = max(0, min(100, 50 + pct_above_ma20 * 5))
    s2 = max(0, min(100, 50 + pct_above_ma50 * 3))  # MA50 wider band
    s3 = max(0, min(100, 50 + ret_5d * 5))  # 5d return: -10% = 0, +10% = 100
    
    score = (s1 + s2 + s3) / 3
    return score, {
        "pct_above_ma20": round(pct_above_ma20, 2),
        "pct_above_ma50": round(pct_above_ma50, 2),
        "ret_5d_pct":      round(ret_5d, 2),
        "current":         round(current, 2),
        "ma20":            round(ma20, 2),
        "ma50":            round(ma50, 2),
    }


def _score_rsi(closes: List[float]) -> Tuple[Optional[float], dict]:
    """RSI-based score: <30 oversold = fear (low), >70 overbought = greed (high)."""
    if not closes or len(closes) < 15:
        return None, {}
    period = 14
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        if diff > 0:
            gains.append(diff); losses.append(0)
        else:
            gains.append(0); losses.append(-diff)
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        rsi = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
    # RSI directly maps to mood: 30 → 30, 50 → 50, 70 → 70
    return rsi, {"rsi": round(rsi, 1)}


def _score_volatility(vix: Optional[float]) -> Tuple[Optional[float], dict]:
    """
    VIX-based score (inverse — high VIX = fear, low VIX = greed):
      VIX <12 = 100 (extreme greed/complacency)
      VIX 12-18 = 70-100 (greed)
      VIX 18-25 = 40-70 (neutral)
      VIX 25-35 = 15-40 (fear)
      VIX 35+ = 0-15 (extreme fear)
    """
    if vix is None:
        return None, {}
    if vix < 12:
        s = 100
    elif vix < 18:
        s = 100 - (vix - 12) * 5  # 100 → 70
    elif vix < 25:
        s = 70 - (vix - 18) * (30 / 7)  # 70 → 40
    elif vix < 35:
        s = 40 - (vix - 25) * 2.5  # 40 → 15
    else:
        s = max(0, 15 - (vix - 35) * 1)
    return max(0, min(100, s)), {"vix": round(vix, 2)}


def _score_breadth(closes_list: List[List[float]]) -> Tuple[Optional[float], dict]:
    """
    Simplified breadth proxy: among supplied series, what % are above their 20-day MA?
    Used only for market mood (apply to a basket of major index components).
    Skipped for sector/stock mood (single instrument).
    """
    if not closes_list:
        return None, {}
    above = 0
    total = 0
    for closes in closes_list:
        if len(closes) < 20:
            continue
        ma20 = sum(closes[-20:]) / 20
        if closes[-1] > ma20:
            above += 1
        total += 1
    if total == 0:
        return None, {}
    pct_above = (above / total) * 100
    return pct_above, {"breadth_pct": round(pct_above, 1), "tickers_above": above, "tickers_total": total}


def _score_relative_strength(stock_closes: List[float], sector_closes: List[float]) -> Tuple[Optional[float], dict]:
    """
    Relative strength: stock's recent return vs sector's recent return.
    +5pp outperformance = strongly bullish for the stock mood.
    """
    if not stock_closes or not sector_closes or len(stock_closes) < 20 or len(sector_closes) < 20:
        return None, {}
    stock_ret = ((stock_closes[-1] - stock_closes[-20]) / stock_closes[-20]) * 100 if stock_closes[-20] > 0 else 0
    sector_ret = ((sector_closes[-1] - sector_closes[-20]) / sector_closes[-20]) * 100 if sector_closes[-20] > 0 else 0
    diff = stock_ret - sector_ret
    # Map: -15pp = 10, -5pp = 30, 0 = 50, +5pp = 70, +15pp = 90
    if diff > 15:
        s = 90 + min(10, (diff - 15) * 1)
    elif diff > 5:
        s = 70 + (diff - 5) * 2  # 70 → 90
    elif diff > 0:
        s = 50 + diff * 4  # 50 → 70
    elif diff > -5:
        s = 50 + diff * 4  # 30 → 50
    elif diff > -15:
        s = 30 + (diff + 5) * 2  # 10 → 30
    else:
        s = max(0, 10 + (diff + 15) * 0.5)
    return max(0, min(100, s)), {"stock_ret_20d": round(stock_ret, 2), "sector_ret_20d": round(sector_ret, 2), "diff_pp": round(diff, 2)}


# ─── BAND CLASSIFICATION ────────────────────────────────────────────────

def _classify_mood(score: Optional[float]) -> dict:
    """Returns dict with label, color, magnitude."""
    if score is None:
        return {"label": "NO DATA", "color": "#cbd5e1", "magnitude": "none"}
    if score < 25:
        return {"label": "EXTREME FEAR", "color": "#991b1b", "magnitude": "extreme_fear"}
    if score < 45:
        return {"label": "FEAR", "color": "#dc2626", "magnitude": "fear"}
    if score < 55:
        return {"label": "NEUTRAL", "color": "#94a3b8", "magnitude": "neutral"}
    if score < 75:
        return {"label": "GREED", "color": "#10b981", "magnitude": "greed"}
    return {"label": "EXTREME GREED", "color": "#059669", "magnitude": "extreme_greed"}


# ─── MOOD CALCULATORS ───────────────────────────────────────────────────

def _calc_market_mood(region: str) -> dict:
    """Market-wide mood: index momentum + VIX + (light) breadth."""
    idx_sym, idx_label = _MARKET_INDEX.get(region.upper(), ("^GSPC", "S&P 500"))
    
    # Index history
    idx_data = _fetch_ticker_history(idx_sym, period="60d")
    idx_closes = idx_data["closes"] if idx_data else []
    
    # VIX
    vix_val = _fetch_vix(region)
    
    # Score components
    mom_score, mom_meta = _score_momentum(idx_closes)
    rsi_score, rsi_meta = _score_rsi(idx_closes)
    vol_score, vol_meta = _score_volatility(vix_val)
    
    # Composite: 50% momentum, 25% RSI, 25% volatility (when all present)
    components = []
    if mom_score is not None: components.append((mom_score, 0.50))
    if rsi_score is not None: components.append((rsi_score, 0.25))
    if vol_score is not None: components.append((vol_score, 0.25))
    
    if not components:
        return _empty_mood("Market", idx_label, "Index data unavailable")
    
    total_w = sum(w for _, w in components)
    composite = sum(s * w for s, w in components) / total_w
    band = _classify_mood(composite)
    
    return {
        "label":           "Market",
        "symbol":          idx_sym,
        "instrument":      idx_label,
        "score":           round(composite, 1),
        "band":            band,
        "components": {
            "momentum":   {"score": round(mom_score, 1) if mom_score else None, **mom_meta},
            "rsi":        {"score": round(rsi_score, 1) if rsi_score else None, **rsi_meta},
            "volatility": {"score": round(vol_score, 1) if vol_score else None, **vol_meta},
        },
        "partial_data":    len(components) < 3,
        "components_present": len(components),
    }


def _calc_sector_mood(sector: str, region: str) -> dict:
    """Sector mood for the stock's sector ETF."""
    etf_sym, etf_label = _map_sector_to_etf(sector, region)
    if not etf_sym:
        return _empty_mood("Sector", "Unknown sector", f"Could not map '{sector}' to a sector ETF")
    
    etf_data = _fetch_ticker_history(etf_sym, period="60d")
    if not etf_data:
        return _empty_mood("Sector", etf_label, f"Could not fetch {etf_sym} data")
    
    closes = etf_data["closes"]
    mom_score, mom_meta = _score_momentum(closes)
    rsi_score, rsi_meta = _score_rsi(closes)
    
    components = []
    if mom_score is not None: components.append((mom_score, 0.60))
    if rsi_score is not None: components.append((rsi_score, 0.40))
    
    if not components:
        return _empty_mood("Sector", etf_label, "Insufficient ETF history")
    
    total_w = sum(w for _, w in components)
    composite = sum(s * w for s, w in components) / total_w
    band = _classify_mood(composite)
    
    return {
        "label":           "Sector",
        "symbol":          etf_sym,
        "instrument":      etf_label,
        "score":           round(composite, 1),
        "band":            band,
        "components": {
            "momentum":   {"score": round(mom_score, 1) if mom_score else None, **mom_meta},
            "rsi":        {"score": round(rsi_score, 1) if rsi_score else None, **rsi_meta},
        },
        "partial_data":    len(components) < 2,
        "components_present": len(components),
    }


def _calc_stock_mood(ticker: str, sector: str, region: str) -> dict:
    """Stock-specific mood: momentum + RSI + relative strength vs sector."""
    yf_sym = ticker if region.upper() == "US" else f"{ticker}.NS"
    stock_data = _fetch_ticker_history(yf_sym, period="60d")
    if not stock_data:
        return _empty_mood("Stock", ticker, f"Could not fetch {ticker} history")
    
    closes = stock_data["closes"]
    mom_score, mom_meta = _score_momentum(closes)
    rsi_score, rsi_meta = _score_rsi(closes)
    
    # Relative strength vs sector
    rs_score = None
    rs_meta = {}
    etf_sym, _ = _map_sector_to_etf(sector, region)
    if etf_sym:
        sector_data = _fetch_ticker_history(etf_sym, period="60d")
        if sector_data:
            rs_score, rs_meta = _score_relative_strength(closes, sector_data["closes"])
    
    components = []
    if mom_score is not None: components.append((mom_score, 0.40))
    if rsi_score is not None: components.append((rsi_score, 0.30))
    if rs_score is not None: components.append((rs_score, 0.30))
    
    if not components:
        return _empty_mood("Stock", ticker, "Insufficient stock history")
    
    total_w = sum(w for _, w in components)
    composite = sum(s * w for s, w in components) / total_w
    band = _classify_mood(composite)
    
    return {
        "label":           "Stock",
        "symbol":          ticker,
        "instrument":      ticker,
        "score":           round(composite, 1),
        "band":            band,
        "components": {
            "momentum":          {"score": round(mom_score, 1) if mom_score else None, **mom_meta},
            "rsi":               {"score": round(rsi_score, 1) if rsi_score else None, **rsi_meta},
            "relative_strength": {"score": round(rs_score, 1) if rs_score is not None else None, **rs_meta},
        },
        "partial_data":    len(components) < 3,
        "components_present": len(components),
    }


def _empty_mood(label: str, instrument: str, reason: str) -> dict:
    return {
        "label":           label,
        "symbol":          "",
        "instrument":      instrument,
        "score":           None,
        "band":            _classify_mood(None),
        "components":      {},
        "reason_unavailable": reason,
        "partial_data":    True,
        "components_present": 0,
    }


# ─── DIVERGENCE NARRATIVE ───────────────────────────────────────────────

def _build_layman(market: dict, sector: dict, stock: dict, ticker: str) -> str:
    """Plain-English explanation of the three moods + their alignment."""
    parts = []
    
    # Individual readings
    if stock.get("score") is not None:
        sb = stock["band"]["label"]
        parts.append(f"{ticker} mood: {sb} ({stock['score']:.0f}).")
    if sector.get("score") is not None:
        parts.append(f"{sector['instrument']} sector mood: {sector['band']['label']} ({sector['score']:.0f}).")
    if market.get("score") is not None:
        parts.append(f"Broad market ({market['instrument']}) mood: {market['band']['label']} ({market['score']:.0f}).")
    
    # Divergence analysis (the actually useful part)
    scores_present = [s for s in [market.get("score"), sector.get("score"), stock.get("score")] if s is not None]
    if len(scores_present) >= 2:
        stk = stock.get("score")
        sct = sector.get("score")
        mkt = market.get("score")
        
        if stk is not None and sct is not None:
            diff_stk_sct = stk - sct
            if diff_stk_sct > 15:
                parts.append(f"⚡ DIVERGENCE: {ticker} is significantly more bullish than its sector (+{diff_stk_sct:.0f}pts) — outperformance signal.")
            elif diff_stk_sct < -15:
                parts.append(f"⚠ DIVERGENCE: {ticker} is significantly more bearish than its sector ({diff_stk_sct:.0f}pts) — underperformance signal.")
        
        if sct is not None and mkt is not None:
            diff_sct_mkt = sct - mkt
            if abs(diff_sct_mkt) > 15:
                if diff_sct_mkt > 0:
                    parts.append(f"Sector is leading the broader market (+{diff_sct_mkt:.0f}pts) — rotation into this sector.")
                else:
                    parts.append(f"Sector is lagging the broader market ({diff_sct_mkt:.0f}pts) — rotation out of this sector.")
        
        # Three-way alignment
        if all(s is not None for s in [mkt, sct, stk]):
            if all(s >= 55 for s in [mkt, sct, stk]):
                parts.append("📈 All three moods aligned BULLISH — broad-based strength supporting this stock.")
            elif all(s <= 45 for s in [mkt, sct, stk]):
                parts.append("📉 All three moods aligned BEARISH — broad-based weakness, not stock-specific.")
            elif stk >= 55 and (mkt <= 45 or sct <= 45):
                parts.append(f"🎯 {ticker} is bullish DESPITE weaker market/sector — relative strength.")
            elif stk <= 45 and (mkt >= 55 or sct >= 55):
                parts.append(f"🎯 {ticker} is bearish DESPITE stronger market/sector — relative weakness.")
    
    return " ".join(parts) if parts else "Mood data unavailable."


# ─── TOP-LEVEL ──────────────────────────────────────────────────────────

def get_mood_gauges(ticker: str, sector: str = "", region: str = "US") -> dict:
    """Build market/sector/stock mood for a ticker."""
    cache_key = f"{ticker.strip().upper()}:{(sector or '').lower()}:{region.upper()}"
    now = time.time()
    with _mood_lock:
        cached = _mood_cache.get(cache_key)
        if cached and (now - cached[0]) < _CACHE_TTL:
            return cached[1]
    
    # Compute all three moods (sequential here; each has its own timeout)
    market = _calc_market_mood(region)
    sector_mood = _calc_sector_mood(sector, region)
    stock_mood = _calc_stock_mood(ticker, sector, region)
    
    layman = _build_layman(market, sector_mood, stock_mood, ticker.upper())
    
    # Overall partial-data flag
    any_data = (market.get("score") is not None or sector_mood.get("score") is not None or stock_mood.get("score") is not None)
    all_full = (
        market.get("components_present", 0) >= 3 and
        sector_mood.get("components_present", 0) >= 2 and
        stock_mood.get("components_present", 0) >= 3
    )
    
    result = {
        "success":        True,
        "ticker":         ticker.strip().upper(),
        "sector":         sector,
        "region":         region.upper(),
        "section":        "mood_gauges",
        "market":         market,
        "sector_mood":    sector_mood,
        "stock":          stock_mood,
        "layman":         layman,
        "partial_data":   not all_full,
        "no_data":        not any_data,
        "confidence":     "high" if all_full else "medium" if any_data else "low",
        "data_sources":   {"history": "yfinance"},
    }
    
    with _mood_lock:
        _mood_cache[cache_key] = (now, result)
    return result
