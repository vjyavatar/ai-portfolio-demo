"""
smart_money_v3.py — Institutional-grade Smart Money Scanner (Expanded Edition).

EXPANDED IMPLEMENTATION — covers everything achievable with free data:

  Layer 1 — Smart Money Detection
       - Insider buying (12-month aggregate)
       - Unusual volume vs float (RVOL)         [NEW]
       - Float tightening detection (short cover)[NEW]
       - Low retail ownership measurement       [NEW]
       - Institutional ownership level

  Layer 2 — Bottleneck Engine (expanded catalog)
       - HBM, AI GPU, Custom Silicon, Advanced Packaging, EUV
       - Datacenter Power, Cooling              [NEW theme]
       - Grid + Gas Turbines, Grid Construction
       - Transformers / Switchgear              [NEW theme]
       - Rare Earths / Critical Minerals        [NEW theme]
       - Nuclear Baseload + SMR
       - Photonics, Optical
       - Defense (multiple sub-themes)
       - GLP-1, Uranium
       - India Capex themes

  Layer 3 — Before Breakout Engine
       - Hyperscaler exposure (business summary scan)  [NEW]
       - Government contract exposure (text scan)      [NEW]
       - AI exposure detection                         [NEW]
       - Revenue acceleration (YoY)                    [NEW]
       - Capacity expansion signal (capex)             [NEW]

  Transparency
       - Score components breakdown
       - Week-over-week score Δ                        [NEW]
       - "What changed this week"                      [NEW]
       - Signals fired list                            [NEW]

Endpoints:
  GET /api/smv3              -> ranked scan
  GET /api/smv3/bottlenecks  -> catalog
  GET /api/smv3/snapshot     -> save current as weekly baseline
"""

