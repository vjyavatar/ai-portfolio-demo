"""
r63.72.10 — Lens-based Multibagger Scanner.

Implements the institutional-grade architecture from the user spec:

    Three INDEPENDENT lenses, each with its own ranking math:
      Lens 1 — COMPOUNDERS              (moat + ROIC durability)
      Lens 2 — INSTITUTIONAL ACCUMULATION (ownership velocity + flow)
      Lens 3 — ASYMMETRIC OPTIONALITY    (technology inflection + survivability)

    Each row gets ONE primary lens classification + measurable metrics for
    each of: Regime, Flow, Quality, Optionality, Saturation.

Critical principles:
    - NO synthetic labels (Phase, Type, Stars dropped)
    - Measurable percentiles only — let the user infer state
    - Each lens produces DIFFERENT verdicts; no unified score
    - Conviction bands (HIGH / MEDIUM / LOW / INSUFFICIENT DATA) replace stars
    - When a metric isn't computable, return None (rendered as N/A)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import math
import statistics

# Reuse the existing fundamentals fetcher
from services.multibagger_scoring import (
    _fetch_fundamentals, FundamentalsSnapshot, _safe_float, _safe_div
)


# ─── Computable metrics helpers ─────────────────────────────────────────────

def _percentile(values: List[float], target: float) -> Optional[float]:
    """Return target's percentile rank within values (0-100). None if no values."""
    if not values:
        return None
    below = sum(1 for v in values if v < target)
    return 100.0 * below / len(values)


def _ownership_pct(latest_value_usd: int, market_cap: int) -> Optional[float]:
    """
    Institutional ownership saturation = aggregate 13F dollar value / mcap.
    Returns 0-100 percentage, or None if either input is missing.
    """
    if not market_cap or market_cap <= 0:
        return None
    if latest_value_usd <= 0:
        return 0.0
    pct = 100.0 * latest_value_usd / market_cap
    return min(100.0, pct)


def _ownership_velocity(value_delta_pct: float, share_delta_pct: float) -> float:
    """
    Combine value-delta and share-delta into a single velocity metric.
    Share-delta is cleaner (immune to price moves). Weighted 70/30.
    """
    return 0.7 * share_delta_pct + 0.3 * value_delta_pct


def _buy_sell_score(buyers: int, sellers: int) -> Optional[float]:
    """0-100 buy/sell dominance. None if too few active filers to be meaningful."""
    total = buyers + sellers
    if total < 10:
        return None
    return 100.0 * buyers / total


def _saturation_score(filer_count: int, market_cap_b: float) -> Optional[float]:
    """
    Institutional saturation as 0-100. Higher = more crowded.
    
    Insight: a company's "saturation level" is filer_count vs. expected
    coverage given its market cap. A $200B name with only 200 filers is
    deeply UNDER-covered (low saturation, not a multibagger setup either).
    A $200B name with 3000 filers is at saturation.
    
    Calibration anchored to real benchmarks:
      - $1T+ mega-cap typically has 3000+ filers → saturation 90+
      - $200B large-cap typically has 2000-2500 filers → saturation 50-70
      - $50B mid-large has ~1500 filers → saturation 50-70
      - $10B mid-cap has ~700 filers → saturation 50-70
      - $1B small-cap has ~200 filers → saturation 50-70
      - $200M micro-cap has ~50 filers → saturation 50-70
    """
    if filer_count <= 0:
        return 0.0

    if market_cap_b <= 0:
        # No mcap data → fall back to absolute filer count
        if filer_count >= 2000: return 90
        if filer_count >= 1000: return 75
        if filer_count >= 400: return 60
        if filer_count >= 150: return 40
        if filer_count >= 50: return 25
        return 10

    # Expected filer count by market cap (linear in log space, anchored to data)
    # log10(mcap_b) → expected_filers:
    #   0   ($1B)    → 200
    #   1   ($10B)   → 700
    #   2   ($100B)  → 2000
    #   3   ($1T)    → 3500
    log_mcap = math.log10(max(0.1, market_cap_b))
    expected = max(20, 100 + 1100 * log_mcap)

    # Saturation = ratio of actual to expected, mapped to 0-100
    # ratio = 0.10 → 5   (deeply under-covered)
    # ratio = 0.30 → 15  (under-covered)
    # ratio = 0.70 → 50  (slightly under-covered)
    # ratio = 1.00 → 70  (typical / saturated)
    # ratio = 1.30 → 85  (above typical)
    # ratio = 1.50+ → 95 (over-saturated)
    ratio = filer_count / expected
    if ratio >= 1.5:
        return 95
    elif ratio >= 1.3:
        return 85 + (ratio - 1.3) * 50
    elif ratio >= 1.0:
        return 70 + (ratio - 1.0) * 50
    elif ratio >= 0.7:
        return 50 + (ratio - 0.7) * 67
    elif ratio >= 0.4:
        return 25 + (ratio - 0.4) * 83
    elif ratio >= 0.2:
        return 10 + (ratio - 0.2) * 75
    else:
        return max(2, ratio * 50)


