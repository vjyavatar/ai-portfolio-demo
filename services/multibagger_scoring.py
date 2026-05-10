"""
r63.72.7 — Multibagger Scoring Engine.

Implements the institution-grade framework:

    Multibagger Score = (0.35M + 0.25F + 0.25G + 0.15O) × (1 − Risk Penalty)

where:
    M = Moat Quality        (35%) — durability of returns
    F = Institutional Flow  (25%) — capital endorsement (early-phase favored)
    G = Growth Inflection   (25%) — momentum of fundamentals
    O = Optionality         (15%) — non-linear upside potential

Each component returns a 0-100 score. Composite is risk-adjusted (multiplicative penalty).

Critical design points:
1. Each component degrades GRACEFULLY when data is missing. Yahoo Finance is
   401-blocked on Render — instead of failing, missing data → neutral 50.
2. The "early-phase" detector in F: rewards stocks where institutional adoption
   is RISING but still BELOW saturation. Pre-multibagger NVDA (~T-12 months)
   had ~200 filers and growing, not 3000 filers. Crowded names get F-penalty.
3. Moat measured by DURABILITY (5Y stability of metrics under stress), not
   point-in-time snapshots.
4. All weights, thresholds, and penalty curves are explicit in code — easy
   to tune without a database migration.

This module reads-only. Caller passes ticker + already-computed positioning
metrics + a quote dict; we add fundamentals lookup ourselves.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
import math
import statistics
import time
import threading


# ─── Caching for yfinance fundamentals — fundamentals don't change intra-day ──
_fund_cache: Dict[str, tuple] = {}
_fund_lock = threading.Lock()
_FUND_CACHE_TTL = 3600  # 1 hour — fundamentals are quarterly anyway


def _safe_float(v, default=0.0) -> float:
    try:
        f = float(v)
        if f != f or f in (float("inf"), float("-inf")):
            return default
        return f
    except (TypeError, ValueError):
        return default


def _safe_div(num, den, default=0.0) -> float:
    if den is None or den == 0:
        return default
    try:
        return num / den
    except Exception:
        return default


@dataclass
class FundamentalsSnapshot:
    """5-year fundamentals pulled from yfinance. Empty if Yahoo blocked."""
    ticker: str
    has_data: bool = False

    # Income statement series (most-recent first, up to 5 years annual)
    revenue: List[float] = None             # annual revenue
    gross_profit: List[float] = None
    operating_income: List[float] = None
    net_income: List[float] = None
    rd_expense: List[float] = None
    eps_diluted: List[float] = None

    # Balance sheet
    total_assets: List[float] = None
    total_equity: List[float] = None
    total_debt: List[float] = None
    cash: List[float] = None
    shares_outstanding: List[float] = None  # for dilution check

    # Cash flow
    fcf: List[float] = None
    capex: List[float] = None

    # Quarterly revenue for G-score (most recent 8 quarters)
    quarterly_revenue: List[float] = None

    # EPS revisions (from earnings_dates pattern in data_sources)
    last_4_eps_beats: int = 0  # how many of last 4 quarters beat consensus

    sector: str = ""

    def __post_init__(self):
        for f in ("revenue", "gross_profit", "operating_income", "net_income",
                  "rd_expense", "eps_diluted", "total_assets", "total_equity",
                  "total_debt", "cash", "shares_outstanding", "fcf", "capex",
                  "quarterly_revenue"):
            if getattr(self, f) is None:
                setattr(self, f, [])


def _fetch_fundamentals(ticker: str) -> FundamentalsSnapshot:
    """
    Fetch 5-year fundamentals from yfinance. Returns FundamentalsSnapshot
    with has_data=True if successful, has_data=False if Yahoo failed.

    Cached for 1 hour per ticker.
    """
    snap = FundamentalsSnapshot(ticker=ticker)
    now = time.time()

    with _fund_lock:
        cached = _fund_cache.get(ticker)
        if cached and (now - cached[0]) < _FUND_CACHE_TTL:
            return cached[1]

    try:
        import yfinance as yf
    except ImportError:
        with _fund_lock:
            _fund_cache[ticker] = (now, snap)
        return snap

    try:
        t = yf.Ticker(ticker)

        # Sector for sector-aware optionality
        try:
            info = t.info if hasattr(t, "info") else {}
            snap.sector = (info or {}).get("sector", "") or ""
        except Exception:
            pass

        # Income statement (annual)
        try:
            inc = t.income_stmt
            if inc is not None and not inc.empty:
                # Columns are date-indexed (newest first usually)
                cols = list(inc.columns)
                snap.revenue = [_safe_float(inc.loc["Total Revenue", c]) if "Total Revenue" in inc.index else 0.0 for c in cols][:5]
                snap.gross_profit = [_safe_float(inc.loc["Gross Profit", c]) if "Gross Profit" in inc.index else 0.0 for c in cols][:5]
                snap.operating_income = [_safe_float(inc.loc["Operating Income", c]) if "Operating Income" in inc.index else 0.0 for c in cols][:5]
                snap.net_income = [_safe_float(inc.loc["Net Income", c]) if "Net Income" in inc.index else 0.0 for c in cols][:5]
                snap.rd_expense = [_safe_float(inc.loc["Research And Development", c]) if "Research And Development" in inc.index else 0.0 for c in cols][:5]
                if "Diluted EPS" in inc.index:
                    snap.eps_diluted = [_safe_float(inc.loc["Diluted EPS", c]) for c in cols][:5]
        except Exception:
            pass

        # Balance sheet
        try:
            bs = t.balance_sheet
            if bs is not None and not bs.empty:
                cols = list(bs.columns)
                snap.total_assets = [_safe_float(bs.loc["Total Assets", c]) if "Total Assets" in bs.index else 0.0 for c in cols][:5]
                if "Stockholders Equity" in bs.index:
                    snap.total_equity = [_safe_float(bs.loc["Stockholders Equity", c]) for c in cols][:5]
                elif "Total Equity Gross Minority Interest" in bs.index:
                    snap.total_equity = [_safe_float(bs.loc["Total Equity Gross Minority Interest", c]) for c in cols][:5]
                if "Total Debt" in bs.index:
                    snap.total_debt = [_safe_float(bs.loc["Total Debt", c]) for c in cols][:5]
                if "Cash And Cash Equivalents" in bs.index:
                    snap.cash = [_safe_float(bs.loc["Cash And Cash Equivalents", c]) for c in cols][:5]
                if "Share Issued" in bs.index:
                    snap.shares_outstanding = [_safe_float(bs.loc["Share Issued", c]) for c in cols][:5]
        except Exception:
            pass

        # Cash flow
        try:
            cf = t.cashflow
            if cf is not None and not cf.empty:
                cols = list(cf.columns)
                if "Free Cash Flow" in cf.index:
                    snap.fcf = [_safe_float(cf.loc["Free Cash Flow", c]) for c in cols][:5]
                if "Capital Expenditure" in cf.index:
                    snap.capex = [abs(_safe_float(cf.loc["Capital Expenditure", c])) for c in cols][:5]
        except Exception:
            pass

        # Quarterly revenue for G-score (acceleration)
        try:
            q_inc = t.quarterly_income_stmt
            if q_inc is not None and not q_inc.empty and "Total Revenue" in q_inc.index:
                cols = list(q_inc.columns)[:8]
                snap.quarterly_revenue = [_safe_float(q_inc.loc["Total Revenue", c]) for c in cols]
        except Exception:
            pass

        # Beat rate from earnings dates
        try:
            ed = t.earnings_dates
            if ed is not None and not ed.empty:
                beats = 0
                checked = 0
                for idx, row in ed.iterrows():
                    if checked >= 4:
                        break
                    est = row.get("EPS Estimate")
                    act = row.get("Reported EPS")
                    if est is None or act is None:
                        continue
                    if (isinstance(est, float) and est != est) or (isinstance(act, float) and act != act):
                        continue
                    if act > est:
                        beats += 1
                    checked += 1
                snap.last_4_eps_beats = beats
        except Exception:
            pass

        # Mark has_data if we got at least revenue
        if snap.revenue and len(snap.revenue) >= 2:
            snap.has_data = True

    except Exception:
        pass

    with _fund_lock:
        _fund_cache[ticker] = (now, snap)

    return snap


# ───────────────────────────────────────────────────────────────────────────
# Component 1 — MOAT QUALITY SCORE (35%)
# ───────────────────────────────────────────────────────────────────────────

def _score_moat(snap: FundamentalsSnapshot) -> tuple:
    """
    Returns (score_0_100, components_dict, narrative).

    Measures DURABILITY of excess returns under stress.
    Key insight from user spec: moat = ability to sustain ROIC > cost-of-capital
    across cycles while defending share. We approximate via:
    - ROIC 5Y MEDIAN (not mean — robust to outliers, captures floor)
    - ROIC stability (coefficient of variation, lower = better)
    - Gross margin floor (worst year in 5Y = pricing power under stress)
    - Operating margin trend
    - FCF consistency
    """
    if not snap.has_data:
        return 50.0, {}, "moat data unavailable"

    components = {}

    # ROIC = NOPAT / Invested Capital ~ Operating Income × (1−tax) / (Debt + Equity)
    # Approximating tax rate at 21% (US corporate) for simplicity
    roics = []
    for i, op in enumerate(snap.operating_income):
        debt = snap.total_debt[i] if i < len(snap.total_debt) else 0
        equity = snap.total_equity[i] if i < len(snap.total_equity) else 0
        invested = debt + equity
        if invested > 0 and op != 0:
            nopat = op * 0.79  # after 21% tax assumption
            roics.append(nopat / invested)

    if len(roics) >= 3:
        roic_median = statistics.median(roics)
        roic_stdev = statistics.pstdev(roics) if len(roics) > 1 else 0
        components["roic_median"] = roic_median
        components["roic_stability"] = roic_stdev

        # Score ROIC level: 0% → 0, 12% → 50, 25%+ → 100
        roic_level_score = max(0, min(100, (roic_median * 100 / 25) * 100))

        # Score ROIC stability: coefficient of variation
        if abs(roic_median) > 0.001:
            cv = roic_stdev / abs(roic_median)
            # Lower CV = more stable. Penalty starts above CV=0.5
            roic_stability_score = max(0, min(100, 100 - (cv * 80)))
        else:
            roic_stability_score = 30
    else:
        roic_level_score = 50
        roic_stability_score = 50
        components["roic_median"] = 0
        components["roic_stability"] = 0

    # Gross margin floor (worst year in 5Y) - pricing power under stress
    gross_margins = []
    for i in range(min(len(snap.gross_profit), len(snap.revenue))):
        if snap.revenue[i] > 0:
            gm = snap.gross_profit[i] / snap.revenue[i]
            gross_margins.append(gm)

    if gross_margins:
        gm_floor = min(gross_margins)
        components["gross_margin_floor"] = gm_floor
        # 0% = 0, 30% = 50, 60%+ = 100
        gm_floor_score = max(0, min(100, gm_floor * 100 / 60 * 100))
    else:
        gm_floor_score = 50
        components["gross_margin_floor"] = 0

    # Operating margin trend (slope over 5Y)
    op_margins = []
    for i in range(min(len(snap.operating_income), len(snap.revenue))):
        if snap.revenue[i] > 0:
            op_margins.append(snap.operating_income[i] / snap.revenue[i])

    if len(op_margins) >= 3:
        # Reverse so oldest first (positive slope = improving)
        rev_margins = list(reversed(op_margins))
        n = len(rev_margins)
        x_mean = (n - 1) / 2
        y_mean = sum(rev_margins) / n
        num = sum((i - x_mean) * (rev_margins[i] - y_mean) for i in range(n))
        den = sum((i - x_mean) ** 2 for i in range(n))
        slope = num / den if den > 0 else 0
        components["op_margin_slope"] = slope
        # +0.02 (200bps/yr) → 100, 0 → 50, -0.02 → 0
        op_trend_score = max(0, min(100, 50 + slope * 2500))
    else:
        op_trend_score = 50
        components["op_margin_slope"] = 0

    # FCF consistency — N years positive of last 5
    fcf_positive_years = sum(1 for f in snap.fcf if f > 0)
    components["fcf_positive_years"] = fcf_positive_years
    fcf_score = (fcf_positive_years / max(1, len(snap.fcf))) * 100 if snap.fcf else 50

    # Cycle survival — did margins compress > 40% in any single year? Penalty.
    cycle_penalty = 0.0
    if len(op_margins) >= 2:
        for i in range(1, len(op_margins)):
            prev = op_margins[i]
            curr = op_margins[i - 1]
            if prev > 0.05 and curr < prev * 0.6:  # margin compressed > 40%
                cycle_penalty = max(cycle_penalty, 20)  # up to -20 pts
    components["cycle_penalty"] = cycle_penalty

    # Weighted composite within Moat
    moat_score = (
        0.30 * roic_level_score
        + 0.20 * roic_stability_score
        + 0.20 * gm_floor_score
        + 0.15 * op_trend_score
        + 0.15 * fcf_score
    ) - cycle_penalty
    moat_score = max(0, min(100, moat_score))

    # Narrative
    narrative_parts = []
    if components["roic_median"] > 0.20:
        narrative_parts.append(f"high ROIC ({components['roic_median']*100:.0f}%) sustained")
    elif components["roic_median"] > 0.12:
        narrative_parts.append(f"durable ROIC ({components['roic_median']*100:.0f}%)")
    if components["gross_margin_floor"] > 0.50:
        narrative_parts.append("strong pricing power")
    if cycle_penalty > 0:
        narrative_parts.append("history of cyclical margin compression")
    narrative = "; ".join(narrative_parts) or "moderate moat profile"

    return moat_score, components, narrative


# ───────────────────────────────────────────────────────────────────────────
# Component 2 — INSTITUTIONAL FLOW SCORE (25%)
# ───────────────────────────────────────────────────────────────────────────

def _score_flow(positioning_metrics: dict, latest_filer_count: int,
                inst_buyers: int, inst_sellers: int) -> tuple:
    """
    Returns (score_0_100, components_dict, narrative).

    KEY INSIGHT (user critique): institutions chase momentum more than they
    front-run alpha. True multibagger candidates are EARLY-PHASE: rising
    institutional adoption but BELOW saturation. We invert U:
    - 50-300 filers + rising = early phase (HIGH score)
    - 300-1500 filers + rising = mid phase (MEDIUM score)
    - 1500+ filers = saturated / crowded (LOW score)

    r63.72.8 fixes:
    - Buy/sell scoring is now SYMMETRIC (heavy sellers get NEGATIVE score, not zero floor)
    - Hard veto: if sellers > 3× buyers AND active >= 20, F is capped at 30
      (prevents "great moat + bad flow" names like FICO from getting top scores)
    - Buy/sell weight increased to 35% (was 25%); phase reduced to 25% (was 35%)
    """
    components = {}

    persistence_q = positioning_metrics.get("persistence_quarters", 0)
    filer_delta = positioning_metrics.get("filer_count_delta", 0)
    concentration = positioning_metrics.get("concentration_hhi", 0.5)

    # 1. Phase detector (existing — inverted U over filer count)
    if latest_filer_count <= 30:
        early_phase_score = 30
        phase_label = "Pre-discovery"
    elif latest_filer_count <= 150:
        early_phase_score = 100
        phase_label = "Early discovery"
    elif latest_filer_count <= 400:
        early_phase_score = 90
        phase_label = "Building"
    elif latest_filer_count <= 1000:
        early_phase_score = 60
        phase_label = "Mid-cycle"
    elif latest_filer_count <= 2000:
        early_phase_score = 35
        phase_label = "Crowded"
    else:
        early_phase_score = 15
        phase_label = "Saturated"

    components["phase_label"] = phase_label
    components["early_phase_score"] = early_phase_score

    # 2. r63.72.8: SYMMETRIC buy/sell scoring (was floored at 0; now full ±range)
    total_active = inst_buyers + inst_sellers
    if total_active >= 10:
        buy_ratio = inst_buyers / total_active
        # 50/50 = 50, 80/20 = 90, all buyers = 100, all sellers = 0
        buyer_dom_score = max(0, min(100, buy_ratio * 100))
    else:
        buyer_dom_score = 50
        buy_ratio = 0.5
    components["buyer_dominance"] = buyer_dom_score
    components["buy_ratio"] = buy_ratio

    # 3. Persistence
    capped_persist = min(6, persistence_q)
    persistence_score = (capped_persist / 6.0) * 100
    components["persistence_capped"] = persistence_score

    # 4. Filer-count momentum
    if filer_delta >= 50:
        flow_momentum_score = 100
    elif filer_delta >= 20:
        flow_momentum_score = 80
    elif filer_delta >= 5:
        flow_momentum_score = 60
    elif filer_delta >= 0:
        flow_momentum_score = 40
    elif filer_delta >= -10:
        flow_momentum_score = 20
    else:
        flow_momentum_score = 5
    components["flow_momentum"] = flow_momentum_score

    # 5. Concentration penalty
    if concentration > 0.7:
        concentration_score = 20
    elif concentration > 0.5:
        concentration_score = 50
    else:
        concentration_score = 80
    components["concentration_score"] = concentration_score

    # r63.72.8: Reweighted — buy/sell ratio is now the PRIMARY signal
    flow_score = (
        0.35 * buyer_dom_score        # PRIMARY (was 25%)
        + 0.25 * early_phase_score    # MODIFIER (was 35%)
        + 0.20 * flow_momentum_score
        + 0.10 * persistence_score
        + 0.10 * concentration_score
    )

    # r63.72.8: HARD VETO for lopsided distribution
    # If institutions are clearly EXITING en masse, no amount of "early phase"
    # filer count math can rescue this. Cap F at 30.
    veto_applied = False
    if total_active >= 20 and inst_sellers >= 3 * max(1, inst_buyers):
        flow_score = min(flow_score, 30)
        veto_applied = True
    components["distribution_veto"] = veto_applied

    # Narrative
    narrative_parts = []
    if veto_applied:
        narrative_parts.append(f"⚠️ Institutional distribution ({inst_buyers}:{inst_sellers})")
    elif buy_ratio > 0.70 and total_active >= 10:
        narrative_parts.append(f"Strong inst accumulation ({inst_buyers}:{inst_sellers})")
    elif buy_ratio > 0.55 and total_active >= 10:
        narrative_parts.append(f"Net accumulation ({inst_buyers}:{inst_sellers})")
    elif buy_ratio < 0.30 and total_active >= 10:
        narrative_parts.append(f"Heavy distribution ({inst_buyers}:{inst_sellers})")
    narrative_parts.append(phase_label)
    if filer_delta >= 20:
        narrative_parts.append(f"+{filer_delta} new filers")
    elif filer_delta <= -10:
        narrative_parts.append(f"{filer_delta} filers exiting")
    narrative = ", ".join(narrative_parts)

    return flow_score, components, narrative


# ───────────────────────────────────────────────────────────────────────────
# Component 3 — GROWTH INFLECTION SCORE (25%)
# ───────────────────────────────────────────────────────────────────────────

def _score_growth(snap: FundamentalsSnapshot) -> tuple:
    """
    Returns (score_0_100, components_dict, narrative).

    "Momentum of fundamentals" — change in growth rate is more predictive of
    multibagger setups than absolute level. NVDA's 100% YoY in 2023 mattered
    less than the ACCELERATION from -20% in early-2023 to +200% by 4Q23.
    """
    if not snap.has_data:
        return 50.0, {}, "growth data unavailable"

    components = {}

    # 1. Revenue Q-over-Q ACCELERATION (the slope of the slope)
    # Compare current Q/Q growth rate to prior Q/Q growth rate
    accel_score = 50
    if len(snap.quarterly_revenue) >= 4:
        qr = snap.quarterly_revenue
        # Most recent first
        qoq_recent = (qr[0] - qr[1]) / qr[1] if qr[1] > 0 else 0
        qoq_prior = (qr[2] - qr[3]) / qr[3] if qr[3] > 0 else 0
        accel = qoq_recent - qoq_prior
        components["qoq_acceleration"] = accel
        # +5pp acceleration → 100, 0 → 50, -5pp → 0
        accel_score = max(0, min(100, 50 + accel * 1000))
    else:
        components["qoq_acceleration"] = 0

    # 2. Annual revenue growth slope (5Y trajectory)
    rev_slope_score = 50
    if len(snap.revenue) >= 3:
        # Compute growth rate in each year
        growth_rates = []
        for i in range(len(snap.revenue) - 1):
            if snap.revenue[i + 1] > 0:
                growth_rates.append((snap.revenue[i] - snap.revenue[i + 1]) / snap.revenue[i + 1])
        if len(growth_rates) >= 2:
            avg_growth = sum(growth_rates) / len(growth_rates)
            components["avg_annual_growth"] = avg_growth
            # 0% → 30, 15% → 70, 30%+ → 100
            rev_slope_score = max(0, min(100, 30 + avg_growth * 233))
    else:
        components["avg_annual_growth"] = 0

    # 3. Margin expansion trend (operating margin improving = leverage kicking in)
    margin_trend_score = 50
    op_margins = []
    for i in range(min(len(snap.operating_income), len(snap.revenue))):
        if snap.revenue[i] > 0:
            op_margins.append(snap.operating_income[i] / snap.revenue[i])
    if len(op_margins) >= 3:
        # Slope (oldest first)
        rev_m = list(reversed(op_margins))
        n = len(rev_m)
        x_mean = (n - 1) / 2
        y_mean = sum(rev_m) / n
        num = sum((i - x_mean) * (rev_m[i] - y_mean) for i in range(n))
        den = sum((i - x_mean) ** 2 for i in range(n))
        slope = num / den if den > 0 else 0
        components["margin_trend_slope"] = slope
        # +200bps/yr → 100, 0 → 50, -200bps → 0
        margin_trend_score = max(0, min(100, 50 + slope * 2500))
    else:
        components["margin_trend_slope"] = 0

    # 4. Beat rate (last 4 quarters)
    beats = snap.last_4_eps_beats
    components["beat_rate"] = beats
    # 4/4 = 100, 3/4 = 75, 2/4 = 50, 1/4 = 25, 0/4 = 10
    beat_score = (beats / 4.0) * 90 + 10 if beats > 0 else 10

    # Weighted composite within G
    growth_score = (
        0.35 * accel_score
        + 0.25 * rev_slope_score
        + 0.25 * margin_trend_score
        + 0.15 * beat_score
    )

    # Narrative
    narrative_parts = []
    if components["qoq_acceleration"] > 0.05:
        narrative_parts.append(f"revenue accelerating Q/Q (+{components['qoq_acceleration']*100:.1f}pp)")
    elif components["qoq_acceleration"] < -0.05:
        narrative_parts.append("revenue decelerating Q/Q")
    if components["avg_annual_growth"] > 0.20:
        narrative_parts.append(f"{components['avg_annual_growth']*100:.0f}% avg annual growth")
    if components["margin_trend_slope"] > 0.01:
        narrative_parts.append("margins expanding")
    if beats >= 3:
        narrative_parts.append(f"{beats}/4 EPS beats")
    narrative = "; ".join(narrative_parts) or "growth profile mixed"

    return growth_score, components, narrative


# ───────────────────────────────────────────────────────────────────────────
# Component 4 — OPTIONALITY SCORE (15%)
# ───────────────────────────────────────────────────────────────────────────

def _score_optionality(snap: FundamentalsSnapshot, pct_in_range: float,
                       market_cap: int) -> tuple:
    """
    Returns (score_0_100, components_dict, narrative).

    Non-linear upside potential. Sector-aware:
    - Tech/Biotech: R&D intensity (innovation pipeline)
    - All sectors: Cash optionality (ability to fund growth without dilution)
    - Asymmetric upside via 52W positioning
    """
    components = {}

    # 1. R&D intensity (for tech/biotech especially)
    rd_score = 50
    if snap.rd_expense and snap.revenue and snap.revenue[0] > 0:
        rd_intensity = snap.rd_expense[0] / snap.revenue[0]
        components["rd_intensity"] = rd_intensity
        sector_lower = (snap.sector or "").lower()
        if "tech" in sector_lower or "communication" in sector_lower:
            # Tech: 5% = floor, 15% = strong, 25%+ = excellent
            rd_score = max(0, min(100, rd_intensity * 100 / 25 * 100))
        elif "health" in sector_lower or "pharma" in sector_lower or "bio" in sector_lower:
            # Pharma: 10%+ R&D = floor, 25%+ = excellent
            rd_score = max(0, min(100, rd_intensity * 100 / 30 * 100))
        else:
            # Other sectors — R&D less central
            rd_score = max(0, min(100, rd_intensity * 100 / 10 * 100))
    else:
        components["rd_intensity"] = 0

    # 2. Cash optionality (cash vs. market cap = ability to fund/M&A without dilution)
    cash_score = 50
    if snap.cash and market_cap > 0:
        cash_ratio = snap.cash[0] / market_cap if market_cap > 0 else 0
        components["cash_to_mcap"] = cash_ratio
        # 5% = neutral, 15% = strong, 30%+ = excellent
        cash_score = max(0, min(100, cash_ratio * 100 / 30 * 100))
    else:
        components["cash_to_mcap"] = 0

    # 3. Asymmetric upside (52W positioning) — moved here per user spec
    upside_score = 50
    if pct_in_range >= 0:
        if pct_in_range <= 25:
            upside_score = 100  # near 52W lows = great asymmetric upside
        elif pct_in_range <= 50:
            upside_score = 75
        elif pct_in_range <= 70:
            upside_score = 50
        elif pct_in_range <= 85:
            upside_score = 30
        else:
            upside_score = 10  # near 52W highs = limited upside
    components["upside_score"] = upside_score

    # 4. Capex intensity (for industrials = capacity expansion = future revenue)
    capex_score = 50
    if snap.capex and snap.revenue and snap.revenue[0] > 0:
        capex_intensity = snap.capex[0] / snap.revenue[0]
        components["capex_intensity"] = capex_intensity
        sector_lower = (snap.sector or "").lower()
        if "industrial" in sector_lower or "energy" in sector_lower or "material" in sector_lower:
            # Industrial: 10%+ capex = capacity expansion
            capex_score = max(0, min(100, capex_intensity * 100 / 15 * 100))
        else:
            # Other sectors — capex less central
            capex_score = 50
    else:
        components["capex_intensity"] = 0

    # Weighted composite within O
    optionality_score = (
        0.35 * rd_score
        + 0.30 * upside_score
        + 0.20 * cash_score
        + 0.15 * capex_score
    )

    narrative_parts = []
    if components.get("rd_intensity", 0) > 0.10:
        narrative_parts.append(f"high R&D intensity ({components['rd_intensity']*100:.0f}%)")
    if components.get("cash_to_mcap", 0) > 0.15:
        narrative_parts.append(f"cash {components['cash_to_mcap']*100:.0f}% of mcap")
    if pct_in_range >= 0 and pct_in_range <= 30:
        narrative_parts.append("near 52W lows")
    elif pct_in_range >= 80:
        narrative_parts.append("at 52W highs")
    narrative = "; ".join(narrative_parts) or "limited optionality signal"

    return optionality_score, components, narrative


# ───────────────────────────────────────────────────────────────────────────
# RISK PENALTY LAYER
# ───────────────────────────────────────────────────────────────────────────

def _compute_risk_penalty(snap: FundamentalsSnapshot, market_cap: int) -> tuple:
    """
    Returns (penalty_0_to_1, narrative).

    Penalty is multiplicative on final score: final = base × (1 − penalty).
    Max penalty caps at 0.40 (60% of score retained even for risky names).
    """
    if not snap.has_data:
        return 0.0, ""

    penalty = 0.0
    reasons = []

    # 1. Leverage risk: net debt / EBITDA > 4×
    if snap.total_debt and snap.cash and snap.operating_income:
        net_debt = max(0, snap.total_debt[0] - snap.cash[0])
        ebitda_proxy = snap.operating_income[0]  # crude — ignore D&A
        if ebitda_proxy > 0:
            ndte = net_debt / ebitda_proxy
            if ndte > 6:
                penalty += 0.20
                reasons.append(f"high leverage ({ndte:.1f}× EBITDA)")
            elif ndte > 4:
                penalty += 0.10
                reasons.append(f"elevated leverage ({ndte:.1f}× EBITDA)")
        elif snap.total_debt[0] > 0 and ebitda_proxy <= 0:
            # Debt with no/negative EBITDA = serious risk
            penalty += 0.25
            reasons.append("debt without earnings to service it")

    # 2. Dilution risk: share count up > 5% YoY
    if snap.shares_outstanding and len(snap.shares_outstanding) >= 2:
        if snap.shares_outstanding[1] > 0:
            dilution = (snap.shares_outstanding[0] - snap.shares_outstanding[1]) / snap.shares_outstanding[1]
            if dilution > 0.10:
                penalty += 0.15
                reasons.append(f"heavy dilution (+{dilution*100:.0f}% shares)")
            elif dilution > 0.05:
                penalty += 0.07
                reasons.append(f"moderate dilution (+{dilution*100:.0f}% shares)")

    # 3. Cash burn: FCF negative AND cash << annual burn
    if snap.fcf and snap.cash and snap.fcf[0] < 0:
        annual_burn = abs(snap.fcf[0])
        if snap.cash[0] < annual_burn * 1.5:
            # Less than 18 months runway
            penalty += 0.25
            reasons.append(f"cash runway < 18 months")
        elif snap.cash[0] < annual_burn * 3:
            penalty += 0.10
            reasons.append("limited cash runway")

    # Cap total penalty
    penalty = min(0.40, penalty)
    narrative = "; ".join(reasons) if reasons else ""
    return penalty, narrative


# ───────────────────────────────────────────────────────────────────────────
# COMPOSITE — the one function called by the scoring engine
# ───────────────────────────────────────────────────────────────────────────

@dataclass
class MultibaggerScore:
    """Output of multibagger scoring for one ticker."""
    ticker: str
    has_fundamentals: bool

    # Component scores (0-100 each)
    moat_score: float
    flow_score: float
    growth_score: float
    optionality_score: float
    risk_penalty: float

    # Composite
    multibagger_score: float       # final 0-100, risk-adjusted

    # Phase label (FROM flow component)
    phase_label: str               # "Pre-discovery" / "Early discovery" / etc.

    # Narratives
    moat_narrative: str
    flow_narrative: str
    growth_narrative: str
    optionality_narrative: str
    risk_narrative: str
    overall_narrative: str         # combined, for "WHY" column in UI


def compute_multibagger(
    ticker: str,
    positioning_metrics: dict,
    latest_filer_count: int,
    inst_buyers: int,
    inst_sellers: int,
    pct_in_range: float,
    market_cap: int,
) -> MultibaggerScore:
    """
    Top-level entry. Pulls fundamentals, computes M/F/G/O, applies risk
    adjustment, returns full MultibaggerScore.
    """
    snap = _fetch_fundamentals(ticker)

    moat_score, moat_comp, moat_narr = _score_moat(snap)
    flow_score, flow_comp, flow_narr = _score_flow(
        positioning_metrics, latest_filer_count, inst_buyers, inst_sellers
    )
    growth_score, growth_comp, growth_narr = _score_growth(snap)
    opt_score, opt_comp, opt_narr = _score_optionality(snap, pct_in_range, market_cap)
    risk_penalty, risk_narr = _compute_risk_penalty(snap, market_cap)

    # Composite: M(35) + F(25) + G(25) + O(15), risk-adjusted
    base = 0.35 * moat_score + 0.25 * flow_score + 0.25 * growth_score + 0.15 * opt_score
    final = base * (1.0 - risk_penalty)
    final = max(0, min(100, final))

    phase = flow_comp.get("phase_label", "Unknown")

    # Overall narrative — the lead one displayed in the UI WHY column
    overall_parts = []
    if moat_score >= 70:
        overall_parts.append(f"Strong moat: {moat_narr}")
    elif moat_score >= 50:
        overall_parts.append(f"Decent moat: {moat_narr}")
    else:
        overall_parts.append(f"Weak moat: {moat_narr}")

    overall_parts.append(f"Flow phase: {phase}")
    if growth_score >= 70:
        overall_parts.append(f"Growth: {growth_narr}")

    if risk_penalty > 0.10:
        overall_parts.append(f"⚠️ Risk: {risk_narr}")

    if final >= 75 and phase in ("Early discovery", "Building"):
        overall_parts.append("👈 EMERGING multibagger candidate")
    elif final >= 75 and phase == "Mid-cycle":
        overall_parts.append("👈 Mid-cycle multibagger")

    overall = ". ".join(overall_parts) + "."

    return MultibaggerScore(
        ticker=ticker,
        has_fundamentals=snap.has_data,
        moat_score=round(moat_score, 1),
        flow_score=round(flow_score, 1),
        growth_score=round(growth_score, 1),
        optionality_score=round(opt_score, 1),
        risk_penalty=round(risk_penalty, 3),
        multibagger_score=round(final, 1),
        phase_label=phase,
        moat_narrative=moat_narr,
        flow_narrative=flow_narr,
        growth_narrative=growth_narr,
        optionality_narrative=opt_narr,
        risk_narrative=risk_narr,
        overall_narrative=overall,
    )


def enrich_with_multibagger(scores: list, parallel: int = 6) -> Dict[str, "MultibaggerScore"]:
    """
    Batch compute multibagger scores for a list of TickerScore objects.

    Threaded — fundamentals fetch is I/O-bound. Returns dict keyed by ticker.

    Failed lookups return a default MultibaggerScore with has_fundamentals=False
    and component scores at 50 (neutral) — never blocks the scanner.
    """
    if not scores:
        return {}

    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _one(s):
        try:
            metrics = {
                "persistence_quarters": s.persistence_quarters,
                "filer_count_delta": s.filer_count_delta,
                "concentration_hhi": s.concentration_hhi,
            }
            return s.ticker, compute_multibagger(
                ticker=s.ticker,
                positioning_metrics=metrics,
                latest_filer_count=s.latest_filer_count,
                inst_buyers=getattr(s, "inst_buyers", 0),
                inst_sellers=getattr(s, "inst_sellers", 0),
                pct_in_range=getattr(s, "pct_in_range", -1),
                market_cap=getattr(s, "market_cap", 0),
            )
        except Exception:
            return s.ticker, None

    results: Dict[str, MultibaggerScore] = {}
    with ThreadPoolExecutor(max_workers=min(parallel, len(scores))) as ex:
        futures = {ex.submit(_one, s): s for s in scores}
        for fut in as_completed(futures):
            try:
                ticker, mb = fut.result(timeout=60)
                if mb is not None:
                    results[ticker] = mb
            except Exception:
                pass

    return results