import time
import json
import logging
import os
from pathlib import Path
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
# BOTTLENECK ENGINE — Expanded catalog: Cooling, Transformers, Rare Earths added
# ═══════════════════════════════════════════════════════════════════════════
_BOTTLENECKS = {
    # AI Memory / Compute
    "MU":   {"theme": "HBM Memory",            "severity": 95, "why": "HBM3e supply oversold through 2027; pricing power exploding"},
    "NVDA": {"theme": "AI GPU Capacity",       "severity": 88, "why": "H200/B200 demand exceeds TSMC CoWoS capacity"},
    "AMD":  {"theme": "AI GPU Capacity",       "severity": 72, "why": "MI300X gaining hyperscaler adoption; CoWoS-constrained"},
    "AVGO": {"theme": "Custom AI Silicon",     "severity": 88, "why": "Hyperscaler custom ASIC demand + networking dominance"},
    "ANET": {"theme": "AI Networking",         "severity": 78, "why": "Switching fabric for hyperscaler AI buildouts"},
    "MRVL": {"theme": "Custom AI Silicon",     "severity": 75, "why": "AWS Trainium2 design wins + DCI optical"},

    # Semi Equipment / Advanced Packaging
    "AMAT": {"theme": "Advanced Packaging",    "severity": 82, "why": "CoWoS + HBM stacking equipment monopoly"},
    "LRCX": {"theme": "Advanced Packaging",    "severity": 80, "why": "Etch tools critical to HBM stacking"},
    "KLAC": {"theme": "Advanced Packaging",    "severity": 75, "why": "Inspection required at every HBM layer"},
    "ASML": {"theme": "EUV Lithography",       "severity": 92, "why": "Only EUV supplier; multi-year backlog for High-NA"},
    "ACLS": {"theme": "Ion Implant",           "severity": 70, "why": "Ion-implant tools for advanced nodes + SiC"},
    "AEHR": {"theme": "SiC Test Capacity",     "severity": 78, "why": "Silicon-carbide burn-in monopoly position"},

    # Power Infra
    "VRT":  {"theme": "Datacenter Power+Cool", "severity": 88, "why": "Liquid cooling + power distribution for AI racks (both bottlenecks)"},
    "ETN":  {"theme": "Electrification+Switchgear", "severity": 84, "why": "Datacenter electrical + switchgear multi-year backlog"},
    "GEV":  {"theme": "Grid + Gas Turbines",   "severity": 90, "why": "Gas turbine backlog stretched into 2028"},
    "PWR":  {"theme": "Grid Construction",     "severity": 80, "why": "Transmission line construction shortage"},
    "MYRG": {"theme": "Grid Construction",     "severity": 75, "why": "Transmission utility contractor benefiting from grid capex"},
    "PRIM": {"theme": "Grid Construction",     "severity": 72, "why": "Energy infra construction tightness"},
    "MOD":  {"theme": "Datacenter Cooling",    "severity": 78, "why": "Modular datacenter + cooling solutions"},

    # Transformers / Switchgear (NEW theme)
    "HUBB": {"theme": "Transformers/Switchgear","severity": 80, "why": "Power transformer backlog 100+ weeks; grid investment cycle"},
    "POWL": {"theme": "Transformers/Switchgear","severity": 75, "why": "Electrical infrastructure backlog at record"},

    # Rare Earths / Critical Minerals (NEW theme)
    "MP":   {"theme": "Rare Earths",           "severity": 78, "why": "Western rare-earth supply security premium; DoD support"},
    "USAR": {"theme": "Rare Earths",           "severity": 72, "why": "Domestic rare-earth processor"},
    "TROX": {"theme": "Critical Minerals",     "severity": 65, "why": "Titanium dioxide critical-supply position"},
    "LAC":  {"theme": "Lithium Supply",        "severity": 60, "why": "US lithium project near production"},

    # Nuclear
    "CEG":  {"theme": "Nuclear Baseload",      "severity": 85, "why": "Hyperscaler PPAs for nuclear power"},
    "VST":  {"theme": "Nuclear Baseload",      "severity": 80, "why": "Texas grid demand + nuclear assets"},
    "BWXT": {"theme": "Nuclear Components",    "severity": 78, "why": "Navy nuclear + SMR opportunity"},
    "SMR":  {"theme": "Small Modular Reactor", "severity": 70, "why": "Early SMR deployment plays"},
    "OKLO": {"theme": "Small Modular Reactor", "severity": 68, "why": "Advanced reactor design firm; AI datacenter demand"},
    "LEU":  {"theme": "Nuclear Fuel",          "severity": 72, "why": "HALEU enrichment for advanced reactors"},

    # Photonics / Optical
    "COHR": {"theme": "Optical Networking",    "severity": 75, "why": "1.6T optical transceivers for AI clusters"},
    "POET": {"theme": "Silicon Photonics",     "severity": 70, "why": "Early-stage but addresses real AI interconnect bottleneck"},
    "LITE": {"theme": "Optical Components",    "severity": 72, "why": "Datacom optical demand acceleration"},
    "FN":   {"theme": "Optical Components",    "severity": 70, "why": "Coherent optical contract manufacturer"},

    # Defense
    "LMT":  {"theme": "Munitions Restock",     "severity": 72, "why": "Allied munitions production backlog"},
    "NOC":  {"theme": "Strategic Deterrent",   "severity": 72, "why": "B-21, Sentinel ICBM programs"},
    "RTX":  {"theme": "Air Defense",           "severity": 70, "why": "Patriot, NASAMS surging demand"},
    "GD":   {"theme": "Submarine Capacity",    "severity": 78, "why": "Virginia/Columbia subs capacity-constrained"},
    "HII":  {"theme": "Submarine Capacity",    "severity": 75, "why": "Sole nuclear-sub builder bottleneck"},
    "PLTR": {"theme": "Defense AI",            "severity": 65, "why": "AIP gaining DoD + commercial adoption"},
    "KTOS": {"theme": "Defense Drones",        "severity": 70, "why": "Unmanned platform development"},

    # Healthcare
    "LLY":  {"theme": "GLP-1 Supply",          "severity": 82, "why": "Mounjaro/Zepbound supply still constrained"},
    "NVO":  {"theme": "GLP-1 Supply",          "severity": 70, "why": "Wegovy supply normalizing but pipeline depth"},
    "VKTX": {"theme": "Next-Gen GLP-1",        "severity": 60, "why": "Oral GLP-1 + dual-mech candidates"},

    # Energy
    "CCJ":  {"theme": "Uranium Supply",        "severity": 75, "why": "Western utilities + AI datacenter nuclear demand"},
    "UEC":  {"theme": "Uranium Supply",        "severity": 72, "why": "US uranium production ramp"},
    "GE":   {"theme": "Aerospace Engines",     "severity": 75, "why": "LEAP engine backlog at record highs"},

    # India
    "LT.NS":       {"theme": "India Capex",        "severity": 78, "why": "Order book at record; defense + infra capex super-cycle"},
    "RVNL.NS":     {"theme": "Rail Modernization", "severity": 72, "why": "Indian Railways capex super-cycle"},
    "BHEL.NS":     {"theme": "Thermal Power Capex","severity": 70, "why": "India coal capex restart"},
    "RECLTD.NS":   {"theme": "Power Sector Lending","severity": 68,"why": "Power capex financing leader"},
    "BHARTIARTL.NS":{"theme": "5G Capex Cycle",    "severity": 62, "why": "5G rollout + tariff hikes"},
    "POWERGRID.NS":{"theme": "Transmission Capex", "severity": 70, "why": "India transmission monopoly + renewables grid"},
}