def _relative_strength_proxy(pct_in_range: float) -> Optional[float]:
    """
    Without sector ETF data, use 52W positioning as a relative-strength proxy.
    >75% of range = strong; <30% = weak. Returns 0-100.
    """
    if pct_in_range < 0:
        return None
    return pct_in_range  # already 0-100


def _conviction_band(score: Optional[float], confidence_inputs: int) -> str:
    """
    Convert a 0-100 score to a conviction band.
    confidence_inputs = how many of the underlying metrics had real data.
    More inputs = higher confidence.
    """
    if score is None or confidence_inputs < 2:
        return "INSUFFICIENT DATA"
    if score >= 75 and confidence_inputs >= 4:
        return "HIGH"
    if score >= 60 and confidence_inputs >= 3:
        return "HIGH"
    if score >= 50:
        return "MEDIUM"
    if score >= 30:
        return "LOW"
    return "AVOID"


# ─── Lens 1 — COMPOUNDERS ───────────────────────────────────────────────────

@dataclass
class CompounderMetrics:
    """Lens 1 output — for the Compounders ranking."""
    ticker: str
    quality_score: Optional[float] = None         # 0-100, the primary signal
    roic_median: Optional[float] = None           # decimal, e.g., 0.18 = 18%
    roic_stability: Optional[float] = None        # coefficient of variation
    gross_margin_floor: Optional[float] = None    # decimal
    fcf_consistency: Optional[float] = None       # 0-1, % of years FCF positive
    revenue_growth_consistency: Optional[float] = None  # std of YoY growth
    conviction: str = "INSUFFICIENT DATA"
    inputs_count: int = 0


def score_lens_compounder(snap: FundamentalsSnapshot) -> CompounderMetrics:
    """Quality of business — ROIC stability + margin durability + FCF compounding."""
    out = CompounderMetrics(ticker=snap.ticker)

    if not snap.has_data:
        return out

    inputs = 0

    # ROIC time series
    roics = []
    for i, op in enumerate(snap.operating_income):
        debt = snap.total_debt[i] if i < len(snap.total_debt) else 0
        equity = snap.total_equity[i] if i < len(snap.total_equity) else 0
        invested = debt + equity
        if invested > 0 and op != 0:
            roics.append(op * 0.79 / invested)

    if len(roics) >= 3:
        out.roic_median = statistics.median(roics)
        out.roic_stability = statistics.pstdev(roics) / abs(out.roic_median) if abs(out.roic_median) > 0.001 else None
        inputs += 1

    # Gross margin floor
    gms = []
    for i in range(min(len(snap.gross_profit), len(snap.revenue))):
        if snap.revenue[i] > 0:
            gms.append(snap.gross_profit[i] / snap.revenue[i])
    if gms:
        out.gross_margin_floor = min(gms)
        inputs += 1

    # FCF consistency
    if snap.fcf:
        positive_years = sum(1 for f in snap.fcf if f > 0)
        out.fcf_consistency = positive_years / len(snap.fcf)
        inputs += 1

    # Revenue growth consistency (lower std = more consistent compounder)
    if len(snap.revenue) >= 3:
        growth_rates = []
        for i in range(len(snap.revenue) - 1):
            if snap.revenue[i + 1] > 0:
                growth_rates.append((snap.revenue[i] - snap.revenue[i + 1]) / snap.revenue[i + 1])
        if growth_rates:
            out.revenue_growth_consistency = statistics.pstdev(growth_rates) if len(growth_rates) > 1 else 0
            inputs += 1

    # Composite quality score
    score = 0.0
    weight_total = 0.0

    if out.roic_median is not None:
        # 0% ROIC → 0; 12% → 50; 25%+ → 100
        roic_score = max(0, min(100, out.roic_median * 100 * 100 / 25))
        score += 0.40 * roic_score
        weight_total += 0.40

    if out.roic_stability is not None:
        # Low CV = stable. Penalty above CV=0.5
        stability_score = max(0, min(100, 100 - out.roic_stability * 80))
        score += 0.20 * stability_score
        weight_total += 0.20

    if out.gross_margin_floor is not None:
        # 0% → 0; 30% → 50; 60% → 100
        gm_score = max(0, min(100, out.gross_margin_floor * 100 * 100 / 60))
        score += 0.20 * gm_score
        weight_total += 0.20

    if out.fcf_consistency is not None:
        score += 0.20 * out.fcf_consistency * 100
        weight_total += 0.20

    if weight_total > 0:
        out.quality_score = score / weight_total
        out.inputs_count = inputs
        out.conviction = _conviction_band(out.quality_score, inputs)

    return out


