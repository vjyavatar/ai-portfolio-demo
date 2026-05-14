"""
smart_money_v3.py — Institutional-grade Smart Money Scanner.

Implements the spec faithfully:
  - 5-column output: Smart Money Score · Accumulation · Stage · Bottleneck · Conviction
  - WHY NOW one-line synthesis per stock
  - Weighted scoring: 30% Accumulation + 25% Bottleneck + 20% Inflection + 15% RS + 10% Narrative
  - Hand-curated bottleneck map (HBM, AI GPU, Power Infra, Photonics, Defense, GLP-1, Uranium)
  - Squeeze Potential signal
  - Stage classification (Early / Expansion / Crowded)
  - 1-5 star Conviction rating

Endpoint: GET /api/smv3?region=US&mcap=large&limit=75

DEPLOYMENT:
  1. Save this file as smart_money_v3.py in the repo root (next to api.py).
  2. Add ONE line near the bottom of api.py (after `app = FastAPI(...)`):
        from smart_money_v3 import attach as _attach_smv3; _attach_smv3(app)
  3. git add smart_money_v3.py api.py
     git commit -m "smart money v3 spec implementation"
     git push origin main

REVERT: if anything breaks, delete the one line + the file, push. Site restored.
"""

import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional

import yfinance as yf
from fastapi import FastAPI

logger = logging.getLogger("smv3")

# ═══════════════════════════════════════════════════════════════════════════
# UNIVERSES
# ═══════════════════════════════════════════════════════════════════════════
_UNIV_US = {
    "large": [
        "AAPL","MSFT","NVDA","GOOGL","AMZN","META","TSLA","AVGO","JPM","WMT",
        "XOM","V","UNH","MA","PG","JNJ","HD","COST","ORCL","BAC","NFLX","KO",
        "CRM","CVX","MRK","TMO","AMD","PEP","ADBE","LIN","CSCO","ACN","MCD",
        "WFC","ABT","DHR","GE","TXN","VZ","DIS","NOW","INTU","AMGN","IBM",
        "QCOM","CAT","GS","UBER","BKNG","AXP","RTX","BLK","PFE","TJX","C",
        "LOW","DE","HON","REGN","MS","BMY","MDT","MU","LRCX","MDLZ","ADI",
        "GILD","TMUS","PANW","KLAC","BA","SO","ICE","NKE",
    ],
    "mid": [
        "MORN","WST","TDY","MANH","DECK","FIX","LII","WSO","SAIA","RPM","EME",
        "FAF","UTHR","ATR","LSTR","CHE","CHRW","WEX","KNX","JBL","SNX","HUBB",
        "DOX","CSL","BRX","AYI","MUSA","ELS","REG","TXRH","AAON","MTH","RYAN",
        "WMS","CASY","BURL","KBR","FND","ENS","UGI",
    ],
    "small": [
        "SXT","UFPI","ESE","WERN","HALO","MGY","PI","HCC","RXO","ASGN","SPSC",
        "HASI","UNFI","SHEN","CALM","STEP","CRC","KLG","OII","WAFD","KFRC",
        "TBBK","TILE","UPBD","CSGS","HCKT","HSII","CAKE","BANC","TRMK","ABM",
        "ARLO","SHAK","BANR","HPP","DLX","NABL",
    ],
    "micro": [
        "AEHR","POET","NVEE","ESSA","ATLC","UFPT","CTKB","PEBK","TBNK","CCB",
        "PFBC","FBNC","HBNC","SRCE","BSRR","WTBA","FCBC","SBT","SMBC","NICK",
        "WMK","BHB","AROW","LARK","ESQ","FCAP","UVSP","SPFI",
    ],
}

