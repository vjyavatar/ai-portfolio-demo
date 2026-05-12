"""
r63.72.29 — Positioning Intelligence

Three-layer institutional framework, replacing the single "Mood" score:

  LAYER 1: MARKET REGIME       (is the macro tape healthy?)
       - Liquidity proxy        (US10Y trend + DXY)
       - Volatility regime      (VIX vs 1Y average)
       - Market breadth         (index above MA20 + 5d return)

  LAYER 2: SECTOR FLOW          (where is money flowing?)
       - Flow Strength          (sector ETF momentum + RSI)
       - Leadership Rank        (this sector vs all 11 SPDRs / NIFTY sector indices)
       - Institutional Rotation (sector 20-d return minus SPY 20-d return)

  LAYER 3: STOCK 4D POSITIONING (the institutional decision matrix)
       Four INDEPENDENT scores, never blended into one number:

       1. FLOW STRENGTH         "Are buyers chasing this right now?"
            - 20d momentum, RSI(14), relative strength vs sector, insider buys

       2. VALUATION COMFORT     "Is this price reasonable?" (HIGH = cheap)
            - Fwd P/E vs own 5y range, P/S vs own range, PEG approximation

       3. BUSINESS QUALITY      "Is this a good company, independent of price?"
            - Gross margin trend, operating margin trend, ROE, revenue growth, FCF margin

       4. RISK / CROWDING       "How extended is this trade?" (HIGH = safe, LOW = crowded)
            - % above MA50, % above MA200, parabolic-move detector, insider selling

  SYNTHESIS: Four institutional questions, each answered from a specific pair:
       - Good company?  ← Business Quality
       - Good stock?    ← Business Quality + Flow
       - Good trade?    ← Flow + Risk
       - Good entry NOW? ← Risk + Valuation

Design principles (carried forward from r63.72.25+):
  - Hard timeouts per fetch (4-6s)
  - Graceful degradation; missing component → still score from rest, flag confidence
  - No fake data; missing inputs surface as N/A
  - 5-minute cache
"""

import time
import threading
import statistics
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError


_pi_cache: Dict[str, tuple] = {}
_pi_lock = threading.Lock()
_CACHE_TTL = 300  # 5 min


# ═════════════════════════════════════════════════════════════════════════
# Sector ETF maps (reused/extended from mood_gauges)
# ═════════════════════════════════════════════════════════════════════════

# Full SPDR roster for leadership ranking
_US_SECTOR_UNIVERSE = [
    ("XLK",  "Technology"),
    ("XLF",  "Financials"),
    ("XLV",  "Healthcare"),
    ("XLE",  "Energy"),
    ("XLC",  "Communication Services"),
    ("XLY",  "Consumer Cyclical"),
    ("XLP",  "Consumer Defensive"),
    ("XLI",  "Industrials"),
    ("XLB",  "Materials"),
    ("XLRE", "Real Estate"),
    ("XLU",  "Utilities"),
    ("SMH",  "Semiconductors"),
]

_IN_SECTOR_UNIVERSE = [
    ("^CNXIT",     "NIFTY IT"),
    ("^NSEBANK",   "NIFTY BANK"),
    ("^CNXPHARMA", "NIFTY PHARMA"),
    ("^CNXFMCG",   "NIFTY FMCG"),
    ("^CNXENERGY", "NIFTY ENERGY"),
    ("^CNXAUTO",   "NIFTY AUTO"),
    ("^CNXINFRA",  "NIFTY INFRA"),
    ("^CNXMETAL",  "NIFTY METAL"),
    ("^CNXREALTY", "NIFTY REALTY"),
]

_US_SECTOR_KEYWORD_MAP = {
    "technology":             "XLK", "information technology": "XLK", "semiconductors": "SMH",
    "communication":          "XLC", "communications":        "XLC",
    "consumer cyclical":      "XLY", "consumer discretionary": "XLY",
    "consumer defensive":     "XLP", "consumer staples":       "XLP",
    "energy":                 "XLE",
    "financial":              "XLF", "financials":             "XLF", "financial services": "XLF",
    "healthcare":             "XLV", "health care":            "XLV",
    "industrials":            "XLI", "industrial":             "XLI",
    "materials":              "XLB", "basic materials":        "XLB",
    "real estate":            "XLRE",
    "utilities":              "XLU",
}

_IN_SECTOR_KEYWORD_MAP = {
    "technology":             "^CNXIT",     "information technology": "^CNXIT", "it": "^CNXIT",
    "financial":              "^NSEBANK",   "financials":             "^NSEBANK", "banking": "^NSEBANK",
    "auto":                   "^CNXAUTO",   "automobile":             "^CNXAUTO",
    "pharmaceutical":         "^CNXPHARMA", "pharma":                 "^CNXPHARMA", "healthcare": "^CNXPHARMA",
    "fmcg":                   "^CNXFMCG",   "consumer":               "^CNXFMCG",
    "energy":                 "^CNXENERGY", "oil":                    "^CNXENERGY",
    "metal":                  "^CNXMETAL",
    "realty":                 "^CNXREALTY", "real estate":            "^CNXREALTY",
    "infrastructure":         "^CNXINFRA",
}


def _map_sector(sector: str, region: str) -> Tuple[Optional[str], Optional[str]]:
    """Map a free-text sector name to (etf_symbol, label)."""
    if not sector:
        return None, None
    s = sector.lower().strip()
    universe = _IN_SECTOR_UNIVERSE if region.upper() == "IN" else _US_SECTOR_UNIVERSE
    keyword_map = _IN_SECTOR_KEYWORD_MAP if region.upper() == "IN" else _US_SECTOR_KEYWORD_MAP
    for kw, etf in keyword_map.items():
        if kw in s:
            label = next((l for sym, l in universe if sym == etf), etf)
            return etf, label
    return None, None


# ═════════════════════════════════════════════════════════════════════════
# Shared utilities
# ═════════════════════════════════════════════════════════════════════════

