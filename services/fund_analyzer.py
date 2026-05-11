"""
r63.72.11 — Fund Analyzer (ETFs + Mutual Funds, US + India).

Detects ticker type (stock / ETF / MF) and returns appropriate analytics.

Data sources:
    US ETFs/MFs   → yfinance (info, holdings via funds_data, history)
    India ETFs    → NSE (existing data_sources.py infrastructure)
    India MFs     → AMFI (NAV) + MFAPI.in (holdings + scheme details)

Outputs unified dict with: type, name, returns, expense_ratio, aum, top_holdings,
sector_allocation, benchmark, alpha, beta, sharpe, max_drawdown.

Caching: 30-minute TTL per ticker. Mutual fund holdings change quarterly so
this cache TTL is comfortable.
"""
import threading
import time
import math
import statistics
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

# 30-minute cache for fund details
_fund_cache: Dict[str, tuple] = {}
_cache_lock = threading.Lock()
_CACHE_TTL = 1800

# Common ETF/MF suffixes/patterns for quick classification
_US_ETF_KNOWN = {
    "SPY", "QQQ", "VOO", "VTI", "IVV", "IWM", "DIA", "VEA", "VWO", "AGG",
    "BND", "GLD", "SLV", "TLT", "XLK", "XLF", "XLE", "XLV", "XLI", "XLY",
    "XLP", "XLB", "XLU", "XLRE", "XLC", "ARKK", "ARKW", "ARKG", "ARKF",
    "SOXX", "SMH", "IBIT", "FBTC", "QQQM", "VUG", "VTV", "VYM", "SCHD",
    "TQQQ", "SQQQ", "SOXL", "SOXS", "TSLL", "NVDL", "MSTU", "SNXX", "SNXL",
    "USMV", "MTUM", "QUAL", "SIZE", "VLUE", "VXUS", "VIG", "BNDX", "TIP",
    "HYG", "LQD", "EMB", "VNQ", "EFA", "EEM", "ACWI", "IEFA", "IEMG",
}

_INDIA_ETF_KNOWN = {
    "NIFTYBEES", "BANKBEES", "JUNIORBEES", "GOLDBEES", "LIQUIDBEES",
    "ICICITECH", "ICICIBANK", "ITBEES", "PSUBNKBEES", "PHARMABEES",
    "NIFTYIETF", "BANKIETF", "NV20IETF", "NEXT50IETF", "MOM100",
    "MOM30IETF", "MIDCAPIETF", "SMALLCAP", "AUTOIETF", "NIFTYBETF",
    "DIVOPPBEES", "CPSEETF", "EQUAL50ADD", "MIDCAPETF", "MNC",
    "ALPHA", "ALPHAETF", "MOMENTUM", "QUALITY", "LOWVOL", "VALUE",
    "MAFANG", "HNGSNGBEES", "MAHKTECH", "NASDAQETF",
}


def _safe_float(v, default=0.0) -> float:
    try:
        f = float(v)
        if f != f or f in (float("inf"), float("-inf")):
            return default
        return f
    except (TypeError, ValueError):
        return default


def _is_india_mf_scheme_code(s: str) -> bool:
    """India MF scheme codes are typically 6-digit numbers (e.g. 120586)."""
    return s.isdigit() and 5 <= len(s) <= 7


def detect_ticker_type(ticker: str, region: str = "US") -> str:
    """
    Classify ticker as 'stock' / 'us_etf' / 'india_etf' / 'india_mf' / 'unknown'.
    Fast classification without network calls when possible.
    """
    t = ticker.strip().upper()
    if not t:
        return "unknown"

    # India MF scheme codes are pure digits (e.g., 120586)
    if _is_india_mf_scheme_code(t):
        return "india_mf"

    if region == "IN":
        if t in _INDIA_ETF_KNOWN:
            return "india_etf"
        if "BEES" in t or "ETF" in t or "IETF" in t:
            return "india_etf"
    else:
        if t in _US_ETF_KNOWN:
            return "us_etf"
        # Heuristic: 5-letter mutual fund codes ending in 'X' (e.g. VFIAX, FXAIX)
        if len(t) == 5 and t.endswith("X"):
            return "us_mf"

    return "stock"  # default — caller should fetch and verify


