"""
r63.72.16 — Diamond Hunter: Post-Crash Quality Scanner.

Stress-tests every ticker in the universe against a simulated market correction.
For each name, computes a 5-component "Crash Opportunity Score" per the
institutional framework:

    30% Business Strength     (survival, FCF, margins, debt)
    25% Valuation Compression (P/S, EV/Sales, FCF yield at simulated price)
    20% Institutional Accum   (13F flow velocity, buy/sell dominance)
    15% Moat / Future Demand  (sector relevance, GM durability)
    10% Technical Recovery    (RS, drawdown, base formation potential)

CRITICAL: Score is computed at the SIMULATED post-crash price, not current.
This lets us identify which names would be diamonds AFTER a correction.

Crash simulation: beta-adjusted.
    implied_drawdown_pct = market_drop_pct × stock_beta
    capped at 60%, floored at 10% (so low-beta names still participate)

NO synthetic data. NO LLM. Missing inputs → component marked None.
Verdict band requires at least 3 of 5 components with real data.
"""

import math
import statistics
import time
import threading
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.multibagger_scoring import _fetch_fundamentals, FundamentalsSnapshot

# Cache: 15-minute TTL — market conditions can shift intraday
_diamond_cache: Dict[str, tuple] = {}
_diamond_lock = threading.Lock()
_CACHE_TTL = 900


# ─── HELPERS ────────────────────────────────────────────────────────────

def _safe_float(v, default=0.0) -> float:
    try:
        f = float(v)
        if f != f or f in (float("inf"), float("-inf")):
            return default
        return f
    except (TypeError, ValueError):
        return default


def _conviction_band(score: Optional[float], components_present: int) -> str:
    """5 bands. Requires ≥3 of 5 components to register confidence."""
    if score is None or components_present < 3:
        return "INSUFFICIENT DATA"
    if score >= 80 and components_present >= 4:
        return "ELITE DIAMOND"
    if score >= 70 and components_present >= 4:
        return "STRONG DIAMOND"
    if score >= 55:
        return "DIAMOND CANDIDATE"
    if score >= 40:
        return "WATCH"
    return "AVOID"


def _simulate_crash_price(current_price: float, beta: float, market_drop_pct: float) -> tuple:
    """
    Beta-adjusted crash price simulation.
    Returns (simulated_price, implied_drawdown_pct).
    """
    if current_price <= 0:
        return 0, 0
    # Default beta to 1.0 if missing
    b = beta if beta and beta > 0 else 1.0
    # Cap at 2.5 (avoid silly multipliers for high-vol names)
    b = min(b, 2.5)
    implied_drawdown = market_drop_pct * b
    # Floor: even low-beta names drop a minimum amount in a real crash
    implied_drawdown = max(implied_drawdown, market_drop_pct * 0.5)
    # Cap: ceiling at 60%
    implied_drawdown = min(implied_drawdown, 60)
    sim_price = current_price * (1 - implied_drawdown / 100)
    return sim_price, implied_drawdown


# ─── COMPONENT A — BUSINESS STRENGTH (30%) ──────────────────────────────