def _fetch_with_timeout(fn, timeout_sec: float, default=None):
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(fn)
        try:
            return fut.result(timeout=timeout_sec)
        except (FuturesTimeoutError, Exception):
            return default


def _safe_history(symbol: str, period: str = "1y"):
    """Fetch yfinance OHLCV history with rate-limit respect. Hard 5s timeout. Returns dict or None."""
    def _go():
        try:
            import yfinance as yf
            try:
                from api import _yahoo_rate_wait
                _yahoo_rate_wait()
            except Exception:
                pass
            tk = yf.Ticker(symbol)
            hist = tk.history(period=period, interval="1d")
            if hist is None or len(hist) == 0:
                return None
            return {
                "closes":  [float(c) for c in hist["Close"].tolist()  if c == c],
                "volumes": [int(v)   for v in hist["Volume"].tolist() if v == v],
                "highs":   [float(h) for h in hist["High"].tolist()   if h == h],
                "lows":    [float(l) for l in hist["Low"].tolist()    if l == l],
            }
        except Exception:
            return None
    return _fetch_with_timeout(_go, timeout_sec=5.0, default=None)


def _safe_info_and_insiders(symbol: str):
    """Fetch info + insider transactions for a stock. Hard 6s timeout."""
    def _go():
        try:
            import yfinance as yf
            try:
                from api import _yahoo_rate_wait
                _yahoo_rate_wait()
            except Exception:
                pass
            tk = yf.Ticker(symbol)
            info = tk.info or {}
            try:
                insider_tx = tk.insider_transactions
            except Exception:
                insider_tx = None
            try:
                financials = tk.financials
            except Exception:
                financials = None
            return {"info": info, "insider_tx": insider_tx, "financials": financials}
        except Exception:
            return None
    return _fetch_with_timeout(_go, timeout_sec=6.0, default=None)


def _compute_rsi(closes: List[float], period: int = 14) -> Optional[float]:
    """Standard Wilder RSI(14)."""
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
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
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _percentile(value: float, series: List[float]) -> Optional[float]:
    """Where does `value` sit in `series` (0-100)? Returns None on empty."""
    if not series:
        return None
    sorted_s = sorted(series)
    below = sum(1 for v in sorted_s if v < value)
    return (below / len(sorted_s)) * 100


def _band_for_score(score: Optional[float], inverted: bool = False) -> dict:
    """
    Score-to-band classifier. Inverted=True for Risk/Crowding (high = safe).
    Returns dict with label + color.
    """
    if score is None:
        return {"label": "NO DATA", "color": "#cbd5e1"}
    if inverted:
        # Risk: high score = safe; low score = crowded
        if score >= 75: return {"label": "SAFE",      "color": "#059669"}
        if score >= 55: return {"label": "BALANCED",  "color": "#10b981"}
        if score >= 45: return {"label": "NEUTRAL",   "color": "#94a3b8"}
        if score >= 25: return {"label": "ELEVATED",  "color": "#dc2626"}
        return {"label": "CROWDED", "color": "#991b1b"}
    if score >= 75: return {"label": "VERY STRONG", "color": "#059669"}
    if score >= 55: return {"label": "STRONG",      "color": "#10b981"}
    if score >= 45: return {"label": "NEUTRAL",     "color": "#94a3b8"}
    if score >= 25: return {"label": "WEAK",        "color": "#dc2626"}
    return {"label": "VERY WEAK", "color": "#991b1b"}


# ═════════════════════════════════════════════════════════════════════════
# LAYER 3 — STOCK 4-DIMENSION SCORING
# ═════════════════════════════════════════════════════════════════════════

def score_flow_strength(stock_hist: dict, sector_hist: Optional[dict], insider_buys: int, insider_sells: int) -> dict:
    """
    Flow Strength: "Are buyers chasing this right now?"
    Components: 20d momentum (35%), RSI(14) (25%), relative strength vs sector (25%), insider activity (15%)
    HIGH = institutions accumulating, momentum strong, RS positive
    """
    components = {}
    weighted_scores = []

    # 20d momentum (current vs 20d ago)
    if stock_hist and len(stock_hist["closes"]) >= 20:
        current = stock_hist["closes"][-1]
        past = stock_hist["closes"][-20]
        ret_20d = ((current - past) / past) * 100 if past > 0 else 0
        # Map: -15% → 0, 0% → 50, +15% → 100
        mom_score = max(0, min(100, 50 + ret_20d * 3.33))
        components["momentum_20d"] = {"score": round(mom_score, 1), "ret_20d_pct": round(ret_20d, 2)}
        weighted_scores.append((mom_score, 0.35))

    # RSI(14)
    if stock_hist and len(stock_hist["closes"]) >= 15:
        rsi = _compute_rsi(stock_hist["closes"], 14)
        if rsi is not None:
            # For flow, RSI maps directly: 50=50, 70=70, 30=30
            components["rsi"] = {"score": round(rsi, 1), "rsi": round(rsi, 1)}
            weighted_scores.append((rsi, 0.25))

    # Relative strength vs sector (20d)
    if stock_hist and sector_hist and len(stock_hist["closes"]) >= 20 and len(sector_hist["closes"]) >= 20:
        stock_ret = ((stock_hist["closes"][-1] - stock_hist["closes"][-20]) / stock_hist["closes"][-20]) * 100 if stock_hist["closes"][-20] > 0 else 0
        sector_ret = ((sector_hist["closes"][-1] - sector_hist["closes"][-20]) / sector_hist["closes"][-20]) * 100 if sector_hist["closes"][-20] > 0 else 0
        diff_pp = stock_ret - sector_ret
        # Map: -10pp → 10, 0 → 50, +10pp → 90
        rs_score = max(0, min(100, 50 + diff_pp * 4))
        components["relative_strength"] = {"score": round(rs_score, 1), "diff_pp": round(diff_pp, 2)}
        weighted_scores.append((rs_score, 0.25))

    # Insider activity
    total_tx = insider_buys + insider_sells
    if total_tx >= 3:
        buy_ratio = insider_buys / total_tx
        # Map: 0% → 20, 50% → 50, 100% → 90
        ins_score = 20 + buy_ratio * 70
        components["insider_activity"] = {"score": round(ins_score, 1), "buys": insider_buys, "sells": insider_sells, "buy_ratio_pct": round(buy_ratio * 100, 0)}
        weighted_scores.append((ins_score, 0.15))

    # Composite (weighted average over components present)
    if not weighted_scores:
        return {"score": None, "band": _band_for_score(None), "components": components, "components_present": 0}
    total_w = sum(w for _, w in weighted_scores)
    composite = sum(s * w for s, w in weighted_scores) / total_w
    return {
        "score":              round(composite, 1),
        "band":               _band_for_score(composite),
        "components":         components,
        "components_present": len(weighted_scores),
    }