# ─── US ETF / MF via yfinance ────────────────────────────────────────────

def _fetch_us_fund(ticker: str) -> Optional[dict]:
    """Pull ETF/MF data from yfinance. Returns None on failure."""
    try:
        import yfinance as yf
    except ImportError:
        return None

    try:
        t = yf.Ticker(ticker)
        info = {}
        try:
            info = t.info if hasattr(t, "info") else {}
        except Exception:
            pass

        # quote_type tells us "ETF" / "MUTUALFUND" / "EQUITY"
        quote_type = (info or {}).get("quoteType", "").upper()
        is_fund = quote_type in ("ETF", "MUTUALFUND")
        if not is_fund:
            return None  # Not a fund — caller routes to stock flow

        out = {
            "ticker": ticker,
            "type": "us_etf" if quote_type == "ETF" else "us_mf",
            "name": info.get("longName") or info.get("shortName") or ticker,
            "category": info.get("category", ""),
            "family": info.get("fundFamily", ""),
            "expense_ratio": _safe_float(info.get("annualReportExpenseRatio")) * 100,
            "nav": _safe_float(info.get("navPrice") or info.get("regularMarketPrice") or info.get("previousClose")),
            "ytd_return": _safe_float(info.get("ytdReturn")) * 100,
            "three_year_return": _safe_float(info.get("threeYearAverageReturn")) * 100,
            "five_year_return": _safe_float(info.get("fiveYearAverageReturn")) * 100,
            "yield_pct": _safe_float(info.get("yield")) * 100,
            "total_assets": _safe_float(info.get("totalAssets")),
            "beta": _safe_float(info.get("beta3Year") or info.get("beta")),
            "currency": info.get("currency", "USD"),
            "inception": info.get("fundInceptionDate", ""),
            "morningstar_rating": info.get("morningStarOverallRating"),
        }

        # Top holdings — try funds_data
        try:
            fd = t.funds_data if hasattr(t, "funds_data") else None
            if fd:
                # Top holdings (returns DataFrame in newer yfinance)
                try:
                    th = fd.top_holdings
                    if th is not None and not th.empty:
                        holdings = []
                        for idx, row in th.iterrows():
                            holdings.append({
                                "ticker": str(idx),
                                "name": str(row.get("Name") or row.get("name") or idx),
                                "weight": _safe_float(row.get("Holding Percent") or row.get("holdingPercent")) * 100,
                            })
                        out["top_holdings"] = holdings[:10]
                except Exception:
                    pass

                # Sector weights
                try:
                    sw = fd.sector_weightings
                    if sw is not None:
                        # Newer yfinance returns dict-like
                        if hasattr(sw, "items"):
                            sectors = [{"sector": k, "weight": _safe_float(v) * 100} for k, v in sw.items()]
                            out["sectors"] = [s for s in sectors if s["weight"] > 0]
                except Exception:
                    pass

                # Asset classes
                try:
                    aw = fd.asset_classes
                    if aw is not None and hasattr(aw, "items"):
                        out["asset_classes"] = [{"class": k, "weight": _safe_float(v) * 100} for k, v in aw.items()]
                except Exception:
                    pass
        except Exception:
            pass

        # Fallback: build sector list from info if funds_data didn't work
        if "sectors" not in out:
            sectors = []
            sector_fields = [
                ("Technology", "sectorWeightings.realestate"),  # placeholder, real fields below
            ]
            # yfinance also exposes sector weights via individual numeric fields
            sector_map = {
                "realestate": "Real Estate", "consumer_cyclical": "Consumer Cyclical",
                "basic_materials": "Basic Materials", "consumer_defensive": "Consumer Defensive",
                "technology": "Technology", "communication_services": "Communication Services",
                "financial_services": "Financial Services", "utilities": "Utilities",
                "industrials": "Industrials", "energy": "Energy", "healthcare": "Healthcare",
            }
            for key, label in sector_map.items():
                v = info.get(key)
                if v:
                    sectors.append({"sector": label, "weight": _safe_float(v) * 100})
            if sectors:
                out["sectors"] = sectors

        # Performance computation via price history
        try:
            hist = t.history(period="5y")
            if hist is not None and not hist.empty:
                closes = hist["Close"].tolist()
                if len(closes) > 1:
                    cur = closes[-1]
                    out["price_1y_ago"] = closes[-252] if len(closes) >= 252 else closes[0]
                    out["price_3y_ago"] = closes[-756] if len(closes) >= 756 else closes[0]
                    out["price_5y_ago"] = closes[0]
                    out["one_year_return"] = ((cur / closes[-252]) - 1) * 100 if len(closes) >= 252 else None
                    out["six_month_return"] = ((cur / closes[-126]) - 1) * 100 if len(closes) >= 126 else None
                    out["three_month_return"] = ((cur / closes[-63]) - 1) * 100 if len(closes) >= 63 else None
                    out["one_month_return"] = ((cur / closes[-21]) - 1) * 100 if len(closes) >= 21 else None

                    # Sharpe + max drawdown (using daily returns)
                    rets = [(closes[i] / closes[i-1] - 1) for i in range(1, len(closes))]
                    if rets:
                        mean_ret = statistics.mean(rets) * 252  # annualized
                        std_ret = statistics.pstdev(rets) * math.sqrt(252) if len(rets) > 1 else 0
                        out["volatility_annual"] = std_ret * 100
                        risk_free = 0.04  # rough US t-bill
                        out["sharpe_ratio"] = (mean_ret - risk_free) / std_ret if std_ret > 0 else 0

                    # Max drawdown from peak
                    peak = closes[0]
                    max_dd = 0
                    for c in closes:
                        if c > peak:
                            peak = c
                        dd = (c - peak) / peak
                        if dd < max_dd:
                            max_dd = dd
                    out["max_drawdown"] = max_dd * 100

                    # Recent close for NAV if not set
                    if not out.get("nav"):
                        out["nav"] = float(cur)
        except Exception:
            pass

        return out
    except Exception:
        return None