# ─── Lens 2 — INSTITUTIONAL ACCUMULATION ────────────────────────────────────

@dataclass
class AccumulationMetrics:
    """Lens 2 output — for the Institutional Accumulation ranking."""
    ticker: str
    flow_score: Optional[float] = None             # primary signal: 0-100
    ownership_pct: Optional[float] = None           # institutional saturation
    ownership_velocity: Optional[float] = None      # Q-over-Q rate of change
    buy_sell_dominance: Optional[float] = None      # 0-100
    saturation: Optional[float] = None              # 0-100
    relative_strength: Optional[float] = None       # 0-100 (52W proxy)
    persistence_q: int = 0
    conviction: str = "INSUFFICIENT DATA"
    inputs_count: int = 0


def score_lens_accumulation(
    ticker: str,
    positioning_metrics: dict,
    latest_filer_count: int,
    inst_buyers: int,
    inst_sellers: int,
    market_cap: int,
    pct_in_range: float,
    latest_value_usd: int,
) -> AccumulationMetrics:
    """Smart-money flow — ownership velocity + buy/sell dominance + relative strength.
    
    Optimized to surface accumulation IN PROGRESS, not yet saturated.
    Penalizes already-crowded names; rewards velocity above baseline.
    """
    out = AccumulationMetrics(
        ticker=ticker,
        persistence_q=positioning_metrics.get("persistence_quarters", 0),
    )
    inputs = 0

    mcap_b = market_cap / 1e9 if market_cap > 0 else 0

    # 1. Ownership %  (inst dollars vs market cap)
    out.ownership_pct = _ownership_pct(latest_value_usd, market_cap)
    if out.ownership_pct is not None:
        inputs += 1

    # 2. Ownership velocity (combine value-delta and share-delta Q/Q)
    out.ownership_velocity = _ownership_velocity(
        positioning_metrics.get("value_delta_pct", 0),
        positioning_metrics.get("share_delta_pct", 0),
    )
    inputs += 1  # always have this from 13F

    # 3. Buy/sell dominance (existing inst_buyers vs inst_sellers)
    out.buy_sell_dominance = _buy_sell_score(inst_buyers, inst_sellers)
    if out.buy_sell_dominance is not None:
        inputs += 1

    # 4. Saturation (mcap-aware)
    out.saturation = _saturation_score(latest_filer_count, mcap_b)
    if out.saturation is not None:
        inputs += 1

    # 5. Relative strength (52W positioning as proxy)
    out.relative_strength = _relative_strength_proxy(pct_in_range)
    if out.relative_strength is not None:
        inputs += 1

    # COMPOSITE FLOW SCORE — Lens 2 specific weighting
    # Reward velocity, buy-side dominance, low saturation, high RS
    score = 0.0
    weight_total = 0.0

    # Velocity (most important): map -50% to +50% to 0-100
    velocity_score = max(0, min(100, 50 + out.ownership_velocity))
    score += 0.30 * velocity_score
    weight_total += 0.30

    if out.buy_sell_dominance is not None:
        score += 0.30 * out.buy_sell_dominance
        weight_total += 0.30

    if out.saturation is not None:
        # Lens 2 PENALIZES saturation — best at 30-50% saturation (rerating phase)
        # 0% = 50 (illiquid), 30-50% = 100 (sweet spot), 90%+ = 10 (saturated)
        sat = out.saturation
        if sat <= 30:
            sat_score = 50 + (sat / 30) * 50
        elif sat <= 60:
            sat_score = 100 - ((sat - 30) / 30) * 30  # 100 → 70
        elif sat <= 90:
            sat_score = 70 - ((sat - 60) / 30) * 50   # 70 → 20
        else:
            sat_score = 10
        score += 0.20 * sat_score
        weight_total += 0.20

    if out.relative_strength is not None:
        # For accumulation lens: RS > 50 = trending up = good
        score += 0.10 * out.relative_strength
        weight_total += 0.10

    # Persistence bonus
    persist_score = min(out.persistence_q, 6) / 6 * 100
    score += 0.10 * persist_score
    weight_total += 0.10

    if weight_total > 0:
        out.flow_score = score / weight_total

    # HARD VETO: if heavy distribution, cap flow score
    if (inst_buyers + inst_sellers) >= 20 and inst_sellers >= 3 * max(1, inst_buyers):
        if out.flow_score is not None:
            out.flow_score = min(out.flow_score, 25)

    out.inputs_count = inputs
    out.conviction = _conviction_band(out.flow_score, inputs)
    return out