def _get_bottleneck(ticker: str) -> Optional[dict]:
    if ticker in _BOTTLENECKS:
        return _BOTTLENECKS[ticker]
    base = ticker.replace(".NS", "")
    return _BOTTLENECKS.get(base)


# ═══════════════════════════════════════════════════════════════════════════
# LAYER 3 — Before-Breakout text scanner (free, deterministic)
# ═══════════════════════════════════════════════════════════════════════════
_HYPERSCALER_KEYWORDS = [
    "amazon web services", "aws", "microsoft azure", "azure", "google cloud",
    "gcp", "hyperscale", "hyperscaler", "meta platforms", "oracle cloud",
    "cloud provider", "hyper-scale",
]
_GOVERNMENT_KEYWORDS = [
    "department of defense", "dod", "u.s. department", "federal government",
    "pentagon", "darpa", "nasa", "department of energy", "doe contract",
    "government contract", "military contract", "federal contract",
    "department of homeland", "ndaa", "ministry of defence",
]
_AI_KEYWORDS = [
    "artificial intelligence", "machine learning", "generative ai",
    "large language model", "llm", "neural network", "deep learning",
    "ai accelerator", "ai training", "ai inference", "ai infrastructure",
    "ai datacenter", "ai workload",
]


def _scan_business_summary(summary: str) -> dict:
    if not summary or not isinstance(summary, str):
        return {"hyperscaler": 0, "government": 0, "ai": 0,
                "hyperscaler_mentions": [], "government_mentions": [], "ai_mentions": []}
    text = summary.lower()
    hyper_hits = [k for k in _HYPERSCALER_KEYWORDS if k in text]
    gov_hits = [k for k in _GOVERNMENT_KEYWORDS if k in text]
    ai_hits = [k for k in _AI_KEYWORDS if k in text]
    return {
        "hyperscaler": len(hyper_hits),
        "government": len(gov_hits),
        "ai": len(ai_hits),
        "hyperscaler_mentions": hyper_hits[:3],
        "government_mentions": gov_hits[:3],
        "ai_mentions": ai_hits[:3],
    }


# ═══════════════════════════════════════════════════════════════════════════
# SNAPSHOT STORE — JSON on disk
# ═══════════════════════════════════════════════════════════════════════════
_SNAPSHOT_DIR = Path(os.environ.get("SMV3_SNAPSHOT_DIR", "/tmp/smv3_snapshots"))
_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)


def _snapshot_path(region: str, mcap: str) -> Path:
    return _SNAPSHOT_DIR / f"snapshot_{region}_{mcap}.json"


def _load_last_snapshot(region: str, mcap: str) -> dict:
    p = _snapshot_path(region, mcap)
    if not p.exists():
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"snapshot load failed: {e}")
        return {}