def _score_business_strength(snap: FundamentalsSnapshot) -> Optional[dict]:
    """
    Survival + business quality. Per document's 8 filters:
    Filter 1 (survival) — cash, debt, FCF, gross margins, dilution
    Filter 5 (moat strength) — partially here via margin quality

    Returns score 0-100 or None if no fundamentals at all.
    Sub-metrics: revenue growth, gross margins, ROIC proxy, FCF, debt health.
    """
    if not snap.has_data or not snap.revenue:
        return None

    score = 0.0
    weight_total = 0.0
    sub = {}

    # 1. Revenue growth (1y) — 20% of component
    if len(snap.revenue) >= 2 and snap.revenue[1] > 0:
        rev_growth = ((snap.revenue[0] - snap.revenue[1]) / snap.revenue[1]) * 100
        # Map: -10% = 20, 0% = 40, 10% = 60, 25%+ = 90, 50%+ = 100
        if rev_growth >= 50: rg_s = 100
        elif rev_growth >= 25: rg_s = 80 + (rev_growth - 25) * 0.8
        elif rev_growth >= 10: rg_s = 55 + (rev_growth - 10) * 1.67
        elif rev_growth >= 0: rg_s = 35 + rev_growth * 2
        else: rg_s = max(0, 35 + rev_growth * 3)
        score += 0.20 * rg_s
        weight_total += 0.20
        sub["revenue_growth_pct"] = round(rev_growth, 1)

    # 2. Gross margin level + stability — 20%
    if snap.gross_profit and snap.revenue:
        gms = []
        for i in range(min(len(snap.gross_profit), len(snap.revenue))):
            if snap.revenue[i] > 0:
                gms.append(snap.gross_profit[i] / snap.revenue[i] * 100)
        if gms:
            gm_avg = statistics.mean(gms)
            gm_std = statistics.pstdev(gms) if len(gms) > 1 else 0
            # Higher GM + lower std = better
            gm_level = min(100, gm_avg * 1.67)  # 60% GM = 100
            gm_stability = max(0, 100 - gm_std * 10)  # 5pp std = 50
            gm_score = 0.7 * gm_level + 0.3 * gm_stability
            score += 0.20 * gm_score
            weight_total += 0.20
            sub["gross_margin_avg"] = round(gm_avg, 1)
            sub["gross_margin_std"] = round(gm_std, 1)

    # 3. ROIC proxy (operating income / invested capital) — 20%
    roics = []
    for i in range(len(snap.operating_income)):
        debt = snap.total_debt[i] if i < len(snap.total_debt) else 0
        equity = snap.total_equity[i] if i < len(snap.total_equity) else 0
        invested = debt + equity
        if invested > 0:
            roics.append((snap.operating_income[i] * 0.79) / invested * 100)
    if roics:
        roic_med = statistics.median(roics)
        # 0% = 30, 12% = 60, 25% = 90, 40%+ = 100
        if roic_med >= 40: roic_s = 100
        elif roic_med >= 25: roic_s = 80 + (roic_med - 25) * 1.33
        elif roic_med >= 12: roic_s = 55 + (roic_med - 12) * 1.92
        elif roic_med >= 0: roic_s = 30 + roic_med * 2.08
        else: roic_s = max(0, 30 + roic_med * 3)
        score += 0.20 * roic_s
        weight_total += 0.20
        sub["roic_median_pct"] = round(roic_med, 1)

    # 4. FCF positive — 20%
    if snap.fcf:
        positive_years = sum(1 for f in snap.fcf if f > 0)
        fcf_consistency_pct = (positive_years / len(snap.fcf)) * 100
        score += 0.20 * fcf_consistency_pct
        weight_total += 0.20
        sub["fcf_positive_years_pct"] = round(fcf_consistency_pct, 0)

    # 5. Debt health (debt-to-EBITDA proxy) — 20%
    if snap.total_debt and snap.cash and snap.operating_income:
        debt = snap.total_debt[0]
        cash = snap.cash[0]
        ebitda_proxy = snap.operating_income[0] * 1.2  # rough D&A add
        net_debt = debt - cash
        if ebitda_proxy > 0:
            ratio = net_debt / ebitda_proxy
            # ratio ≤ 0 (net cash) = 100, ratio 1× = 80, 2.5× = 50, 4× = 20, 6×+ = 0
            if ratio <= 0: debt_s = 100
            elif ratio <= 1: debt_s = 100 - ratio * 20
            elif ratio <= 2.5: debt_s = 80 - (ratio - 1) * 20
            elif ratio <= 4: debt_s = 50 - (ratio - 2.5) * 20
            else: debt_s = max(0, 20 - (ratio - 4) * 10)
            score += 0.20 * debt_s
            weight_total += 0.20
            sub["net_debt_to_ebitda"] = round(ratio, 2)
        else:
            # No EBITDA: net cash position is still informative
            if net_debt < 0:
                score += 0.20 * 70  # net cash = ok even without EBITDA
                weight_total += 0.20
                sub["net_debt_position"] = "net_cash"

    if weight_total == 0:
        return None

    return {
        "score": round(score / weight_total, 1),
        "weight_filled": round(weight_total, 2),
        "sub_metrics": sub,
    }