_UNIV_IN = {
    "large": [
        "RELIANCE.NS","TCS.NS","HDFCBANK.NS","BHARTIARTL.NS","ICICIBANK.NS",
        "INFY.NS","SBIN.NS","LT.NS","ITC.NS","HINDUNILVR.NS","BAJFINANCE.NS",
        "MARUTI.NS","AXISBANK.NS","KOTAKBANK.NS","HCLTECH.NS","SUNPHARMA.NS",
        "TITAN.NS","ASIANPAINT.NS","ULTRACEMCO.NS","TATAMOTORS.NS","NESTLEIND.NS",
        "WIPRO.NS","POWERGRID.NS","ONGC.NS","NTPC.NS","TATASTEEL.NS","HDFCLIFE.NS",
        "ADANIPORTS.NS","COALINDIA.NS","CIPLA.NS","BAJAJFINSV.NS","JSWSTEEL.NS",
        "INDUSINDBK.NS","TECHM.NS","HINDALCO.NS","ADANIENT.NS","GRASIM.NS",
        "DRREDDY.NS","SBILIFE.NS","BAJAJ-AUTO.NS","BRITANNIA.NS","EICHERMOT.NS",
        "TATACONSUM.NS","DIVISLAB.NS","HEROMOTOCO.NS","APOLLOHOSP.NS","BPCL.NS","TRENT.NS",
    ],
    "mid": [
        "PERSISTENT.NS","POLYCAB.NS","BHARATFORG.NS","CUMMINSIND.NS","TVSMOTOR.NS",
        "COFORGE.NS","MPHASIS.NS","LTIM.NS","DLF.NS","INDHOTEL.NS","TATAPOWER.NS",
        "MOTHERSON.NS","HAVELLS.NS","DABUR.NS","MARICO.NS","PIDILITIND.NS",
        "BANKBARODA.NS","CANBK.NS","FEDERALBNK.NS","RECLTD.NS","JINDALSTEL.NS",
        "SAIL.NS","VEDL.NS","NMDC.NS","BHEL.NS","IRCTC.NS","GAIL.NS","IOC.NS",
        "HPCL.NS","TORNTPHARM.NS","LUPIN.NS","AUROPHARMA.NS",
    ],
    "small": [
        "KPITTECH.NS","CDSL.NS","CAMS.NS","INTELLECT.NS","BLUESTARCO.NS",
        "KAJARIACER.NS","CROMPTON.NS","VOLTAS.NS","JUBLFOOD.NS","TATAELXSI.NS",
        "DEEPAKNTR.NS","BALKRISIND.NS","APOLLOTYRE.NS","ASTRAL.NS","SUPREMEIND.NS",
        "KEI.NS","BIOCON.NS","ALKEM.NS","ABBOTINDIA.NS",
    ],
    "micro": [
        "KAYNES.NS","SYRMA.NS","DODLA.NS","CAPLIPOINT.NS","FINCABLES.NS",
        "RAINBOW.NS","KRSNAA.NS","GLENMARK.NS","TIMKEN.NS","INDIAMART.NS",
        "TANLA.NS","ROUTE.NS","MAPMYINDIA.NS","CYIENT.NS","BSOFT.NS",
        "RAILTEL.NS","RVNL.NS","IRCON.NS",
    ],
}