# ─── Lens 3 — ASYMMETRIC OPTIONALITY ────────────────────────────────────────

@dataclass
class OptionalityMetrics:
    """Lens 3 output — for Asymmetric Optionality ranking."""
    ticker: str
    optionality_score: Optional[float] = None       # primary signal
    rd_intensity: Optional[float] = None             # decimal
    cash_to_mcap: Optional[float] = None             # decimal
    revenue_acceleration: Optional[float] = None     # change in growth rate
    survivability: Optional[float] = None            # months of cash runway proxy
    pct_in_range: float = -1
    conviction: str = "INSUFFICIENT DATA"
    inputs_count: int = 0


def score_lens_optionality(
    snap: FundamentalsSnapshot, pct_in_range: float, market_cap: int
) -> OptionalityMetrics:
    """Non-linear upside — innovation pipeline + cash runway + asymmetric entry."""
    out = OptionalityMetrics(ticker=snap.ticker, pct_in_range=pct_in_range)
    inputs = 0

    # 1. R&D intensity (innovation proxy)
    if snap.has_data and snap.rd_expense and snap.revenue and snap.revenue[0] > 0:
        out.rd_intensity = snap.rd_expense[0] / snap.revenue[0]
        inputs += 1

    # 2. Cash-to-mcap (war chest for optionality)
    if snap.has_data and snap.cash and market_cap > 0:
        out.cash_to_mcap = snap.cash[0] / market_cap
        inputs += 1

    # 3. Revenue acceleration (technology inflection)
    if snap.has_data and len(snap.quarterly_revenue) >= 4:
        qr = snap.quarterly_revenue
        recent_growth = (qr[0] - qr[1]) / qr[1] if qr[1] > 0 else 0
        prior_growth = (qr[2] - qr[3]) / qr[3] if qr[3] > 0 else 0
        out.revenue_acceleration = recent_growth - prior_growth
        inputs += 1

    # 4. Survivability (cash runway in months if FCF negative; else infinity)
    if snap.has_data and snap.cash and snap.fcf and snap.fcf[0] < 0:
        annual_burn = abs(snap.fcf[0])
        if annual_burn > 0:
            months = (snap.cash[0] / annual_burn) * 12
            out.survivability = min(months, 60)  # cap display at 60mo
        inputs += 1
    elif snap.has_data and snap.fcf and snap.fcf[0] >= 0:
        out.survivability = 60  # FCF positive = effectively infinite runway
        inputs += 1

    # 5. Asymmetric entry — 52W positioning
    has_52w = pct_in_range >= 0
    if has_52w:
        inputs += 1

    # COMPOSITE OPTIONALITY SCORE
    score = 0.0
    weight_total = 0.0

    if out.rd_intensity is not None:
        # Tech: 5% = floor, 15%+ = strong, 25%+ = excellent
        sector = (snap.sector or "").lower()
        if "tech" in sector or "communication" in sector:
            rd_score = max(0, min(100, out.rd_intensity * 100 * 100 / 25))
        elif "health" in sector or "pharma" in sector or "bio" in sector:
            rd_score = max(0, min(100, out.rd_intensity * 100 * 100 / 30))
        else:
            rd_score = max(0, min(100, out.rd_intensity * 100 * 100 / 10))
        score += 0.30 * rd_score
        weight_total += 0.30

    if out.revenue_acceleration is not None:
        # +5pp acceleration = 100, 0 = 50, -5pp = 0
        accel_score = max(0, min(100, 50 + out.revenue_acceleration * 1000))
        score += 0.25 * accel_score
        weight_total += 0.25

    if out.cash_to_mcap is not None:
        # 5% = 30, 15% = 70, 30%+ = 100
        cash_score = max(0, min(100, out.cash_to_mcap * 100 * 100 / 30))
        score += 0.15 * cash_score
        weight_total += 0.15

    if out.survivability is not None:
        # <12mo = 0, 24mo = 50, 60mo = 100
        surv_score = min(100, max(0, out.survivability * 100 / 60))
        score += 0.15 * surv_score
        weight_total += 0.15

    if has_52w:
        # Asymmetric upside: <30% of range = 100, >85% = 0
        if pct_in_range <= 25:
            upside = 100
        elif pct_in_range <= 50:
            upside = 75
        elif pct_in_range <= 70:
            upside = 50
        elif pct_in_range <= 85:
            upside = 30
        else:
            upside = 10
        score += 0.15 * upside
        weight_total += 0.15

    if weight_total > 0:
        out.optionality_score = score / weight_total

    out.inputs_count = inputs
    out.conviction = _conviction_band(out.optionality_score, inputs)
    return out