def score_valuation_comfort(info: dict, financials) -> dict:
    """
    Valuation Comfort: "Is this price reasonable?"
    HIGH = cheap; LOW = stretched/expensive.

    Components:
      - Forward P/E vs its own historical median (40%) — uses pe ratio from info
      - Forward P/E vs 5-year history percentile (30%) — requires historical earnings
      - P/S vs own range (20%) — uses priceToSalesTrailing12Months
      - PEG approximation: forward P/E / earnings growth (10%)

    DATA HONESTY: yfinance gives us forward P/E and trailing P/S directly.
    True historical P/E percentile requires multi-year data — we approximate using
    forward P/E vs trailing P/E (compression signal) when historical isn't accessible.
    """
    components = {}
    weighted_scores = []

    fwd_pe = info.get("forwardPE")
    trailing_pe = info.get("trailingPE")
    ps_ttm = info.get("priceToSalesTrailing12Months")
    eps_growth = info.get("earningsGrowth")  # 0.0-1.0 fraction
    rev_growth = info.get("revenueGrowth")

    # 1. Forward P/E reasonableness (sector-agnostic broad bands)
    if fwd_pe is not None and 0 < fwd_pe < 200:
        # General mapping (works for most stocks; tech/growth on the high end):
        #   <10 = very cheap (95), 15 = cheap (75), 20 = fair (55), 30 = expensive (30), 50+ = very expensive (10)
        if fwd_pe < 10:
            pe_score = 95
        elif fwd_pe < 15:
            pe_score = 95 - (fwd_pe - 10) * 4   # 95 → 75
        elif fwd_pe < 20:
            pe_score = 75 - (fwd_pe - 15) * 4   # 75 → 55
        elif fwd_pe < 30:
            pe_score = 55 - (fwd_pe - 20) * 2.5  # 55 → 30
        elif fwd_pe < 50:
            pe_score = 30 - (fwd_pe - 30) * 1   # 30 → 10
        else:
            pe_score = max(0, 10 - (fwd_pe - 50) * 0.2)
        components["forward_pe"] = {"score": round(pe_score, 1), "fwd_pe": round(fwd_pe, 2)}
        weighted_scores.append((pe_score, 0.40))

    # 2. P/E compression vs trailing — if forward < trailing, growth is expected (cheaper on fwd basis)
    if fwd_pe is not None and trailing_pe is not None and 0 < fwd_pe < 200 and 0 < trailing_pe < 500:
        compression = ((trailing_pe - fwd_pe) / trailing_pe) * 100 if trailing_pe > 0 else 0
        # +30% compression (expected earnings growth) → 80; 0% → 50; -30% (decline expected) → 20
        comp_score = max(0, min(100, 50 + compression * 1.0))
        components["pe_compression"] = {"score": round(comp_score, 1), "compression_pct": round(compression, 1), "trailing_pe": round(trailing_pe, 2)}
        weighted_scores.append((comp_score, 0.30))

    # 3. P/S band
    if ps_ttm is not None and 0 < ps_ttm < 100:
        # General: <2 cheap (80), 5 fair (50), 10 rich (30), 20+ extreme (10)
        if ps_ttm < 2:
            ps_score = 80 + max(0, (2 - ps_ttm) * 10)
        elif ps_ttm < 5:
            ps_score = 80 - (ps_ttm - 2) * 10  # 80 → 50
        elif ps_ttm < 10:
            ps_score = 50 - (ps_ttm - 5) * 4   # 50 → 30
        elif ps_ttm < 20:
            ps_score = 30 - (ps_ttm - 10) * 2  # 30 → 10
        else:
            ps_score = max(0, 10 - (ps_ttm - 20) * 0.3)
        ps_score = max(0, min(100, ps_score))
        components["price_to_sales"] = {"score": round(ps_score, 1), "ps_ttm": round(ps_ttm, 2)}
        weighted_scores.append((ps_score, 0.20))

    # 4. PEG-like (fwd_pe / growth_pct) — lower = better
    if fwd_pe is not None and 0 < fwd_pe < 200:
        growth_pct = None
        if eps_growth is not None and -0.5 < eps_growth < 5:
            growth_pct = eps_growth * 100
        elif rev_growth is not None and -0.5 < rev_growth < 5:
            growth_pct = rev_growth * 100  # fallback
        if growth_pct is not None and growth_pct > 0:
            peg = fwd_pe / growth_pct
            # PEG <0.7 = cheap (90), 1.0 = fair (60), 1.5 = expensive (30), 3.0+ = very expensive (10)
            if peg < 0.7:
                peg_score = 90
            elif peg < 1.0:
                peg_score = 90 - (peg - 0.7) * 100  # 90 → 60
            elif peg < 1.5:
                peg_score = 60 - (peg - 1.0) * 60   # 60 → 30
            elif peg < 3.0:
                peg_score = 30 - (peg - 1.5) * 13   # 30 → 10
            else:
                peg_score = max(0, 10 - (peg - 3.0) * 1)
            components["peg"] = {"score": round(peg_score, 1), "peg": round(peg, 2), "growth_pct": round(growth_pct, 1)}
            weighted_scores.append((peg_score, 0.10))

    # r63.72.29: CYCLE-PEAK PENALTY
    # When revenue growth >50% AND operating margins >25%, the company is likely
    # at cyclical peak. Forward P/E and PEG look artificially attractive because
    # earnings are inflated. Apply a penalty so the score reflects normalized risk.
    op_margins_now = info.get("operatingMargins")
    cycle_penalty_pct = 0
    cycle_warning = False
    if rev_growth is not None and op_margins_now is not None:
        if rev_growth > 0.5 and op_margins_now > 0.25:
            cycle_penalty_pct = 25  # 25% reduction in composite valuation score
            cycle_warning = True
        elif rev_growth > 0.30 and op_margins_now > 0.30:
            cycle_penalty_pct = 15
            cycle_warning = True
        elif rev_growth > 1.0:
            cycle_penalty_pct = 20  # extreme revenue growth alone is a cycle flag
            cycle_warning = True
    if cycle_warning:
        components["cycle_peak_warning"] = {
            "applied":          True,
            "penalty_pct":      cycle_penalty_pct,
            "rev_growth_pct":   round(rev_growth * 100, 1) if rev_growth is not None else None,
            "op_margin_pct":    round(op_margins_now * 100, 1) if op_margins_now is not None else None,
            "explain":          "Revenue + margins suggest cyclical peak. Forward P/E may look cheap because earnings are inflated above normalized levels.",
        }

    if not weighted_scores:
        return {"score": None, "band": _band_for_score(None), "components": components, "components_present": 0}
    total_w = sum(w for _, w in weighted_scores)
    composite = sum(s * w for s, w in weighted_scores) / total_w

    # Apply cycle-peak penalty
    if cycle_penalty_pct > 0:
        composite = composite * (1 - cycle_penalty_pct / 100)

    return {
        "score":              round(composite, 1),
        "band":               _band_for_score(composite),
        "components":         components,
        "components_present": len(weighted_scores),
        "cycle_peak_warning": cycle_warning,
    }