def _save_snapshot(region: str, mcap: str, results: list):
    snap = {
        r["ticker"]: {
            "score": r["smart_money_score"],
            "components": r.get("score_components", {}),
            "bottleneck_severity": r.get("bottleneck_severity", 0),
            "ts": datetime.utcnow().isoformat(),
        }
        for r in results
    }
    try:
        with open(_snapshot_path(region, mcap), "w") as f:
            json.dump(snap, f)
    except Exception as e:
        logger.warning(f"snapshot save failed: {e}")


# ═══════════════════════════════════════════════════════════════════════════
_cache: dict = {}
_TTL = 4 * 3600


def _compute(ticker: str, last_snapshot: dict) -> Optional[dict]:
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
        capex = info.get("totalCashFromInvestingActivities") or 0

        inst_pct = info.get("heldPercentInstitutions") or 0
        insider_pct = info.get("heldPercentInsiders") or 0
        float_shares = info.get("floatShares") or 0
        shares_short = info.get("sharesShort") or 0
        shares_short_prior = info.get("sharesShortPriorMonth") or 0
        short_pct_float = (shares_short / float_shares * 100) if float_shares else 0
        avg_vol_10d = info.get("averageDailyVolume10Day") or 0
        avg_vol_3m = info.get("averageVolume") or 0

        # NEW signals
        rvol = (avg_vol_10d / avg_vol_3m) if avg_vol_3m > 0 else 1.0
        unusual_volume = rvol > 1.3

        short_delta_pct = 0
        if shares_short_prior > 0:
            short_delta_pct = ((shares_short - shares_short_prior) / shares_short_prior) * 100

        # Insider activity
        insider_net = 0.0
        insider_buy_dollars = 0.0
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
                insider_buy_dollars = buy_v
                if buy_v + sell_v > 0:
                    insider_net = max(-1, min(1, (buy_v - sell_v) / (buy_v + sell_v)))
        except Exception:
            pass

        retail_pct = max(0, 1 - inst_pct - insider_pct)
        low_retail = retail_pct < 0.30

        # Layer 3 scan
        business_scan = _scan_business_summary(info.get("longBusinessSummary", ""))
        capacity_expansion = capex < -100_000_000

        bottleneck = _get_bottleneck(ticker)

        # ─── SCORING ───
        signals_fired = []

        # 30% Accumulation
        accum = 50.0
        if 0.40 < inst_pct < 0.85:
            accum += 15
            signals_fired.append("inst_ownership_sweet_spot")
        elif inst_pct >= 0.85:
            accum += 8
            signals_fired.append("inst_ownership_crowded")

        accum += insider_net * 20
        if insider_net > 0.3:
            signals_fired.append("insider_net_buying")
        elif insider_net < -0.3:
            signals_fired.append("insider_net_selling")

        if rec is not None:
            if rec <= 1.8:
                accum += 15
                signals_fired.append("strong_buy_consensus")
            elif rec <= 2.4:
                accum += 8
            elif rec >= 3.6:
                accum -= 15
                signals_fired.append("sell_consensus")
            elif rec >= 3.0:
                accum -= 8

        if unusual_volume:
            accum += 8
            signals_fired.append(f"unusual_volume_{rvol:.2f}x")

        if low_retail and inst_pct > 0.50:
            accum += 5
            signals_fired.append("low_retail_high_institutional")

        if short_delta_pct < -10:
            accum += 5
            signals_fired.append(f"shorts_covering_{abs(short_delta_pct):.0f}pct")

        accum = max(0, min(100, accum))

        # 25% Bottleneck
        btl = bottleneck["severity"] if bottleneck else 35.0
        if bottleneck:
            signals_fired.append(f"bottleneck_{bottleneck['theme'][:24]}")

        # 20% Inflection
        inflx = 50.0
        if rev_growth > 0.30:
            inflx += 25; signals_fired.append("revenue_30pct_plus")
        elif rev_growth > 0.15:
            inflx += 15; signals_fired.append("revenue_15pct_plus")
        elif rev_growth > 0.05:
            inflx += 5
        elif rev_growth < -0.05:
            inflx -= 15; signals_fired.append("revenue_declining")

        if earn_growth > 0.50:
            inflx += 15; signals_fired.append("earnings_50pct_plus")
        elif earn_growth > 0.20:
            inflx += 8
        elif earn_growth < -0.10:
            inflx -= 10

        if gross_margin > 0.50:
            inflx += 5; signals_fired.append("high_gross_margin")
        if profit_margin > 0.20:
            inflx += 5
        if capacity_expansion:
            inflx += 5; signals_fired.append("capacity_expansion_capex")

        inflx = max(0, min(100, inflx))

        # 15% Relative Strength
        rs = 50.0
        if price_vs_sma200 > 20:
            rs += 20; signals_fired.append("trend_strong_above_sma200")
        elif price_vs_sma200 > 10:
            rs += 12
        elif price_vs_sma200 > 0:
            rs += 5
        elif price_vs_sma200 < -10:
            rs -= 15; signals_fired.append("below_sma200")
        if pct_52w > 80:
            rs += 8; signals_fired.append("near_52w_high")
        elif pct_52w < 30:
            rs -= 8; signals_fired.append("near_52w_low")
        rs = max(0, min(100, rs))

        # 10% Narrative (now includes business-summary)
        narr = 50.0
        if bottleneck:
            narr += 30
        if business_scan["hyperscaler"] >= 1:
            narr += 10
            signals_fired.append(f"hyperscaler_exposure_{business_scan['hyperscaler']}")
        if business_scan["government"] >= 1:
            narr += 8
            signals_fired.append(f"government_exposure_{business_scan['government']}")
        if business_scan["ai"] >= 2:
            narr += 8
            signals_fired.append(f"ai_exposure_{business_scan['ai']}")
        if rec and rec <= 2.0:
            narr += 5
        narr = min(100, narr)

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

        if score >= 85:   conviction = 5
        elif score >= 72: conviction = 4
        elif score >= 60: conviction = 3
        elif score >= 45: conviction = 2
        else:              conviction = 1

        squeeze = "Extreme" if short_pct_float > 20 else "Medium" if short_pct_float > 10 else "Low"

        if score >= 75:   action = "STRONG BUY"
        elif score >= 60: action = "BUY"
        elif score >= 45: action = "HOLD"
        elif score >= 30: action = "TRIM"
        else:              action = "AVOID"

        # WHY NOW
        why_parts = []
        if bottleneck:
            why_parts.append(bottleneck["why"])
        else:
            if rev_growth > 0.20:
                why_parts.append(f"Revenue +{rev_growth*100:.0f}%")
            if insider_net > 0.3:
                why_parts.append("insiders net buying")
            if business_scan["hyperscaler"] >= 1:
                why_parts.append("hyperscaler exposure")
            if business_scan["government"] >= 1:
                why_parts.append("government contracts")
            if rec and rec <= 2.0:
                why_parts.append("strong analyst consensus")
            if pct_52w > 85:
                why_parts.append("near 52w highs")
            elif pct_52w < 30:
                why_parts.append("setup near 52w lows")
        why_now = " · ".join(why_parts) if why_parts else "Building base; await catalyst"

        # Week-over-week delta
        prev = last_snapshot.get(ticker, {})
        week_delta = None
        what_changed = []
        if prev:
            prev_score = prev.get("score", score)
            week_delta = round(score - prev_score, 1)
            prev_comps = prev.get("components", {})
            for comp_name, current_val in {
                "accumulation": round(accum, 1),
                "bottleneck": round(btl, 1),
                "inflection": round(inflx, 1),
                "relative_strength": round(rs, 1),
                "narrative": round(narr, 1),
            }.items():
                prev_val = prev_comps.get(comp_name)
                if prev_val is not None:
                    delta = round(current_val - prev_val, 1)
                    if abs(delta) >= 3:
                        sign = "+" if delta > 0 else ""
                        what_changed.append(f"{comp_name} {sign}{delta}")

        return {
            "ticker": ticker,
            "issuer_name": info.get("longName") or info.get("shortName") or ticker,
            "sector": info.get("sector") or "—",
            "industry": info.get("industry") or "—",
            "price": round(px, 2),
            "change_pct": round(change_pct, 2),
            "smart_money_score": score,
            "accumulation": accum_label,
            "stage": stage,
            "bottleneck": bottleneck["theme"] if bottleneck else None,
            "bottleneck_severity": bottleneck["severity"] if bottleneck else 0,
            "conviction": conviction,
            "squeeze": squeeze,
            "why_now": why_now,
            "action": action,
            "week_delta": week_delta,
            "what_changed": what_changed,
            "signals_fired": signals_fired,
            "breakout_signals": {
                "hyperscaler_exposure": business_scan["hyperscaler"],
                "government_exposure": business_scan["government"],
                "ai_exposure": business_scan["ai"],
                "rvol": round(rvol, 2),
                "unusual_volume": unusual_volume,
                "short_change_pct": round(short_delta_pct, 1),
                "shorts_covering": short_delta_pct < -10,
                "capacity_expansion": capacity_expansion,
                "low_retail": low_retail,
            },
            "score_components": {
                "accumulation": round(accum, 1),
                "bottleneck": round(btl, 1),
                "inflection": round(inflx, 1),
                "relative_strength": round(rs, 1),
                "narrative": round(narr, 1),
            },
            "raw": {
                "inst_ownership_pct": round(inst_pct * 100, 1) if inst_pct else None,
                "insider_ownership_pct": round(insider_pct * 100, 1) if insider_pct else None,
                "retail_ownership_pct": round(retail_pct * 100, 1) if retail_pct else None,
                "short_pct_float": round(short_pct_float, 1),
                "insider_net_score": round(insider_net, 2),
                "insider_buy_dollars": int(insider_buy_dollars),
                "rev_growth_pct": round(rev_growth * 100, 1) if rev_growth else 0,
                "earn_growth_pct": round(earn_growth * 100, 1) if earn_growth else 0,
                "gross_margin_pct": round(gross_margin * 100, 1) if gross_margin else 0,
                "price_vs_sma200_pct": round(price_vs_sma200, 1),
                "pct_of_52w_range": round(pct_52w, 0),
                "analyst_rec": round(rec, 2) if rec else None,
                "rvol_10d_vs_3m": round(rvol, 2),
            },
        }
    except Exception as e:
        logger.warning(f"smv3 {ticker}: {e}")
        return None