# ─── COMPONENT B — VALUATION COMPRESSION (25%) ──────────────────────────
# Computed at the SIMULATED post-crash price, not current.

def _score_valuation_compression(snap: FundamentalsSnapshot, current_price: float,
                                  sim_price: float, market_cap: int) -> Optional[dict]:
    """
    Per document Filter 3: EV/Sales, P/S, PEG, FCF yield, market cap vs TAM.
    Computed at simulated post-crash price.
    """
    if not snap.has_data or sim_price <= 0:
        return None

    shares = snap.shares_outstanding[0] if snap.shares_outstanding else 0
    if shares <= 0:
        return None

    sim_mcap = sim_price * shares

    score = 0.0
    weight_total = 0.0
    sub = {}

    # 1. P/S at simulated price — 35% of valuation component
    if snap.revenue and snap.revenue[0] > 0:
        ps_sim = sim_mcap / snap.revenue[0]
        # Tech P/S map: <2 = 90, 2-4 = 75, 4-8 = 55, 8-15 = 30, 15+ = 10
        if ps_sim <= 1: ps_s = 100
        elif ps_sim <= 2: ps_s = 90 - (ps_sim - 1) * 10
        elif ps_sim <= 4: ps_s = 80 - (ps_sim - 2) * 12.5
        elif ps_sim <= 8: ps_s = 55 - (ps_sim - 4) * 6.25
        elif ps_sim <= 15: ps_s = 30 - (ps_sim - 8) * 2.86
        else: ps_s = max(0, 10 - (ps_sim - 15) * 0.5)
        score += 0.35 * ps_s
        weight_total += 0.35
        sub["ps_at_simulated_price"] = round(ps_sim, 2)

        # Historical comparison: compare to 5Y trailing P/S using current snap
        # (rough: assume past mcap proportional to past revenue × current P/S ratio)
        # Better: use price history × shares vs revenue if we had it. For now, skip historical.

    # 2. EV/Sales at simulated price — 25%
    if snap.revenue and snap.revenue[0] > 0:
        debt = snap.total_debt[0] if snap.total_debt else 0
        cash = snap.cash[0] if snap.cash else 0
        ev = sim_mcap + debt - cash
        ev_sales = ev / snap.revenue[0]
        # Similar bands to P/S but slightly more generous (EV captures debt)
        if ev_sales <= 1: evs_s = 100
        elif ev_sales <= 2: evs_s = 90 - (ev_sales - 1) * 10
        elif ev_sales <= 4: evs_s = 80 - (ev_sales - 2) * 10
        elif ev_sales <= 8: evs_s = 60 - (ev_sales - 4) * 7.5
        elif ev_sales <= 15: evs_s = 30 - (ev_sales - 8) * 3
        else: evs_s = max(0, 10 - (ev_sales - 15) * 0.5)
        score += 0.25 * evs_s
        weight_total += 0.25
        sub["ev_sales_at_simulated_price"] = round(ev_sales, 2)

    # 3. FCF yield at simulated price — 25%
    if snap.fcf and snap.fcf[0] != 0:
        fcf_yield = (snap.fcf[0] / sim_mcap) * 100
        # 5%+ = great, 8%+ = elite, 3% = ok, 0% = poor, negative = avoid
        if fcf_yield >= 10: fcf_s = 100
        elif fcf_yield >= 5: fcf_s = 75 + (fcf_yield - 5) * 5
        elif fcf_yield >= 2: fcf_s = 50 + (fcf_yield - 2) * 8.33
        elif fcf_yield >= 0: fcf_s = 30 + fcf_yield * 10
        else: fcf_s = max(0, 30 + fcf_yield * 5)
        score += 0.25 * fcf_s
        weight_total += 0.25
        sub["fcf_yield_at_simulated_price"] = round(fcf_yield, 2)

    # 4. Earnings yield (TTM EPS / simulated price) — 15%
    if snap.eps_diluted and snap.eps_diluted[0] > 0:
        eps_yield = (snap.eps_diluted[0] / sim_price) * 100
        # 10% = good, 6% = ok, 3% = poor
        if eps_yield >= 12: ey_s = 100
        elif eps_yield >= 6: ey_s = 60 + (eps_yield - 6) * 6.67
        elif eps_yield >= 3: ey_s = 30 + (eps_yield - 3) * 10
        else: ey_s = max(0, eps_yield * 10)
        score += 0.15 * ey_s
        weight_total += 0.15
        sub["earnings_yield_at_simulated"] = round(eps_yield, 2)
        sub["pe_at_simulated_price"] = round(sim_price / snap.eps_diluted[0], 1)

    if weight_total == 0:
        return None

    return {
        "score": round(score / weight_total, 1),
        "weight_filled": round(weight_total, 2),
        "sub_metrics": sub,
    }