# ═══════════════════════════════════════════════════════════════════════════
# BOTTLENECK ENGINE — hand-curated supply-constraint catalog
# Edit anytime. Each entry: severity (0-100) + WHY NOW sentence
# ═══════════════════════════════════════════════════════════════════════════
_BOTTLENECKS = {
    # AI Memory / Compute
    "MU":   {"theme": "HBM Memory",            "severity": 95, "why": "HBM3e supply oversold through 2027; pricing power exploding"},
    "NVDA": {"theme": "AI GPU Capacity",       "severity": 88, "why": "H200/B200 demand exceeds TSMC CoWoS capacity"},
    "AMD":  {"theme": "AI GPU Capacity",       "severity": 72, "why": "MI300X gaining hyperscaler adoption; CoWoS-constrained"},
    "AVGO": {"theme": "Custom AI Silicon",     "severity": 88, "why": "Hyperscaler custom ASIC demand + networking dominance"},
    "ANET": {"theme": "AI Networking",         "severity": 78, "why": "Switching fabric for hyperscaler AI buildouts"},
    # Semi Equipment / Advanced Packaging
    "AMAT": {"theme": "Advanced Packaging",    "severity": 82, "why": "CoWoS + HBM stacking equipment monopoly"},
    "LRCX": {"theme": "Advanced Packaging",    "severity": 80, "why": "Etch tools critical to HBM stacking"},
    "KLAC": {"theme": "Advanced Packaging",    "severity": 75, "why": "Inspection required at every HBM layer"},
    "ASML": {"theme": "EUV Lithography",       "severity": 92, "why": "Only EUV supplier; multi-year backlog for High-NA"},
    # Power Infra for AI Datacenters
    "VRT":  {"theme": "Datacenter Power",      "severity": 88, "why": "Liquid cooling + power distribution for AI racks"},
    "ETN":  {"theme": "Electrification",       "severity": 82, "why": "Datacenter electrical equipment multi-year backlog"},
    "GEV":  {"theme": "Grid + Gas Turbines",   "severity": 90, "why": "Gas turbine backlog stretched into 2028"},
    "PWR":  {"theme": "Grid Construction",     "severity": 80, "why": "Transmission line construction shortage"},
    # Nuclear / Baseload
    "CEG":  {"theme": "Nuclear Baseload",      "severity": 85, "why": "Hyperscaler PPAs for nuclear power"},
    "VST":  {"theme": "Nuclear Baseload",      "severity": 80, "why": "Texas grid demand + nuclear assets"},
    "BWXT": {"theme": "Nuclear Components",    "severity": 78, "why": "Navy nuclear + SMR opportunity"},
    # Photonics / Optical
    "COHR": {"theme": "Optical Networking",    "severity": 75, "why": "1.6T optical transceivers for AI clusters"},
    "POET": {"theme": "Silicon Photonics",     "severity": 70, "why": "Early-stage but addresses real AI interconnect bottleneck"},
    "LITE": {"theme": "Optical Components",    "severity": 72, "why": "Datacom optical demand acceleration"},
    # Defense
    "LMT":  {"theme": "Munitions Restock",     "severity": 72, "why": "Allied munitions production backlog"},
    "NOC":  {"theme": "Strategic Deterrent",   "severity": 72, "why": "B-21, Sentinel ICBM programs"},
    "RTX":  {"theme": "Air Defense",           "severity": 70, "why": "Patriot, NASAMS surging demand"},
    "GD":   {"theme": "Submarine Capacity",    "severity": 78, "why": "Virginia/Columbia subs capacity-constrained"},
    "PLTR": {"theme": "Defense AI",            "severity": 65, "why": "AIP gaining DoD + commercial adoption"},
    # Healthcare bottlenecks
    "LLY":  {"theme": "GLP-1 Supply",          "severity": 82, "why": "Mounjaro/Zepbound supply still constrained"},
    # Energy
    "CCJ":  {"theme": "Uranium Supply",        "severity": 75, "why": "Western utilities + AI datacenter nuclear demand"},
    "GE":   {"theme": "Aerospace Engines",     "severity": 75, "why": "LEAP engine backlog at record highs"},

    # India bottlenecks
    "LT.NS":       {"theme": "India Capex",        "severity": 78, "why": "Order book at record; defense + infra capex super-cycle"},
    "RVNL.NS":     {"theme": "Rail Modernization", "severity": 72, "why": "Indian Railways capex super-cycle"},
    "BHEL.NS":     {"theme": "Thermal Power Capex","severity": 70, "why": "India coal capex restart"},
    "RECLTD.NS":   {"theme": "Power Sector Lending","severity": 68,"why": "Power capex financing leader"},
    "BHARTIARTL.NS":{"theme": "5G Capex Cycle",    "severity": 62, "why": "5G rollout + tariff hikes"},
}


def _get_bottleneck(ticker: str) -> Optional[dict]:
    if ticker in _BOTTLENECKS:
        return _BOTTLENECKS[ticker]
    base = ticker.replace(".NS", "")
    return _BOTTLENECKS.get(base)


# ═══════════════════════════════════════════════════════════════════════════
# CACHE (4h TTL, doesn't cache empty results)
# ═══════════════════════════════════════════════════════════════════════════
_cache: dict = {}
_TTL = 4 * 3600