def score_business_quality(info: dict, financials) -> dict:
    """
    Business Quality: "Is this a good company, independent of price?"

    Components: gross margin (25%), operating margin (25%), revenue growth (20%),
                ROE (15%), FCF margin (15%)

    DATA HONESTY: this captures financial-quality dimensions. It does NOT specifically
    capture qualitative tailwinds like "AI exposure" or "HBM supply tightness" — those
    require sector-expert analysis or paid sector classifiers. Users should read this
    as "quantitative business strength" not "is the business in a great cyclical spot."
    """
    components = {}
    weighted_scores = []

    gm = info.get("grossMargins")
    om = info.get("operatingMargins")
    rev_g = info.get("revenueGrowth")
    roe = info.get("returnOnEquity")
    fcf = info.get("freeCashflow")
    revenue = info.get("totalRevenue")

    # Gross margin
    if gm is not None and -1 < gm < 1.5:
        gm_pct = gm * 100
        # <10% bad (10), 20% okay (40), 40% strong (75), 60%+ excellent (95)
        if gm_pct < 10:
            gm_score = max(0, gm_pct * 1)
        elif gm_pct < 20:
            gm_score = 10 + (gm_pct - 10) * 3   # 10 → 40
        elif gm_pct < 40:
            gm_score = 40 + (gm_pct - 20) * 1.75  # 40 → 75
        elif gm_pct < 60:
            gm_score = 75 + (gm_pct - 40) * 1     # 75 → 95
        else:
            gm_score = min(100, 95 + (gm_pct - 60) * 0.1)
        components["gross_margin"] = {"score": round(gm_score, 1), "gm_pct": round(gm_pct, 1)}
        weighted_scores.append((gm_score, 0.25))

    # Operating margin
    if om is not None and -1 < om < 1.5:
        om_pct = om * 100
        if om_pct < 0:
            om_score = max(0, 20 + om_pct * 1)  # negative penalized
        elif om_pct < 10:
            om_score = 20 + om_pct * 3   # 20 → 50
        elif om_pct < 25:
            om_score = 50 + (om_pct - 10) * 2  # 50 → 80
        elif om_pct < 40:
            om_score = 80 + (om_pct - 25) * 1  # 80 → 95
        else:
            om_score = min(100, 95 + (om_pct - 40) * 0.1)
        components["operating_margin"] = {"score": round(om_score, 1), "om_pct": round(om_pct, 1)}
        weighted_scores.append((om_score, 0.25))

    # Revenue growth
    if rev_g is not None and -0.5 < rev_g < 5:
        rg_pct = rev_g * 100
        if rg_pct < -5:
            rg_score = max(0, 20 + (rg_pct + 5) * 2)  # decline
        elif rg_pct < 5:
            rg_score = 20 + (rg_pct + 5) * 3  # -5% → 20, 5% → 50
        elif rg_pct < 15:
            rg_score = 50 + (rg_pct - 5) * 2.5  # 50 → 75
        elif rg_pct < 30:
            rg_score = 75 + (rg_pct - 15) * 1.33  # 75 → 95
        else:
            rg_score = min(100, 95 + (rg_pct - 30) * 0.1)
        components["revenue_growth"] = {"score": round(rg_score, 1), "rg_pct": round(rg_pct, 1)}
        weighted_scores.append((rg_score, 0.20))

    # ROE
    if roe is not None and -1 < roe < 5:
        roe_pct = roe * 100
        if roe_pct < 0:
            roe_score = max(0, 20 + roe_pct * 1)  # negative
        elif roe_pct < 10:
            roe_score = 20 + roe_pct * 3  # 20 → 50
        elif roe_pct < 25:
            roe_score = 50 + (roe_pct - 10) * 2  # 50 → 80
        elif roe_pct < 50:
            roe_score = 80 + (roe_pct - 25) * 0.6  # 80 → 95
        else:
            roe_score = min(100, 95)
        components["roe"] = {"score": round(roe_score, 1), "roe_pct": round(roe_pct, 1)}
        weighted_scores.append((roe_score, 0.15))

    # FCF margin
    if fcf is not None and revenue and revenue > 0:
        fcf_margin = (fcf / revenue) * 100
        if fcf_margin < -10:
            fcf_score = max(0, 10 + (fcf_margin + 10) * 1)
        elif fcf_margin < 0:
            fcf_score = 10 + (fcf_margin + 10) * 2  # 10 → 30
        elif fcf_margin < 10:
            fcf_score = 30 + fcf_margin * 3  # 30 → 60
        elif fcf_margin < 25:
            fcf_score = 60 + (fcf_margin - 10) * 2  # 60 → 90
        else:
            fcf_score = min(100, 90 + (fcf_margin - 25) * 0.4)
        components["fcf_margin"] = {"score": round(fcf_score, 1), "fcf_margin_pct": round(fcf_margin, 1)}
        weighted_scores.append((fcf_score, 0.15))

    if not weighted_scores:
        return {"score": None, "band": _band_for_score(None), "components": components, "components_present": 0}
    total_w = sum(w for _, w in weighted_scores)
    composite = sum(s * w for s, w in weighted_scores) / total_w
    return {
        "score":              round(composite, 1),
        "band":               _band_for_score(composite),
        "components":         components,
        "components_present": len(weighted_scores),
    }