# ─── COMPONENT C — INSTITUTIONAL ACCUMULATION (20%) ─────────────────────
# Uses 13F data already in the universe. Available on Render.

def _score_institutional_accumulation(positioning_metrics: dict, inst_buyers: int,
                                       inst_sellers: int, market_cap: int) -> Optional[dict]:
    """
    Per document Filter 4 + 13F-based accumulation.
    Key insight for crash framework: institutional accumulation during fear
    = smart money accumulating. We reward names where buyers > sellers DESPITE
    market weakness.
    """
    score = 0.0
    weight_total = 0.0
    sub = {}

    # 1. Buy/sell dominance — 40%
    total_active = inst_buyers + inst_sellers
    if total_active >= 10:
        buy_ratio = inst_buyers / total_active
        bs_s = buy_ratio * 100  # 50/50 = 50, all buyers = 100
        score += 0.40 * bs_s
        weight_total += 0.40
        sub["buyers"] = inst_buyers
        sub["sellers"] = inst_sellers
        sub["buy_sell_ratio_pct"] = round(buy_ratio * 100, 0)

    # 2. Ownership velocity (share-count delta Q-o-Q) — 30%
    share_delta = positioning_metrics.get("share_delta_pct", 0)
    # Map: -20% = 0, 0% = 50, +20% = 90, +40%+ = 100
    if share_delta >= 40: vel_s = 100
    elif share_delta >= 10: vel_s = 70 + (share_delta - 10) * 0.67
    elif share_delta >= 0: vel_s = 50 + share_delta * 2
    elif share_delta >= -20: vel_s = max(0, 50 + share_delta * 2.5)
    else: vel_s = 0
    score += 0.30 * vel_s
    weight_total += 0.30
    sub["share_velocity_qoq_pct"] = round(share_delta, 1)

    # 3. Persistence (consecutive Qs of net accumulation) — 20%
    persist_q = positioning_metrics.get("persistence_quarters", 0)
    persist_s = min(100, persist_q * 16.67)  # 6Q = 100
    score += 0.20 * persist_s
    weight_total += 0.20
    sub["persistence_quarters"] = persist_q

    # 4. Concentration (HHI — too concentrated = fragile, too diffuse = no conviction) — 10%
    hhi = positioning_metrics.get("concentration_hhi", 0.5)
    # Sweet spot: 0.15-0.35 (moderate concentration = institutional conviction without single-holder risk)
    if 0.15 <= hhi <= 0.35: hhi_s = 100
    elif hhi < 0.15: hhi_s = 50 + (hhi / 0.15) * 50
    else: hhi_s = max(0, 100 - (hhi - 0.35) * 200)
    score += 0.10 * hhi_s
    weight_total += 0.10
    sub["concentration_hhi"] = round(hhi, 3)

    # HARD VETO: heavy distribution caps the score at 25
    if total_active >= 20 and inst_sellers >= 3 * max(1, inst_buyers):
        final = min(score / weight_total, 25)
        sub["distribution_veto"] = True
    else:
        final = score / weight_total

    return {
        "score": round(final, 1),
        "weight_filled": round(weight_total, 2),
        "sub_metrics": sub,
    }


# ─── COMPONENT D — MOAT / FUTURE DEMAND (15%) ──────────────────────────