# ─── TOP-LEVEL ENTRY: compute all three lenses for a row ────────────────────

@dataclass
class LensScores:
    """All three lens results plus shared metrics for one ticker."""
    ticker: str
    has_fundamentals: bool

    # Lens results
    compounder: CompounderMetrics
    accumulation: AccumulationMetrics
    optionality: OptionalityMetrics

    # Shared display metrics (for the 7-column institutional layout)
    regime: str = "NEUTRAL"           # ACCUMULATION / DISTRIBUTION / NEUTRAL — derived
    saturation_pct: Optional[float] = None
    ownership_change_pct: Optional[float] = None
    revenue_acceleration_pct: Optional[float] = None  # percentile rank within universe


def compute_all_lenses(
    ticker: str,
    positioning_metrics: dict,
    latest_filer_count: int,
    inst_buyers: int,
    inst_sellers: int,
    pct_in_range: float,
    market_cap: int,
    latest_value_usd: int,
) -> LensScores:
    """Compute all three lens scores in one pass. Single fundamentals fetch."""
    snap = _fetch_fundamentals(ticker)

    comp = score_lens_compounder(snap)
    acc = score_lens_accumulation(
        ticker, positioning_metrics, latest_filer_count,
        inst_buyers, inst_sellers, market_cap, pct_in_range, latest_value_usd
    )
    opt = score_lens_optionality(snap, pct_in_range, market_cap)

    # Regime: derived from buy/sell + velocity
    regime = "NEUTRAL"
    total_active = inst_buyers + inst_sellers
    velocity = positioning_metrics.get("share_delta_pct", 0)
    if total_active >= 20:
        if inst_sellers >= 3 * max(1, inst_buyers):
            regime = "DISTRIBUTION"
        elif inst_buyers >= 1.5 * max(1, inst_sellers) and velocity > 0:
            regime = "ACCUMULATION"
    elif velocity > 15:
        regime = "ACCUMULATION"
    elif velocity < -15:
        regime = "DISTRIBUTION"

    return LensScores(
        ticker=ticker,
        has_fundamentals=snap.has_data,
        compounder=comp,
        accumulation=acc,
        optionality=opt,
        regime=regime,
        saturation_pct=acc.saturation,
        ownership_change_pct=acc.ownership_velocity,
    )


def enrich_with_lenses(scores: list, parallel: int = 8) -> Dict[str, LensScores]:
    """Batch-compute all lenses for a list of TickerScore objects."""
    if not scores:
        return {}

    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _one(s):
        try:
            metrics = {
                "persistence_quarters": s.persistence_quarters,
                "filer_count_delta": s.filer_count_delta,
                "concentration_hhi": s.concentration_hhi,
                "value_delta_pct": s.value_delta_pct,
                "share_delta_pct": s.share_delta_pct,
            }
            return s.ticker, compute_all_lenses(
                ticker=s.ticker,
                positioning_metrics=metrics,
                latest_filer_count=s.latest_filer_count,
                inst_buyers=getattr(s, "inst_buyers", 0),
                inst_sellers=getattr(s, "inst_sellers", 0),
                pct_in_range=getattr(s, "pct_in_range", -1),
                market_cap=getattr(s, "market_cap", 0),
                latest_value_usd=s.latest_value_usd,
            )
        except Exception:
            return s.ticker, None

    results: Dict[str, LensScores] = {}
    with ThreadPoolExecutor(max_workers=min(parallel, len(scores))) as ex:
        futures = {ex.submit(_one, s): s for s in scores}
        for fut in as_completed(futures):
            try:
                ticker, ls = fut.result(timeout=60)
                if ls is not None:
                    results[ticker] = ls
            except Exception:
                pass
    return results