# ─── India MF via AMFI + MFAPI.in ────────────────────────────────────────

_amfi_cache: Optional[tuple] = None
_amfi_lock = threading.Lock()


def _fetch_amfi_nav_universe() -> Dict[str, dict]:
    """
    Fetch the AMFI NAV file — daily snapshot of every Indian MF.
    Returns dict {scheme_code: {scheme_name, nav, date, isin_growth}}.
    Cached for 4 hours since AMFI updates ~once per day.
    """
    global _amfi_cache
    with _amfi_lock:
        if _amfi_cache and (time.time() - _amfi_cache[0]) < 14400:
            return _amfi_cache[1]

    try:
        import urllib.request
        req = urllib.request.Request(
            "https://www.amfiindia.com/spages/NAVAll.txt",
            headers={"User-Agent": "Celesys/1.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            text = resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return {}

    schemes = {}
    for line in text.split("\n"):
        parts = [p.strip() for p in line.split(";")]
        if len(parts) < 6:
            continue
        scheme_code = parts[0]
        if not scheme_code.isdigit():
            continue
        try:
            nav = float(parts[4])
        except (ValueError, IndexError):
            continue
        schemes[scheme_code] = {
            "scheme_code": scheme_code,
            "isin_growth": parts[1],
            "isin_div": parts[2] if len(parts) > 2 else "",
            "scheme_name": parts[3],
            "nav": nav,
            "date": parts[5] if len(parts) > 5 else "",
        }

    with _amfi_lock:
        _amfi_cache = (time.time(), schemes)
    return schemes


def _fetch_mfapi_in(scheme_code: str) -> Optional[dict]:
    """
    Fetch India MF history + meta from mfapi.in (free, public).
    Returns: {meta, data (NAV history)}.
    """
    try:
        import urllib.request
        import json
        req = urllib.request.Request(
            f"https://api.mfapi.in/mf/{scheme_code}",
            headers={"User-Agent": "Celesys/1.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _compute_india_mf_returns(history: List[dict]) -> dict:
    """
    Compute trailing returns from MFAPI.in history (list of {date, nav}, most recent first).
    """
    if not history or len(history) < 2:
        return {}

    # Most recent NAV
    try:
        navs = [(h["date"], float(h["nav"])) for h in history if "nav" in h and h["nav"]]
    except (ValueError, KeyError):
        return {}
    if not navs:
        return {}

    current = navs[0][1]
    out = {"current_nav": current}

    # MFAPI returns daily history newest-first
    def _at_index(idx):
        if idx < len(navs):
            return navs[idx][1]
        return None

    # Approx trading-day indices
    targets = {
        "one_month_return": 21,
        "three_month_return": 63,
        "six_month_return": 126,
        "one_year_return": 252,
        "three_year_return": 756,
        "five_year_return": 1260,
    }
    for key, idx in targets.items():
        old = _at_index(idx)
        if old and old > 0:
            out[key] = ((current / old) - 1) * 100

    # Volatility + Sharpe from daily returns
    try:
        rets = []
        for i in range(1, min(len(navs), 756)):
            if navs[i][1] > 0:
                rets.append((navs[i-1][1] / navs[i][1]) - 1)
        if rets:
            mean_ret = statistics.mean(rets) * 252
            std_ret = statistics.pstdev(rets) * math.sqrt(252) if len(rets) > 1 else 0
            out["volatility_annual"] = std_ret * 100
            risk_free_in = 0.065  # 10yr GoI yield approx
            out["sharpe_ratio"] = (mean_ret - risk_free_in) / std_ret if std_ret > 0 else 0
    except Exception:
        pass

    # Max drawdown
    try:
        peak = navs[-1][1]  # oldest
        max_dd = 0
        for _, n in reversed(navs):
            if n > peak:
                peak = n
            dd = (n - peak) / peak
            if dd < max_dd:
                max_dd = dd
        out["max_drawdown"] = max_dd * 100
    except Exception:
        pass

    return out


def _fetch_india_mf(scheme_code_or_name: str) -> Optional[dict]:
    """Pull India MF data. Input is either AMFI scheme code OR scheme name."""
    universe = _fetch_amfi_nav_universe()
    if not universe:
        return None

    # Resolve scheme code
    scheme = None
    s = scheme_code_or_name.strip()
    if s.isdigit() and s in universe:
        scheme = universe[s]
    else:
        # Name-based lookup (case-insensitive substring)
        s_upper = s.upper()
        for code, meta in universe.items():
            if s_upper in meta["scheme_name"].upper():
                scheme = meta
                break
        if not scheme:
            return None

    out = {
        "ticker": scheme["scheme_code"],
        "type": "india_mf",
        "name": scheme["scheme_name"],
        "scheme_code": scheme["scheme_code"],
        "isin": scheme.get("isin_growth", ""),
        "nav": scheme["nav"],
        "nav_date": scheme.get("date", ""),
        "currency": "INR",
    }

    # Detail + history from MFAPI.in
    mfapi = _fetch_mfapi_in(scheme["scheme_code"])
    if mfapi:
        meta = mfapi.get("meta", {}) or {}
        out["family"] = meta.get("fund_house", "")
        out["category"] = meta.get("scheme_category", "")
        out["scheme_type"] = meta.get("scheme_type", "")
        history = mfapi.get("data", []) or []
        if history:
            out.update(_compute_india_mf_returns(history))

    return out


# ─── India ETF via NSE ───────────────────────────────────────────────────

def _fetch_india_etf(ticker: str) -> Optional[dict]:
    """Pull India ETF data via existing NSE infrastructure."""
    try:
        from data_sources import _nse_quote
        info = _nse_quote(ticker, "IN")
        if not info:
            return None
        out = {
            "ticker": ticker,
            "type": "india_etf",
            "name": info.get("longName") or info.get("shortName") or ticker,
            "nav": _safe_float(info.get("currentPrice")),
            "prev_close": _safe_float(info.get("previousClose")),
            "day_high": _safe_float(info.get("dayHigh")),
            "day_low": _safe_float(info.get("dayLow")),
            "fifty_two_week_high": _safe_float(info.get("fiftyTwoWeekHigh")),
            "fifty_two_week_low": _safe_float(info.get("fiftyTwoWeekLow")),
            "volume": _safe_float(info.get("volume")),
            "currency": "INR",
        }
        return out
    except Exception:
        return None


# ─── PUBLIC TOP-LEVEL ENTRY ──────────────────────────────────────────────

def analyze_fund(ticker: str, region: str = "US") -> Optional[dict]:
    """
    Detect and analyze a fund (ETF or MF). Returns None if input is NOT a fund
    — caller should route to regular stock DD flow.

    Cached for 30 minutes per (ticker, region) pair.
    """
    t = ticker.strip().upper()
    if not t:
        return None

    cache_key = f"{region}:{t}"
    now = time.time()
    with _cache_lock:
        cached = _fund_cache.get(cache_key)
        if cached and (now - cached[0]) < _CACHE_TTL:
            return cached[1]

    result = None
    ticker_type = detect_ticker_type(t, region)

    if region == "IN":
        # Try MF first (numeric scheme codes are unambiguous)
        if ticker_type == "india_mf" or t.isdigit():
            result = _fetch_india_mf(t)
        # Then try as ETF / NSE-listed
        if not result:
            result = _fetch_india_etf(t)
        # Last attempt — name search across AMFI universe
        if not result:
            result = _fetch_india_mf(t)
    else:
        # US: try yfinance first; it returns None for non-funds (stocks)
        result = _fetch_us_fund(t)

    with _cache_lock:
        _fund_cache[cache_key] = (now, result)
    return result


def search_india_funds(query: str, limit: int = 20) -> List[dict]:
    """Search India MFs by name (substring match across full AMFI universe)."""
    if not query or len(query) < 2:
        return []
    universe = _fetch_amfi_nav_universe()
    q = query.upper()
    out = []
    for code, meta in universe.items():
        if q in meta["scheme_name"].upper():
            out.append({
                "scheme_code": code,
                "name": meta["scheme_name"],
                "nav": meta["nav"],
            })
            if len(out) >= limit:
                break
    return out


# ─── PHASE 2: COMPARISON + LENS RANKING ──────────────────────────────────

def compute_holdings_overlap(fund_a: dict, fund_b: dict) -> dict:
    """
    Calculate overlap between two funds' top holdings.
    Returns: {overlap_pct, common_tickers, total_weight_a, total_weight_b}.
    """
    h_a = fund_a.get("top_holdings") or []
    h_b = fund_b.get("top_holdings") or []
    if not h_a or not h_b:
        return {"overlap_pct": None, "common_tickers": [], "note": "Holdings data unavailable"}

    a_map = {h["ticker"]: h["weight"] for h in h_a}
    b_map = {h["ticker"]: h["weight"] for h in h_b}
    common = set(a_map.keys()) & set(b_map.keys())

    if not common:
        return {"overlap_pct": 0, "common_tickers": [], "total_overlap_weight": 0}

    # Overlap weight = sum of min(weight_a, weight_b) for common tickers
    overlap_weight = sum(min(a_map[t], b_map[t]) for t in common)
    total_a = sum(a_map.values())
    total_b = sum(b_map.values())
    # Overlap pct = 2 * overlap_weight / (total_a + total_b) — symmetric
    overlap_pct = 2 * overlap_weight / (total_a + total_b) * 100 if (total_a + total_b) > 0 else 0

    common_list = sorted(
        [{"ticker": t, "weight_a": a_map[t], "weight_b": b_map[t]} for t in common],
        key=lambda x: min(x["weight_a"], x["weight_b"]),
        reverse=True
    )
    return {
        "overlap_pct": round(overlap_pct, 1),
        "common_tickers": common_list[:15],
        "total_overlap_weight": round(overlap_weight, 1),
    }


def compute_fund_lens_score(fund: dict) -> dict:
    """
    Phase 2 lens-style scoring for an ETF/MF — 4 dimensions, 0-100 each.
    
    - COST_EFFICIENCY: lower expense ratio = higher score
    - RISK_ADJUSTED:   Sharpe ratio + volatility
    - PERFORMANCE:     1y/3y/5y returns vs. peers
    - SIZE_QUALITY:    AUM (larger = more reliable, lower expense impact)
    
    Returns dict with each subscore + composite + verdict band.
    """
    out = {
        "cost_efficiency": None,
        "risk_adjusted": None,
        "performance": None,
        "size_quality": None,
        "composite": None,
        "verdict": "INSUFFICIENT DATA",
    }
    n_inputs = 0

    # 1. Cost efficiency (lower expense ratio = better)
    er = fund.get("expense_ratio")
    if er is not None and er > 0:
        # Expense ratio scoring: 0.05% = 100, 0.20% = 80, 0.50% = 50, 1.00%+ = 20
        if er <= 0.05:
            out["cost_efficiency"] = 100
        elif er <= 0.10:
            out["cost_efficiency"] = 90
        elif er <= 0.20:
            out["cost_efficiency"] = 80
        elif er <= 0.50:
            out["cost_efficiency"] = 60
        elif er <= 1.00:
            out["cost_efficiency"] = 35
        else:
            out["cost_efficiency"] = 15
        n_inputs += 1

    # 2. Risk-adjusted (Sharpe ratio)
    sharpe = fund.get("sharpe_ratio")
    if sharpe is not None:
        # Sharpe scoring: 2.0+ = 100, 1.0 = 70, 0.5 = 50, 0 = 30, neg = 10
        if sharpe >= 2.0:
            out["risk_adjusted"] = 100
        elif sharpe >= 1.0:
            out["risk_adjusted"] = 70 + (sharpe - 1.0) * 30
        elif sharpe >= 0.5:
            out["risk_adjusted"] = 50 + (sharpe - 0.5) * 40
        elif sharpe >= 0:
            out["risk_adjusted"] = 30 + sharpe * 40
        else:
            out["risk_adjusted"] = max(0, 30 + sharpe * 30)
        n_inputs += 1

    # 3. Performance (composite of trailing returns)
    perf_scores = []
    for key, weight in [("one_year_return", 0.20), ("three_year_return", 0.40), ("five_year_return", 0.40)]:
        v = fund.get(key)
        if v is not None:
            # Map: 0% → 30, 10% → 60, 20% → 85, 30%+ → 100
            if v >= 30:
                s = 100
            elif v >= 20:
                s = 85 + (v - 20) * 1.5
            elif v >= 10:
                s = 60 + (v - 10) * 2.5
            elif v >= 0:
                s = 30 + v * 3
            else:
                s = max(0, 30 + v * 2)
            perf_scores.append((s, weight))
    if perf_scores:
        total_w = sum(w for _, w in perf_scores)
        out["performance"] = sum(s * w for s, w in perf_scores) / total_w
        n_inputs += 1

    # 4. Size / quality (AUM)
    aum = fund.get("total_assets")
    if aum and aum > 0:
        # $100M = 30, $1B = 60, $10B = 85, $100B+ = 100
        log_aum = math.log10(aum)
        if log_aum >= 11:
            out["size_quality"] = 100
        elif log_aum >= 10:
            out["size_quality"] = 85 + (log_aum - 10) * 15
        elif log_aum >= 9:
            out["size_quality"] = 60 + (log_aum - 9) * 25
        elif log_aum >= 8:
            out["size_quality"] = 30 + (log_aum - 8) * 30
        else:
            out["size_quality"] = max(0, log_aum * 3)
        n_inputs += 1

    # Composite (only if 2+ inputs)
    if n_inputs >= 2:
        weights = {
            "cost_efficiency": 0.25,
            "risk_adjusted": 0.30,
            "performance": 0.30,
            "size_quality": 0.15,
        }
        score_sum = 0.0
        weight_sum = 0.0
        for key, w in weights.items():
            v = out.get(key)
            if v is not None:
                score_sum += v * w
                weight_sum += w
        if weight_sum > 0:
            out["composite"] = round(score_sum / weight_sum, 1)
            # Verdict band
            c = out["composite"]
            if c >= 75 and n_inputs >= 3:
                out["verdict"] = "EXCELLENT"
            elif c >= 60:
                out["verdict"] = "GOOD"
            elif c >= 40:
                out["verdict"] = "FAIR"
            else:
                out["verdict"] = "POOR"

    return out