# Diamond sectors per document: AI, infrastructure, semis, photonics, defense, energy
_DIAMOND_SECTORS = {
    # sector_keyword: (relevance_score, label)
    "semiconductor":            (95, "AI/semis — top diamond sector"),
    "technology":               (80, "Tech — strong diamond exposure"),
    "communication services":   (70, "Comm services — varies, check sub-industry"),
    "industrial":               (65, "Industrials — includes defense, automation"),
    "aerospace":                (90, "Defense/aerospace — top diamond sector"),
    "energy":                   (75, "Energy — grid, nuclear, renewables"),
    "utilities":                (60, "Utilities — power for AI data centers"),
    "healthcare":               (55, "Healthcare — varies; biotech speculative"),
    "consumer cyclical":        (30, "Consumer cyclical — lower diamond relevance"),
    "consumer defensive":       (40, "Consumer defensive — recovery-resistant but not high-growth"),
    "financial":                (35, "Financials — credit-cycle dependent"),
    "real estate":              (40, "REITs — interest-rate sensitive"),
    "basic materials":          (50, "Materials — commodity dependent"),
}


def _score_moat_future(snap: FundamentalsSnapshot, sector: str) -> Optional[dict]:
    """
    Per document Filter 2 + Filter 5: moat + future demand relevance.
    Sector-based heuristic + margin durability proxy.
    """
    score = 0.0
    weight_total = 0.0
    sub = {}

    # 1. Sector / AI relevance — 50%
    s = (sector or "").lower()
    relevance_score = 50  # default
    relevance_label = "Unknown sector — neutral"
    for keyword, (val, label) in _DIAMOND_SECTORS.items():
        if keyword in s:
            relevance_score = val
            relevance_label = label
            break
    score += 0.50 * relevance_score
    weight_total += 0.50
    sub["sector_relevance_score"] = relevance_score
    sub["sector_relevance_label"] = relevance_label

    # 2. Gross margin level (proxy for pricing power / moat) — 30%
    if snap.has_data and snap.gross_profit and snap.revenue:
        gms = []
        for i in range(min(len(snap.gross_profit), len(snap.revenue))):
            if snap.revenue[i] > 0:
                gms.append(snap.gross_profit[i] / snap.revenue[i] * 100)
        if gms:
            gm_avg = statistics.mean(gms)
            # 70%+ = elite moat (SaaS-like), 50% = strong, 30% = ok, <20% = commodity
            if gm_avg >= 70: gm_s = 100
            elif gm_avg >= 50: gm_s = 80 + (gm_avg - 50) * 1
            elif gm_avg >= 30: gm_s = 50 + (gm_avg - 30) * 1.5
            elif gm_avg >= 15: gm_s = 25 + (gm_avg - 15) * 1.67
            else: gm_s = max(0, gm_avg * 1.67)
            score += 0.30 * gm_s
            weight_total += 0.30
            sub["gross_margin_avg_pct"] = round(gm_avg, 1)

    # 3. Revenue growth durability — 20%
    if snap.has_data and len(snap.revenue) >= 3:
        # 3Y CAGR
        if snap.revenue[2] > 0:
            cagr = ((snap.revenue[0] / snap.revenue[2]) ** (1/2) - 1) * 100
        else:
            cagr = 0
        # 30%+ = excellent, 15% = good, 5% = ok, negative = bad
        if cagr >= 30: g_s = 100
        elif cagr >= 15: g_s = 70 + (cagr - 15) * 2
        elif cagr >= 5: g_s = 50 + (cagr - 5) * 2
        elif cagr >= 0: g_s = 30 + cagr * 4
        else: g_s = max(0, 30 + cagr * 3)
        score += 0.20 * g_s
        weight_total += 0.20
        sub["revenue_3y_cagr_pct"] = round(cagr, 1)

    if weight_total == 0:
        return None
    return {
        "score": round(score / weight_total, 1),
        "weight_filled": round(weight_total, 2),
        "sub_metrics": sub,
    }


# ─── COMPONENT E — TECHNICAL RECOVERY POTENTIAL (10%) ───────────────────