def score_risk_crowding(stock_hist: dict, info: dict, insider_buys: int, insider_sells: int) -> dict:
    """
    Risk/Crowding: "How extended is this trade?"
    INVERTED interpretation — HIGH = safe; LOW = crowded/dangerous.

    Components:
      - Distance above MA50 (25%):    far above = crowded (LOW score)
      - Distance above MA200 (25%):   far above = crowded
      - Parabolic move detector (20%): recent acceleration
      - Insider selling (15%):        net selling = crowded distribution
      - Beta + volatility (15%):       higher beta + recent vol = riskier
    """
    components = {}
    weighted_scores = []

    if stock_hist and len(stock_hist["closes"]) >= 50:
        closes = stock_hist["closes"]
        current = closes[-1]
        ma50 = sum(closes[-50:]) / 50
        pct_above_ma50 = ((current - ma50) / ma50) * 100 if ma50 > 0 else 0
        # 0-2% above MA50 = ideal (80); +15% = crowded (20)
        if pct_above_ma50 < -10:
            ma50_score = 60  # well below — could be oversold setup, not crowded
        elif pct_above_ma50 < 2:
            ma50_score = 80 - abs(pct_above_ma50) * 1   # ~80 near it
        elif pct_above_ma50 < 8:
            ma50_score = 80 - (pct_above_ma50 - 2) * 5   # 80 → 50
        elif pct_above_ma50 < 15:
            ma50_score = 50 - (pct_above_ma50 - 8) * 4.3  # 50 → 20
        else:
            ma50_score = max(0, 20 - (pct_above_ma50 - 15) * 1)
        components["distance_ma50"] = {"score": round(ma50_score, 1), "pct_above_ma50": round(pct_above_ma50, 2)}
        weighted_scores.append((ma50_score, 0.25))

    if stock_hist and len(stock_hist["closes"]) >= 200:
        closes = stock_hist["closes"]
        current = closes[-1]
        ma200 = sum(closes[-200:]) / 200
        pct_above_ma200 = ((current - ma200) / ma200) * 100 if ma200 > 0 else 0
        # MA200 wider tolerance: 0-10% ideal (80); +30% crowded
        if pct_above_ma200 < -20:
            ma200_score = 50
        elif pct_above_ma200 < 10:
            ma200_score = 80 - abs(pct_above_ma200) * 0.5
        elif pct_above_ma200 < 25:
            ma200_score = 80 - (pct_above_ma200 - 10) * 3  # 80 → 35
        elif pct_above_ma200 < 50:
            ma200_score = 35 - (pct_above_ma200 - 25) * 1  # 35 → 10
        else:
            ma200_score = max(0, 10 - (pct_above_ma200 - 50) * 0.2)
        components["distance_ma200"] = {"score": round(ma200_score, 1), "pct_above_ma200": round(pct_above_ma200, 2)}
        weighted_scores.append((ma200_score, 0.25))

    # Parabolic detector: 20d return high AND 60d return much higher than 240d return
    if stock_hist and len(stock_hist["closes"]) >= 240:
        closes = stock_hist["closes"]
        ret_20d = ((closes[-1] - closes[-20]) / closes[-20]) * 100 if closes[-20] > 0 else 0
        ret_60d = ((closes[-1] - closes[-60]) / closes[-60]) * 100 if closes[-60] > 0 else 0
        ret_240d = ((closes[-1] - closes[-240]) / closes[-240]) * 100 if closes[-240] > 0 else 0
        # Parabolic if 20d > 15% AND 60d/240d ratio is extreme
        parabolic = ret_20d > 15 and (ret_60d > ret_240d * 0.5 if ret_240d > 0 else False)
        if parabolic:
            # The steeper the parabolic move, the lower the safety score
            para_score = max(5, 40 - max(0, ret_20d - 15) * 2)
        elif ret_20d > 25:
            para_score = max(10, 50 - (ret_20d - 25) * 2)
        else:
            para_score = 70
        components["parabolic_check"] = {"score": round(para_score, 1), "ret_20d_pct": round(ret_20d, 1), "ret_60d_pct": round(ret_60d, 1), "parabolic": parabolic}
        weighted_scores.append((para_score, 0.20))

    # Insider selling (high net selling = crowded distribution = LOW score)
    total_tx = insider_buys + insider_sells
    if total_tx >= 3:
        sell_ratio = insider_sells / total_tx if total_tx > 0 else 0
        # 100% selling = 20 (concerning); 50/50 = 60; 100% buying = 90
        ins_safety = 90 - sell_ratio * 70
        components["insider_distribution"] = {"score": round(ins_safety, 1), "sells": insider_sells, "buys": insider_buys, "sell_ratio_pct": round(sell_ratio * 100, 0)}
        weighted_scores.append((ins_safety, 0.15))

    # Beta + recent volatility
    beta = info.get("beta")
    if stock_hist and len(stock_hist["closes"]) >= 20 and beta is not None:
        recent_closes = stock_hist["closes"][-20:]
        if recent_closes[0] > 0:
            daily_rets = [(recent_closes[i] - recent_closes[i-1]) / recent_closes[i-1] for i in range(1, len(recent_closes))]
            if daily_rets:
                vol_20d = statistics.stdev(daily_rets) * 100 if len(daily_rets) > 1 else 0
                # Vol < 1.5% calm (80); 3% = 50; 5%+ = 20
                if vol_20d < 1.5:
                    vol_score = 80
                elif vol_20d < 3:
                    vol_score = 80 - (vol_20d - 1.5) * 20  # 80 → 50
                elif vol_20d < 5:
                    vol_score = 50 - (vol_20d - 3) * 15  # 50 → 20
                else:
                    vol_score = max(0, 20 - (vol_20d - 5) * 3)
                # Penalize high beta a bit
                if beta > 1.5:
                    vol_score *= 0.85
                components["volatility_beta"] = {"score": round(vol_score, 1), "vol_20d_pct": round(vol_20d, 2), "beta": round(beta, 2)}
                weighted_scores.append((vol_score, 0.15))

    if not weighted_scores:
        return {"score": None, "band": _band_for_score(None, inverted=True), "components": components, "components_present": 0}
    total_w = sum(w for _, w in weighted_scores)
    composite = sum(s * w for s, w in weighted_scores) / total_w
    return {
        "score":              round(composite, 1),
        "band":               _band_for_score(composite, inverted=True),
        "components":         components,
        "components_present": len(weighted_scores),
    }