def _compute(ticker: str) -> Optional[dict]:
    """Compute v3 signals for one ticker. Returns None if Yahoo fully fails."""
    try:
        info, yt = {}, None
        for attempt in range(3):
            try:
                yt = yf.Ticker(ticker)
                info = yt.info or {}
                if info.get("currentPrice") or info.get("regularMarketPrice"):
                    break
            except Exception:
                pass
            time.sleep(1.0 * (attempt + 1))
        else:
            return None

        if not yt or not info:
            return None

        px = info.get("currentPrice") or info.get("regularMarketPrice") or 0
        if not px:
            return None
        pc = info.get("previousClose") or px
        change_pct = ((px - pc) / pc * 100) if pc else 0

        # Inputs
        sma200 = info.get("twoHundredDayAverage") or px
        sma50 = info.get("fiftyDayAverage") or px
        hi52 = info.get("fiftyTwoWeekHigh") or px
        lo52 = info.get("fiftyTwoWeekLow") or px
        price_vs_sma200 = ((px - sma200) / sma200 * 100) if sma200 else 0
        pct_52w = ((px - lo52) / (hi52 - lo52) * 100) if hi52 > lo52 else 50
        rec = info.get("recommendationMean")
        rev_growth = info.get("revenueGrowth") or 0
        earn_growth = info.get("earningsGrowth") or 0
        gross_margin = info.get("grossMargins") or 0
        profit_margin = info.get("profitMargins") or 0
        inst_pct = info.get("heldPercentInstitutions") or 0
        float_shares = info.get("floatShares") or 0
        shares_short = info.get("sharesShort") or 0
        short_pct_float = (shares_short / float_shares * 100) if float_shares else 0

        # Insider net flow (last 12 months)
        insider_net = 0.0
        try:
            ins = yt.insider_transactions
            if ins is not None and not ins.empty:
                cutoff = datetime.now() - timedelta(days=365)
                buy_v, sell_v = 0.0, 0.0
                for _, row in ins.iterrows():
                    dt = row.get("Start Date")
                    if dt is None:
                        continue
                    if hasattr(dt, "to_pydatetime"):
                        dt = dt.to_pydatetime()
                    if dt < cutoff:
                        continue
                    txn = str(row.get("Transaction", "")).lower()
                    val = float(row.get("Value") or 0)
                    if "purchase" in txn or "buy" in txn:
                        buy_v += val
                    elif "sale" in txn or "sell" in txn:
                        sell_v += val
                if buy_v + sell_v > 0:
                    insider_net = max(-1, min(1, (buy_v - sell_v) / (buy_v + sell_v)))
        except Exception:
            pass

        bottleneck = _get_bottleneck(ticker)

        # ── SCORING (per spec weights) ──

        # 30% Institutional Accumulation
        accum = 50.0
        if 0.40 < inst_pct < 0.85:
            accum += 15
        elif inst_pct >= 0.85:
            accum += 8
        accum += insider_net * 20
        if rec is not None:
            if rec <= 1.8:
                accum += 15
            elif rec <= 2.4:
                accum += 8
            elif rec >= 3.6:
                accum -= 15
            elif rec >= 3.0:
                accum -= 8
        accum = max(0, min(100, accum))

        # 25% Bottleneck Severity
        btl = bottleneck["severity"] if bottleneck else 35.0

        # 20% Revenue/Margin Inflection
        inflx = 50.0
        if rev_growth > 0.30:
            inflx += 25
        elif rev_growth > 0.15:
            inflx += 15
        elif rev_growth > 0.05:
            inflx += 5
        elif rev_growth < -0.05:
            inflx -= 15
        if earn_growth > 0.50:
            inflx += 15
        elif earn_growth > 0.20:
            inflx += 8
        elif earn_growth < -0.10:
            inflx -= 10
        if gross_margin > 0.50:
            inflx += 5
        if profit_margin > 0.20:
            inflx += 5
        inflx = max(0, min(100, inflx))

        # 15% Relative Strength
        rs = 50.0
        if price_vs_sma200 > 20:
            rs += 20
        elif price_vs_sma200 > 10:
            rs += 12
        elif price_vs_sma200 > 0:
            rs += 5
        elif price_vs_sma200 < -10:
            rs -= 15
        if pct_52w > 80:
            rs += 8
        elif pct_52w < 30:
            rs -= 8
        rs = max(0, min(100, rs))

        # 10% Narrative
        narr = 50.0
        if bottleneck:
            narr += 30
        if rec and rec <= 2.0:
            narr += 10
        narr = min(100, narr)

        # Composite
        score = round(accum * 0.30 + btl * 0.25 + inflx * 0.20 + rs * 0.15 + narr * 0.10, 1)

        # Labels
        accum_label = "Aggressive" if accum >= 70 else "Moderate" if accum >= 55 else "Weak"

        if pct_52w < 50 and price_vs_sma200 < 10 and inflx > 55:
            stage = "Early"
        elif pct_52w > 85 and rs > 75:
            stage = "Crowded"
        elif price_vs_sma200 > 5 and rs > 55:
            stage = "Expansion"
        elif pct_52w < 40:
            stage = "Early"
        else:
            stage = "Expansion"

        if score >= 85:
            conviction = 5
        elif score >= 72:
            conviction = 4
        elif score >= 60:
            conviction = 3
        elif score >= 45:
            conviction = 2
        else:
            conviction = 1

        squeeze = "Extreme" if short_pct_float > 20 else "Medium" if short_pct_float > 10 else "Low"

        if score >= 75:
            action = "STRONG BUY"
        elif score >= 60:
            action = "BUY"
        elif score >= 45:
            action = "HOLD"
        elif score >= 30:
            action = "TRIM"
        else:
            action = "AVOID"

        # WHY NOW synthesis
        why_parts = []
        if bottleneck:
            why_parts.append(bottleneck["why"])
        else:
            if rev_growth > 0.20:
                why_parts.append(f"Revenue +{rev_growth*100:.0f}%")
            if insider_net > 0.3:
                why_parts.append("insiders net buying")
            if rec and rec <= 2.0:
                why_parts.append("strong analyst consensus")
            if pct_52w > 85:
                why_parts.append("near 52w highs on momentum")
            elif pct_52w < 30:
                why_parts.append("setup near 52w lows")
        why_now = " · ".join(why_parts) if why_parts else "Building base; await catalyst confirmation"

        return {
            "ticker": ticker,
            "issuer_name": info.get("longName") or info.get("shortName") or ticker,
            "price": round(px, 2),
            "change_pct": round(change_pct, 2),
            # Spec columns
            "smart_money_score": score,
            "accumulation": accum_label,
            "stage": stage,
            "bottleneck": bottleneck["theme"] if bottleneck else None,
            "bottleneck_severity": bottleneck["severity"] if bottleneck else 0,
            "conviction": conviction,
            "squeeze": squeeze,
            "why_now": why_now,
            "action": action,
            "score_components": {
                "accumulation": round(accum, 1),
                "bottleneck": round(btl, 1),
                "inflection": round(inflx, 1),
                "relative_strength": round(rs, 1),
                "narrative": round(narr, 1),
            },
            "raw": {
                "inst_ownership_pct": round(inst_pct * 100, 1) if inst_pct else None,
                "short_pct_float": round(short_pct_float, 1),
                "insider_net_score": round(insider_net, 2),
                "rev_growth_pct": round(rev_growth * 100, 1) if rev_growth else 0,
                "price_vs_sma200_pct": round(price_vs_sma200, 1),
                "pct_of_52w_range": round(pct_52w, 0),
                "analyst_rec": round(rec, 2) if rec else None,
            },
        }
    except Exception as e:
        logger.warning(f"smv3 {ticker}: {e}")
        return None