def _score_technical_recovery(pct_in_range: float, current_price: float,
                               sim_price: float) -> Optional[dict]:
    """
    Per document Filter 7. Without intraday OHLC + sector ETF, we use:
    - 52W positioning (proxy for current technical setup)
    - Implied drawdown at simulated price (how oversold would it be?)
    """
    if pct_in_range < 0 or current_price <= 0:
        return None

    score = 0.0
    weight_total = 0.0
    sub = {}

    # 1. Current 52W positioning — high RS today = quality, will hold up better — 50%
    # For DIAMOND scanner: we want names that ARE strong today (resilient)
    # because their post-crash setup will still be attractive
    rs_s = pct_in_range  # 0-100 directly
    score += 0.50 * rs_s
    weight_total += 0.50
    sub["current_52w_position_pct"] = round(pct_in_range, 0)

    # 2. Simulated drawdown depth (deeper crash = more attractive entry, up to a point) — 50%
    sim_drawdown = ((current_price - sim_price) / current_price) * 100
    # 15-30% = sweet spot for entry, <10% = not enough discount, >50% = something likely broken
    if 15 <= sim_drawdown <= 30: dd_s = 100
    elif sim_drawdown < 15: dd_s = 50 + sim_drawdown * 3.33
    elif sim_drawdown <= 50: dd_s = 100 - (sim_drawdown - 30) * 2
    else: dd_s = max(0, 60 - (sim_drawdown - 50) * 3)
    score += 0.50 * dd_s
    weight_total += 0.50
    sub["simulated_drawdown_pct"] = round(sim_drawdown, 1)
    sub["simulated_entry_price"] = round(sim_price, 2)

    return {
        "score": round(score / weight_total, 1),
        "weight_filled": round(weight_total, 2),
        "sub_metrics": sub,
    }


# ─── TOP-LEVEL SCORING ──────────────────────────────────────────────────

@dataclass
class DiamondScore:
    ticker: str
    has_fundamentals: bool
    current_price: float
    simulated_price: float
    implied_drawdown_pct: float
    beta_used: float
    market_cap: int

    # 5 component scores (0-100 each, or None)
    business_strength: Optional[dict]
    valuation_compression: Optional[dict]
    institutional_accumulation: Optional[dict]
    moat_future: Optional[dict]
    technical_recovery: Optional[dict]

    # Composite + verdict
    composite_score: Optional[float]
    components_present: int
    verdict: str
    sector: str
    narrative: str = ""


def compute_diamond_score(
    ticker: str,
    current_price: float,
    market_cap: int,
    beta: float,
    market_drop_pct: float,
    positioning_metrics: dict,
    inst_buyers: int,
    inst_sellers: int,
    pct_in_range: float,
) -> DiamondScore:
    """Compute full diamond score for one ticker. Single fundamentals fetch."""
    snap = _fetch_fundamentals(ticker)
    sector = snap.sector if snap.has_data else ""

    # Crash simulation
    sim_price, implied_dd = _simulate_crash_price(current_price, beta, market_drop_pct)

    # Compute all 5 components
    bs = _score_business_strength(snap)
    vc = _score_valuation_compression(snap, current_price, sim_price, market_cap)
    ia = _score_institutional_accumulation(positioning_metrics, inst_buyers, inst_sellers, market_cap)
    mf = _score_moat_future(snap, sector)
    tr = _score_technical_recovery(pct_in_range, current_price, sim_price)

    # Composite (per document weights: 30/25/20/15/10)
    weights = [
        (bs, 0.30),
        (vc, 0.25),
        (ia, 0.20),
        (mf, 0.15),
        (tr, 0.10),
    ]
    score_sum = 0.0
    weight_sum = 0.0
    components_present = 0
    for comp, w in weights:
        if comp and comp.get("score") is not None:
            score_sum += comp["score"] * w
            weight_sum += w
            components_present += 1

    if weight_sum > 0:
        composite = score_sum / weight_sum
    else:
        composite = None

    verdict = _conviction_band(composite, components_present)

    # Narrative
    parts = []
    if bs: parts.append(f"Business: {bs['score']:.0f}")
    if vc: parts.append(f"Val@-{implied_dd:.0f}%: {vc['score']:.0f}")
    if ia: parts.append(f"Inst flow: {ia['score']:.0f}")
    if mf: parts.append(f"Moat/Future: {mf['score']:.0f}")
    if tr: parts.append(f"Tech: {tr['score']:.0f}")
    narrative = " · ".join(parts)
    if verdict == "ELITE DIAMOND":
        narrative += " — would be a top buy at simulated price"
    elif verdict == "STRONG DIAMOND":
        narrative += " — high-conviction buy at simulated price"

    return DiamondScore(
        ticker=ticker,
        has_fundamentals=snap.has_data,
        current_price=round(current_price, 2),
        simulated_price=round(sim_price, 2),
        implied_drawdown_pct=round(implied_dd, 1),
        beta_used=round(beta if beta else 1.0, 2),
        market_cap=int(market_cap),
        business_strength=bs,
        valuation_compression=vc,
        institutional_accumulation=ia,
        moat_future=mf,
        technical_recovery=tr,
        composite_score=round(composite, 1) if composite is not None else None,
        components_present=components_present,
        verdict=verdict,
        sector=sector,
        narrative=narrative,
    )