# ═════════════════════════════════════════════════════════════════════════
# LAYER 1 — MARKET REGIME
# ═════════════════════════════════════════════════════════════════════════

def calc_market_regime(region: str) -> dict:
    """
    Market regime: 3 mini-scores.
      Liquidity: 10Y trend (lower yields = more liquidity = higher score) + dollar trend
      Volatility regime: VIX level + VIX vs 1Y avg
      Breadth: index above MA20 + 5d return + 20d return
    """
    region_u = region.upper()

    index_sym = "^GSPC" if region_u == "US" else "^NSEI"
    vix_sym = "^VIX" if region_u == "US" else "^INDIAVIX"

    idx_hist = _safe_history(index_sym, period="1y")
    vix_hist = _safe_history(vix_sym, period="1y")

    components = {}

    # 1. LIQUIDITY — use proxy: index drawdown from 1y high (smaller = better liquidity environment)
    #    We don't have direct 10Y/DXY here without another fetch; for now use a simpler proxy.
    if idx_hist and len(idx_hist["closes"]) >= 60:
        high_60d = max(idx_hist["closes"][-60:])
        current = idx_hist["closes"][-1]
        dd_from_high = ((high_60d - current) / high_60d) * 100 if high_60d > 0 else 0
        # 0% drawdown = healthy liquidity (85), 5% = 60, 10% = 35, 20%+ = 10
        if dd_from_high < 2:
            liq_score = 85
        elif dd_from_high < 5:
            liq_score = 85 - (dd_from_high - 2) * 8.33  # 85 → 60
        elif dd_from_high < 10:
            liq_score = 60 - (dd_from_high - 5) * 5   # 60 → 35
        elif dd_from_high < 20:
            liq_score = 35 - (dd_from_high - 10) * 2.5  # 35 → 10
        else:
            liq_score = max(0, 10 - (dd_from_high - 20) * 0.3)
        components["liquidity"] = {
            "score": round(liq_score, 1),
            "band": _band_for_score(liq_score),
            "label": "Liquidity",
            "detail": f"Index {round(dd_from_high, 1)}% off 60d high",
        }

    # 2. VOLATILITY REGIME — VIX current vs 1Y mean
    if vix_hist and len(vix_hist["closes"]) >= 60:
        vix_current = vix_hist["closes"][-1]
        vix_avg_1y = sum(vix_hist["closes"]) / len(vix_hist["closes"])
        # Score: low VIX, near 1Y avg = stable (high score). Spiking = low.
        if vix_current < 12:
            vol_score = 90
        elif vix_current < 18:
            vol_score = 90 - (vix_current - 12) * 5  # 90 → 60
        elif vix_current < 25:
            vol_score = 60 - (vix_current - 18) * 4.3  # 60 → 30
        elif vix_current < 35:
            vol_score = 30 - (vix_current - 25) * 2  # 30 → 10
        else:
            vol_score = max(0, 10 - (vix_current - 35) * 0.5)
        # Adjust for VIX above its own 1Y mean (more turbulent)
        if vix_avg_1y > 0 and vix_current > vix_avg_1y * 1.3:
            vol_score *= 0.8
        components["volatility_regime"] = {
            "score": round(vol_score, 1),
            "band": _band_for_score(vol_score),
            "label": "Volatility",
            "detail": f"VIX {round(vix_current, 1)} (1Y avg {round(vix_avg_1y, 1)})",
        }

    # 3. BREADTH (single-index proxy)
    if idx_hist and len(idx_hist["closes"]) >= 20:
        closes = idx_hist["closes"]
        ma20 = sum(closes[-20:]) / 20
        above_ma20 = closes[-1] > ma20
        ret_5d = ((closes[-1] - closes[-5]) / closes[-5]) * 100 if len(closes) >= 5 and closes[-5] > 0 else 0
        ret_20d = ((closes[-1] - closes[-20]) / closes[-20]) * 100 if closes[-20] > 0 else 0
        # Score: index above MA20 + positive trends
        brd_score = 50
        if above_ma20: brd_score += 15
        if ret_5d > 0:  brd_score += min(15, ret_5d * 3)
        if ret_5d < 0:  brd_score -= min(20, abs(ret_5d) * 3)
        if ret_20d > 0: brd_score += min(15, ret_20d * 1.5)
        if ret_20d < 0: brd_score -= min(20, abs(ret_20d) * 1.5)
        brd_score = max(0, min(100, brd_score))
        components["breadth"] = {
            "score": round(brd_score, 1),
            "band": _band_for_score(brd_score),
            "label": "Breadth",
            "detail": f"{'Above' if above_ma20 else 'Below'} MA20 · 5d {round(ret_5d, 1)}% · 20d {round(ret_20d, 1)}%",
        }

    if not components:
        return {"success": False, "components": {}, "verdict": "Data unavailable", "layman": "Market regime data unavailable."}

    # Verdict
    scores = [c["score"] for c in components.values() if c.get("score") is not None]
    avg = sum(scores) / len(scores) if scores else None
    if avg is None:
        verdict = "Insufficient data"
    elif avg >= 70:
        verdict = "RISK-ON · Healthy regime"
    elif avg >= 50:
        verdict = "NEUTRAL · Mixed signals"
    elif avg >= 30:
        verdict = "RISK-OFF · Caution warranted"
    else:
        verdict = "STRESS · Defensive positioning"

    # Layman
    layman_parts = ["The overall market environment for stocks right now."]
    if "liquidity" in components:
        layman_parts.append(f"Liquidity: {components['liquidity']['band']['label'].lower()}.")
    if "volatility_regime" in components:
        layman_parts.append(f"Volatility: {components['volatility_regime']['band']['label'].lower()}.")
    if "breadth" in components:
        layman_parts.append(f"Breadth: {components['breadth']['band']['label'].lower()}.")
    layman_parts.append(f"Overall verdict: {verdict}.")

    return {
        "success":    True,
        "index_symbol": index_sym,
        "components": components,
        "verdict":    verdict,
        "avg_score":  round(avg, 1) if avg is not None else None,
        "layman":     " ".join(layman_parts),
    }