def attach(app: FastAPI):
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
        last_snapshot = _load_last_snapshot(region, mcap)
        t0 = time.time()
        results = []
        with ThreadPoolExecutor(max_workers=3) as ex:
            futures = {ex.submit(_compute, t, last_snapshot): t for t in universe[:limit]}
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
            "spec_version": "v3.1-expanded",
            "universe_size": len(universe),
            "scanned_count": len(results),
            "results": results,
            "scan_time_sec": round(time.time() - t0, 1),
            "region": region,
            "mcap": mcap,
            "has_snapshot_baseline": bool(last_snapshot),
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

    @app.get("/api/smv3/snapshot")
    def smv3_snapshot(region: str = "US", mcap: str = "large", email: str = ""):
        region = region.upper()
        mcap = mcap.lower()
        umap = _UNIV_US if region == "US" else _UNIV_IN
        universe = umap.get(mcap, [])
        if not universe:
            return {"success": False, "error": f"{mcap}-cap {region} not populated"}
        results = []
        with ThreadPoolExecutor(max_workers=3) as ex:
            futures = {ex.submit(_compute, t, {}): t for t in universe[:75]}
            for f in as_completed(futures):
                try:
                    r = f.result(timeout=60)
                    if r:
                        results.append(r)
                except Exception:
                    pass
        if results:
            _save_snapshot(region, mcap, results)
            return {"success": True, "tickers_saved": len(results),
                    "snapshot_path": str(_snapshot_path(region, mcap))}
        return {"success": False, "error": "No results to snapshot"}