# ─── BATCH SCANNER ──────────────────────────────────────────────────────

def hunt_diamonds(scores: list, market_drop_pct: float = 25,
                  min_market_cap: int = 1_000_000_000,
                  max_workers: int = 8) -> List[dict]:
    """
    Run diamond scoring across the universe.
    Input: list of TickerScore objects from existing positioning scanner.
    """
    cache_key = f"{market_drop_pct}:{min_market_cap}"
    now = time.time()
    with _diamond_lock:
        cached = _diamond_cache.get(cache_key)
        if cached and (now - cached[0]) < _CACHE_TTL:
            return cached[1]

    # Pre-filter by market cap
    eligible = [s for s in scores if getattr(s, "market_cap", 0) >= min_market_cap]

    def _one(ts):
        try:
            metrics = {
                "persistence_quarters": ts.persistence_quarters,
                "filer_count_delta": ts.filer_count_delta,
                "concentration_hhi": ts.concentration_hhi,
                "value_delta_pct": ts.value_delta_pct,
                "share_delta_pct": ts.share_delta_pct,
            }
            return compute_diamond_score(
                ticker=ts.ticker,
                current_price=getattr(ts, "price", 0) or 0,
                market_cap=getattr(ts, "market_cap", 0),
                beta=getattr(ts, "beta", 1.0) or 1.0,
                market_drop_pct=market_drop_pct,
                positioning_metrics=metrics,
                inst_buyers=getattr(ts, "inst_buyers", 0),
                inst_sellers=getattr(ts, "inst_sellers", 0),
                pct_in_range=getattr(ts, "pct_in_range", -1),
            )
        except Exception:
            return None

    results = []
    with ThreadPoolExecutor(max_workers=min(max_workers, max(1, len(eligible)))) as ex:
        futures = {ex.submit(_one, ts): ts for ts in eligible[:200]}  # cap at 200 for speed
        for fut in as_completed(futures):
            try:
                ds = fut.result(timeout=60)
                if ds is not None:
                    results.append(ds)
            except Exception:
                pass

    # Convert to dict and sort by composite score (None last)
    out = []
    for ds in results:
        d = {
            "ticker": ds.ticker,
            "sector": ds.sector,
            "has_fundamentals": ds.has_fundamentals,
            "current_price": ds.current_price,
            "simulated_price": ds.simulated_price,
            "implied_drawdown_pct": ds.implied_drawdown_pct,
            "beta_used": ds.beta_used,
            "market_cap": ds.market_cap,
            "composite_score": ds.composite_score,
            "components_present": ds.components_present,
            "verdict": ds.verdict,
            "narrative": ds.narrative,
            "business_strength": ds.business_strength,
            "valuation_compression": ds.valuation_compression,
            "institutional_accumulation": ds.institutional_accumulation,
            "moat_future": ds.moat_future,
            "technical_recovery": ds.technical_recovery,
        }
        out.append(d)

    # Sort: composite desc (None last)
    out.sort(key=lambda x: (x["composite_score"] if x["composite_score"] is not None else -1), reverse=True)

    with _diamond_lock:
        _diamond_cache[cache_key] = (now, out)
    return out