# ═════════════════════════════════════════════════════════════════════════
# LAYER 2 — SECTOR FLOW
# ═════════════════════════════════════════════════════════════════════════

def calc_sector_flow(sector: str, region: str) -> dict:
    """
    Sector Flow: where is money flowing relative to the rest of the market?
    Returns: flow_score, leadership_rank, institutional_rotation (vs benchmark).
    """
    etf_sym, etf_label = _map_sector(sector, region)
    if not etf_sym:
        return {"success": False, "reason": f"Could not map sector '{sector}'", "layman": "Sector flow unavailable."}

    sector_hist = _safe_history(etf_sym, period="60d")
    if not sector_hist or len(sector_hist["closes"]) < 20:
        return {"success": False, "etf_symbol": etf_sym, "etf_label": etf_label, "reason": "Insufficient sector history", "layman": "Sector data unavailable."}

    # Flow Strength score (momentum + RSI)
    closes = sector_hist["closes"]
    current = closes[-1]
    ma20 = sum(closes[-20:]) / 20
    pct_above_ma20 = ((current - ma20) / ma20) * 100 if ma20 > 0 else 0
    ret_20d = ((current - closes[-20]) / closes[-20]) * 100 if closes[-20] > 0 else 0
    rsi = _compute_rsi(closes, 14)

    # Momentum sub-score
    mom = max(0, min(100, 50 + pct_above_ma20 * 4 + ret_20d * 1.5))
    rsi_score = rsi if rsi is not None else 50
    flow_score = mom * 0.6 + rsi_score * 0.4

    # Leadership rank — fetch all sector ETFs in this region's universe
    universe = _IN_SECTOR_UNIVERSE if region.upper() == "IN" else _US_SECTOR_UNIVERSE
    sector_returns = []
    for sym, label in universe:
        hist = _safe_history(sym, period="30d")
        if hist and len(hist["closes"]) >= 20:
            r = ((hist["closes"][-1] - hist["closes"][-20]) / hist["closes"][-20]) * 100 if hist["closes"][-20] > 0 else 0
            sector_returns.append({"symbol": sym, "label": label, "ret_20d": r})
    sector_returns.sort(key=lambda x: -x["ret_20d"])
    leadership_rank = None
    for i, sr in enumerate(sector_returns):
        if sr["symbol"] == etf_sym:
            leadership_rank = i + 1
            break

    # Institutional rotation: this sector's 20d return vs SPY (US) or NIFTY (IN)
    bench_sym = "SPY" if region.upper() == "US" else "^NSEI"
    bench_hist = _safe_history(bench_sym, period="60d")
    rotation_diff = None
    if bench_hist and len(bench_hist["closes"]) >= 20:
        bench_ret = ((bench_hist["closes"][-1] - bench_hist["closes"][-20]) / bench_hist["closes"][-20]) * 100 if bench_hist["closes"][-20] > 0 else 0
        rotation_diff = ret_20d - bench_ret

    layman = (
        f"Where money is flowing in/out of {etf_label} relative to the broader market. "
        f"Flow strength: {round(flow_score, 0)}/100. "
        + (f"Ranked #{leadership_rank} of {len(sector_returns)} sectors by 20-day return. " if leadership_rank else "")
        + (f"This sector is {'outperforming' if rotation_diff and rotation_diff > 0 else 'underperforming'} the broader market by {abs(round(rotation_diff, 1))}pp over 20 days. " if rotation_diff is not None else "")
    )

    return {
        "success":              True,
        "etf_symbol":           etf_sym,
        "etf_label":            etf_label,
        "flow_score":           round(flow_score, 1),
        "flow_band":            _band_for_score(flow_score),
        "leadership_rank":      leadership_rank,
        "leadership_universe_size": len(sector_returns),
        "rotation_vs_bench_pp": round(rotation_diff, 2) if rotation_diff is not None else None,
        "ret_20d_pct":          round(ret_20d, 2),
        "rsi":                  round(rsi, 1) if rsi is not None else None,
        "components": {
            "momentum": {"score": round(mom, 1), "ret_20d_pct": round(ret_20d, 2), "pct_above_ma20": round(pct_above_ma20, 2)},
            "rsi":      {"score": round(rsi_score, 1)} if rsi is not None else None,
        },
        "layman":               layman,
    }