def attach(app: FastAPI):
    """Attach v3 endpoints to the FastAPI app."""

    @app.get("/api/smv3")
    def smv3(region: str = "US", mcap: str = "large", email: str = "", limit: int = 75):
        region = (region or "US").upper()
        mcap = (mcap or "large").lower()
        if mcap not in ("large", "mid", "small", "micro"):
            mcap = "large"
        umap = _UNIV_US if region == "US" else _UNIV_IN
        universe = umap.get(mcap, [])
        if not universe:
            return {"success": False, "results": [], "universe_size": 0,
                    "error": f"{mcap}-cap {region} not populated"}

        ck = f"smv3:{region}:{mcap}"
        if ck in _cache and time.time() - _cache[ck]["t"] < _TTL:
            cached = _cache[ck]
            return {**cached["data"], "_cached": True,
                    "_cache_age_sec": int(time.time() - cached["t"])}

        t0 = time.time()
        results = []
        with ThreadPoolExecutor(max_workers=3) as ex:
            futures = {ex.submit(_compute, t): t for t in universe[:limit]}
            for f in as_completed(futures):
                try:
                    r = f.result(timeout=60)
                    if r:
                        results.append(r)
                except Exception:
                    pass
        results.sort(key=lambda r: r.get("smart_money_score", 0), reverse=True)
        payload = {
            "success": True,
            "spec_version": "v3",
            "universe_size": len(universe),
            "scanned_count": len(results),
            "results": results,
            "scan_time_sec": round(time.time() - t0, 1),
            "region": region,
            "mcap": mcap,
        }
        if results:
            _cache[ck] = {"t": time.time(), "data": payload}
        return payload

    @app.get("/api/smv3/bottlenecks")
    def smv3_bottlenecks():
        grouped = defaultdict(list)
        for ticker, data in _BOTTLENECKS.items():
            grouped[data["theme"]].append({
                "ticker": ticker,
                "severity": data["severity"],
                "why": data["why"],
            })
        themes = []
        for name, members in grouped.items():
            avg_sev = sum(m["severity"] for m in members) / len(members)
            themes.append({
                "theme": name,
                "avg_severity": round(avg_sev, 0),
                "stock_count": len(members),
                "stocks": members,
            })
        themes.sort(key=lambda t: t["avg_severity"], reverse=True)
        return {"success": True, "themes": themes, "total_stocks": len(_BOTTLENECKS)}