# ═════════════════════════════════════════════════════════════════════════
# SYNTHESIS — answer the 4 institutional questions
# ═════════════════════════════════════════════════════════════════════════

def _synthesize_verdict(flow: dict, valuation: dict, quality: dict, risk: dict) -> dict:
    """
    Map the 4D scores to 4 institutional questions:
      Good company?       Business Quality
      Good stock?         Quality + Flow
      Good trade?         Flow + Risk
      Good entry NOW?     Risk + Valuation
    """
    def _verdict_word(score):
        if score is None: return "INSUFFICIENT DATA"
        if score >= 75: return "YES — STRONG"
        if score >= 60: return "YES"
        if score >= 45: return "MIXED"
        if score >= 30: return "LEAN NO"
        return "NO"

    def _avg(scores):
        valid = [s for s in scores if s is not None]
        return sum(valid) / len(valid) if valid else None

    good_company_s   = quality.get("score")
    good_stock_s     = _avg([quality.get("score"), flow.get("score")])
    good_trade_s     = _avg([flow.get("score"), risk.get("score")])
    good_entry_now_s = _avg([risk.get("score"), valuation.get("score")])

    return {
        "good_company": {
            "score":   round(good_company_s, 1) if good_company_s is not None else None,
            "verdict": _verdict_word(good_company_s),
            "explain": "Based on Business Quality (margins, growth, ROE, FCF).",
        },
        "good_stock": {
            "score":   round(good_stock_s, 1) if good_stock_s is not None else None,
            "verdict": _verdict_word(good_stock_s),
            "explain": "Business Quality + Flow Strength (is the market recognizing the quality?).",
        },
        "good_trade": {
            "score":   round(good_trade_s, 1) if good_trade_s is not None else None,
            "verdict": _verdict_word(good_trade_s),
            "explain": "Flow Strength + Risk score (is momentum strong without being too crowded?).",
        },
        "good_entry_now": {
            "score":   round(good_entry_now_s, 1) if good_entry_now_s is not None else None,
            "verdict": _verdict_word(good_entry_now_s),
            "explain": "Risk score + Valuation Comfort (is the price reasonable AND not parabolic?).",
        },
    }


# ═════════════════════════════════════════════════════════════════════════
# TOP-LEVEL ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════

def get_positioning_intelligence(ticker: str, sector: str = "", region: str = "US") -> dict:
    """Compute the full 3-layer positioning intelligence for a ticker."""
    cache_key = f"{ticker.strip().upper()}:{(sector or '').lower()}:{region.upper()}"
    now = time.time()
    with _pi_lock:
        cached = _pi_cache.get(cache_key)
        if cached and (now - cached[0]) < _CACHE_TTL:
            return cached[1]

    # Layer 1 + 2
    market_regime = calc_market_regime(region)
    sector_flow = calc_sector_flow(sector, region)

    # Layer 3 — stock 4D
    yf_sym = ticker if region.upper() == "US" else f"{ticker}.NS"
    stock_hist = _safe_history(yf_sym, period="1y")

    sector_etf_sym = sector_flow.get("etf_symbol") if sector_flow.get("success") else None
    sector_hist = None
    if sector_etf_sym:
        sector_hist = _safe_history(sector_etf_sym, period="60d")

    stock_info_data = _safe_info_and_insiders(yf_sym)
    info = stock_info_data["info"] if stock_info_data else {}
    insider_tx = stock_info_data["insider_tx"] if stock_info_data else None
    financials = stock_info_data["financials"] if stock_info_data else None

    # Parse insider transactions
    insider_buys = 0
    insider_sells = 0
    if insider_tx is not None:
        try:
            if hasattr(insider_tx, "iterrows"):
                for _, row in insider_tx.head(30).iterrows():
                    tx_type = str(row.get("Transaction", "") or row.get("Action", "")).lower()
                    if "buy" in tx_type or "purchase" in tx_type:
                        insider_buys += 1
                    elif "sale" in tx_type or "sell" in tx_type:
                        insider_sells += 1
        except Exception:
            pass

    # Compute the four dimensions
    flow      = score_flow_strength(stock_hist, sector_hist, insider_buys, insider_sells)
    valuation = score_valuation_comfort(info, financials)
    quality   = score_business_quality(info, financials)
    risk      = score_risk_crowding(stock_hist, info, insider_buys, insider_sells)

    synthesis = _synthesize_verdict(flow, valuation, quality, risk)

    # Confidence
    total_comps = (
        flow.get("components_present", 0)
        + valuation.get("components_present", 0)
        + quality.get("components_present", 0)
        + risk.get("components_present", 0)
    )
    # Max components = 4 + 4 + 5 + 5 = 18
    if total_comps >= 14:
        confidence = "high"
    elif total_comps >= 8:
        confidence = "medium"
    else:
        confidence = "low"

    result = {
        "success":       True,
        "ticker":        ticker.strip().upper(),
        "sector":        sector,
        "region":        region.upper(),
        "section":       "positioning_intelligence",
        "market_regime": market_regime,
        "sector_flow":   sector_flow,
        "stock_4d": {
            "flow":      flow,
            "valuation": valuation,
            "quality":   quality,
            "risk":      risk,
        },
        "synthesis":     synthesis,
        "confidence":    confidence,
        "components_present_total": total_comps,
        "data_sources":  {"market": "yfinance"},
        "partial_data":  confidence != "high",
    }

    with _pi_lock:
        _pi_cache[cache_key] = (now, result)
    return result
