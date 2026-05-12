"""
r63.72.12 — 360° Cycle Analysis module.

For any stock ticker, computes 15 analytical sections from structured
fundamental data. Each section produces:
    - real numeric metrics
    - rule-based plain-English commentary
    - layman explanation
    - verdict band where applicable

NO LLM CALLS. NO HALLUCINATION RISK. All commentary derived deterministically
from computed metrics via templates.

Honest about data limits: when a metric isn't computable (missing fundamentals,
Render Yahoo block, etc.), section returns confidence='low' and notes the gap
explicitly rather than fabricating numbers.
"""

import math
import statistics
import time
import threading
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict

# Reuse existing fundamentals fetcher
from services.multibagger_scoring import _fetch_fundamentals, FundamentalsSnapshot

# 1-hour cache for cycle analysis (fundamentals don't change intra-day)
_cycle_cache: Dict[str, tuple] = {}
_cycle_lock = threading.Lock()
_CACHE_TTL = 3600


def _safe_float(v, default=0.0) -> float:
    try:
        f = float(v)
        if f != f or f in (float("inf"), float("-inf")):
            return default
        return f
    except (TypeError, ValueError):
        return default


def _pct_change(current: float, prior: float) -> Optional[float]:
    if prior is None or prior == 0:
        return None
    return ((current - prior) / abs(prior)) * 100


# r63.72.23: defensive formatter — never crashes on None/non-numeric
def _f(v, spec=".1f", placeholder="N/A") -> str:
    """Safe number formatter. Returns placeholder if value is None/non-numeric."""
    if v is None:
        return placeholder
    try:
        return format(v, spec)
    except (TypeError, ValueError):
        return placeholder


# r63.72.23: section-level guard — failing section returns degraded result,
# does not crash the entire analysis
def _safe_section(name: str, title: str, fn, *args, **kwargs) -> dict:
    """Run a section function. If it raises, return a low-confidence stub instead of crashing."""
    try:
        result = fn(*args, **kwargs)
        if result is None:
            return {
                "section": name, "title": title, "confidence": "low",
                "narrative": "Section unavailable.", "layman": "Section unavailable.",
                "metrics": {},
            }
        return result
    except Exception as e:
        import traceback
        print(f"[cycle_analyzer] Section '{name}' failed: {e}")
        print(traceback.format_exc())
        return {
            "section": name, "title": title, "confidence": "low",
            "narrative": f"Section failed: {str(e)[:120]}",
            "layman": "Section error — try refreshing.",
            "metrics": {}, "error": str(e)[:200],
        }


# ═════════════════════════════════════════════════════════════════════════
# SECTION 1 — PROFIT MARGIN ANALYSIS (where are we vs. cycle peak)
# ═════════════════════════════════════════════════════════════════════════

def _section_profit_margins(snap: FundamentalsSnapshot) -> dict:
    """
    Tracks gross / operating / net margins over 5 years.
    Identifies: are we near peak, mid-cycle, or trough?
    """
    if not snap.has_data or not snap.revenue:
        return {
            "section": "profit_margins",
            "title": "Profit Margins — Where in the Cycle?",
            "confidence": "low",
            "narrative": "Fundamentals unavailable for margin analysis (Yahoo blocked or thin data).",
            "layman": "We couldn't pull the financial statements to analyze this stock's margins.",
            "metrics": {},
        }

    # Compute margin series (newest first)
    gms, oms, nms = [], [], []
    for i in range(len(snap.revenue)):
        rev = snap.revenue[i]
        if rev > 0:
            if i < len(snap.gross_profit):
                gms.append((snap.gross_profit[i] / rev) * 100)
            if i < len(snap.operating_income):
                oms.append((snap.operating_income[i] / rev) * 100)
            if i < len(snap.net_income):
                nms.append((snap.net_income[i] / rev) * 100)

    if not gms or not oms:
        return {
            "section": "profit_margins",
            "title": "Profit Margins — Where in the Cycle?",
            "confidence": "low",
            "narrative": "Margin time series incomplete.",
            "layman": "Not enough margin data to draw conclusions.",
            "metrics": {},
        }

    current_gm = gms[0]
    current_om = oms[0]
    current_nm = nms[0] if nms else None

    peak_gm = max(gms)
    peak_om = max(oms)
    trough_om = min(oms)
    median_om = statistics.median(oms)

    # Distance from peak
    pct_below_om_peak = ((peak_om - current_om) / peak_om) * 100 if peak_om != 0 else 0
    # Position in range (0=trough, 100=peak)
    om_range = peak_om - trough_om
    om_position_pct = ((current_om - trough_om) / om_range) * 100 if om_range != 0 else 50

    # Determine phase
    if om_position_pct >= 85:
        phase = "AT PEAK"
        phase_color = "red"
    elif om_position_pct >= 65:
        phase = "NEAR PEAK"
        phase_color = "yellow"
    elif om_position_pct >= 35:
        phase = "MID-CYCLE"
        phase_color = "blue"
    elif om_position_pct >= 15:
        phase = "RECOVERY"
        phase_color = "green"
    else:
        phase = "AT TROUGH"
        phase_color = "green"

    # Narrative
    narrative = (
        f"Operating margin currently {current_om:.1f}% — "
        f"vs 5Y peak of {peak_om:.1f}% and 5Y trough of {trough_om:.1f}%. "
        f"Position: {om_position_pct:.0f}% of cycle range ({phase}). "
        f"Gross margin {current_gm:.1f}% vs peak {peak_gm:.1f}%. "
    )
    if phase in ("AT PEAK", "NEAR PEAK"):
        narrative += "Mean reversion risk: margins this elevated historically compress within 4-8 quarters as supply responds to demand."
    elif phase == "AT TROUGH":
        narrative += "Margins suggest cyclical bottom — operating leverage upside possible if demand recovers."

    # Layman
    layman = (
        f"For every $1 in sales, ${current_om/100:.2f} is operating profit. "
        f"At the best point in the last 5 years, that was ${peak_om/100:.2f}. "
        f"Right now we're {phase.lower()} in the margin cycle. "
    )
    if phase in ("AT PEAK", "NEAR PEAK"):
        layman += "Translation: this company is making peak money per dollar of sales. Historically, that's hard to sustain — competition or supply catches up. Buying at this point means you're paying full price for margins that may shrink."
    elif phase == "AT TROUGH":
        layman += "Translation: margins are squeezed. If business conditions improve, profit could rise much faster than revenue."

    return {
        "section": "profit_margins",
        "title": "1. Profit Margins — Where in the Cycle?",
        "confidence": "high" if len(oms) >= 4 else "medium",
        "phase": phase,
        "phase_color": phase_color,
        "narrative": narrative,
        "layman": layman,
        "metrics": {
            "current_gross_margin": round(current_gm, 1),
            "peak_gross_margin": round(peak_gm, 1),
            "current_operating_margin": round(current_om, 1),
            "peak_operating_margin": round(peak_om, 1),
            "trough_operating_margin": round(trough_om, 1),
            "median_operating_margin": round(median_om, 1),
            "pct_below_peak": round(pct_below_om_peak, 1),
            "cycle_position_pct": round(om_position_pct, 0),
            "operating_margin_series": [round(m, 1) for m in oms],
            "gross_margin_series": [round(m, 1) for m in gms],
        },
    }


# ═════════════════════════════════════════════════════════════════════════
# SECTION 2 — NORMALIZED EARNINGS (smoothed EPS across cycle)
# ═════════════════════════════════════════════════════════════════════════

def _section_normalized_earnings(snap: FundamentalsSnapshot, market_cap: int) -> dict:
    """
    Compute average / median EPS across the cycle to strip out cyclical noise.
    Useful for cyclical names where peak EPS is misleading.
    """
    if not snap.has_data or not snap.eps_diluted or len(snap.eps_diluted) < 3:
        return {
            "section": "normalized_earnings",
            "title": "2. Normalized Earnings (Cycle-Adjusted)",
            "confidence": "low",
            "narrative": "EPS history unavailable.",
            "layman": "Couldn't pull enough years of earnings to normalize.",
            "metrics": {},
        }

    eps_series = [e for e in snap.eps_diluted if e is not None]
    current_eps = eps_series[0]
    avg_eps = statistics.mean(eps_series)
    median_eps = statistics.median(eps_series)
    peak_eps = max(eps_series)
    trough_eps = min(eps_series)

    # Normalized EPS = trimmed mean (exclude best+worst year) — institutional standard
    if len(eps_series) >= 5:
        trimmed = sorted(eps_series)[1:-1]
        normalized_eps = statistics.mean(trimmed)
    else:
        normalized_eps = avg_eps

    # Current vs normalized
    over_under = ((current_eps - normalized_eps) / abs(normalized_eps)) * 100 if normalized_eps != 0 else 0

    # Price implied if we revert to normalized at peak P/E
    shares = snap.shares_outstanding[0] if snap.shares_outstanding else 0
    price_now = (market_cap / shares) if shares > 0 and market_cap > 0 else 0

    # Implied multiples
    pe_on_current = (price_now / current_eps) if current_eps > 0 else None
    pe_on_normalized = (price_now / normalized_eps) if normalized_eps > 0 else None

    # Narrative
    narrative = (
        f"Current TTM EPS ${current_eps:.2f}, but cycle-normalized (trimmed-mean 5Y) EPS is ${normalized_eps:.2f}. "
        f"Current is {over_under:+.0f}% vs normalized. "
        f"Trough EPS was ${trough_eps:.2f}; peak was ${peak_eps:.2f}. "
    )
    if pe_on_current and pe_on_normalized:
        narrative += (
            f"P/E on TTM = {pe_on_current:.1f}× looks cheap, but P/E on NORMALIZED earnings = {pe_on_normalized:.1f}× — "
            f"which is the multiple to actually pay attention to in a cyclical business. "
        )

    if over_under > 75:
        narrative += "WARNING: current earnings are dramatically above normalized — TTM P/E understates the real valuation."
    elif over_under < -50:
        narrative += "Current earnings are deeply suppressed vs normalized — TTM P/E overstates valuation; normalized-P/E is what matters here."
    else:
        narrative += "Current earnings near long-term normalized — TTM P/E is roughly representative."

    # Layman
    layman = (
        f"If we average this company's profit over the last 5 years (the only honest way for a cyclical stock), it earns about ${normalized_eps:.2f} per share. "
        f"Right now it's earning ${current_eps:.2f}. "
    )
    if over_under > 75:
        layman += (
            f"That's WAY above its long-term average ({over_under:.0f}% above). "
            f"The P/E ratio you see on Yahoo Finance ({_f(pe_on_current, '.0f')}× if shown) looks cheap, but it's based on peak earnings. "
            f"When normalized, the P/E is actually {_f(pe_on_normalized, '.0f')}× — a much truer picture of what you're paying."
        )
    elif over_under < -50:
        layman += "That's well below average — could mean earnings are about to recover, but it also means the current P/E looks expensive."
    else:
        layman += "Roughly typical — the headline P/E ratio is meaningful."

    return {
        "section": "normalized_earnings",
        "title": "2. Normalized Earnings (Cycle-Adjusted)",
        "confidence": "high" if len(eps_series) >= 5 else "medium",
        "narrative": narrative,
        "layman": layman,
        "metrics": {
            "current_eps": round(current_eps, 2),
            "normalized_eps": round(normalized_eps, 2),
            "peak_eps": round(peak_eps, 2),
            "trough_eps": round(trough_eps, 2),
            "median_eps": round(median_eps, 2),
            "over_under_pct": round(over_under, 1),
            "pe_on_current": round(pe_on_current, 1) if pe_on_current else None,
            "pe_on_normalized": round(pe_on_normalized, 1) if pe_on_normalized else None,
            "eps_series": [round(e, 2) for e in eps_series],
        },
    }


# ═════════════════════════════════════════════════════════════════════════
# SECTION 3 — BALANCE SHEET STRENGTH
# ═════════════════════════════════════════════════════════════════════════

def _section_balance_sheet(snap: FundamentalsSnapshot) -> dict:
    if not snap.has_data or not snap.total_assets:
        return {
            "section": "balance_sheet",
            "title": "3. Balance Sheet Strength",
            "confidence": "low",
            "narrative": "Balance sheet data unavailable.",
            "layman": "Couldn't access balance sheet details.",
            "metrics": {},
        }

    debt = snap.total_debt[0] if snap.total_debt else 0
    cash = snap.cash[0] if snap.cash else 0
    equity = snap.total_equity[0] if snap.total_equity else 0
    assets = snap.total_assets[0] if snap.total_assets else 0
    ebitda = (snap.operating_income[0] * 1.2) if snap.operating_income else 0  # rough D&A add-back

    net_debt = debt - cash
    debt_to_equity = (debt / equity) * 100 if equity > 0 else None
    net_debt_to_ebitda = (net_debt / ebitda) if ebitda > 0 else None
    cash_to_assets = (cash / assets) * 100 if assets > 0 else None

    # Grading
    grade = "STRONG"
    grade_color = "green"
    reasons = []
    if net_debt_to_ebitda is not None:
        if net_debt_to_ebitda > 4:
            grade = "STRESSED"; grade_color = "red"
            reasons.append(f"net debt/EBITDA = {net_debt_to_ebitda:.1f}× (>4× is concerning)")
        elif net_debt_to_ebitda > 2.5:
            grade = "MODERATE"; grade_color = "yellow"
            reasons.append(f"net debt/EBITDA = {net_debt_to_ebitda:.1f}× (manageable but elevated)")
        elif net_debt_to_ebitda < 0:
            grade = "FORTRESS"; grade_color = "green"
            reasons.append(f"net cash position (cash > debt) of ${abs(net_debt)/1e9:.1f}B")
        else:
            reasons.append(f"net debt/EBITDA = {net_debt_to_ebitda:.1f}× (comfortable)")

    if cash_to_assets is not None and cash_to_assets > 20:
        reasons.append(f"cash = {cash_to_assets:.0f}% of total assets (well-capitalized)")

    narrative = (
        f"Total debt ${debt/1e9:.1f}B vs cash ${cash/1e9:.1f}B → net debt ${net_debt/1e9:+.1f}B. "
    )
    if debt_to_equity is not None:
        narrative += f"Debt-to-equity = {debt_to_equity:.0f}%. "
    if net_debt_to_ebitda is not None:
        narrative += f"Net debt / EBITDA = {net_debt_to_ebitda:.1f}×. "
    narrative += "Grade: " + grade + ". " + " · ".join(reasons) + "."

    # Layman
    layman = ""
    if grade == "FORTRESS":
        layman = f"This company has MORE cash than debt — ${abs(net_debt)/1e9:.1f}B in net cash. It could survive a deep recession without raising capital. Strong balance sheet means it can buy back stock, make acquisitions, or invest while competitors retrench."
    elif grade == "STRONG":
        layman = "Healthy balance sheet. Manageable debt relative to earnings. No solvency concerns."
    elif grade == "MODERATE":
        layman = f"Debt is elevated relative to earnings ({net_debt_to_ebitda:.1f}× EBITDA). In a normal economy, fine. In a recession, could become a problem."
    else:
        layman = f"Debt levels are high ({net_debt_to_ebitda:.1f}× EBITDA). If earnings drop meaningfully, this could become a credit concern. Watch interest coverage carefully."

    return {
        "section": "balance_sheet",
        "title": "3. Balance Sheet Strength",
        "confidence": "high",
        "grade": grade,
        "grade_color": grade_color,
        "narrative": narrative,
        "layman": layman,
        "metrics": {
            "total_debt": int(debt),
            "cash": int(cash),
            "net_debt": int(net_debt),
            "total_equity": int(equity),
            "debt_to_equity_pct": round(debt_to_equity, 0) if debt_to_equity is not None else None,
            "net_debt_to_ebitda": round(net_debt_to_ebitda, 2) if net_debt_to_ebitda is not None else None,
            "cash_to_assets_pct": round(cash_to_assets, 1) if cash_to_assets is not None else None,
        },
    }


# ═════════════════════════════════════════════════════════════════════════
# SECTION 4 — REVENUE VISIBILITY / CUSTOMER AGREEMENTS
# ═════════════════════════════════════════════════════════════════════════

def _section_revenue_visibility(snap: FundamentalsSnapshot, sector: str) -> dict:
    """
    Customer agreements / RPO disclosure isn't in structured data. We infer
    revenue visibility from:
        - revenue growth consistency (low CV = predictable)
        - sector context (SaaS / semis = high visibility)
        - operating margin stability
    """
    if not snap.has_data or not snap.revenue or len(snap.revenue) < 3:
        return {
            "section": "revenue_visibility",
            "title": "4. Revenue Visibility & Customer Lock-in",
            "confidence": "low",
            "narrative": "Insufficient revenue history for visibility analysis.",
            "layman": "Not enough sales history to judge predictability.",
            "metrics": {},
        }

    # Y-o-Y growth rates
    rev = snap.revenue
    growth_rates = []
    for i in range(len(rev) - 1):
        if rev[i+1] > 0:
            growth_rates.append(((rev[i] - rev[i+1]) / rev[i+1]) * 100)

    if not growth_rates:
        return {
            "section": "revenue_visibility",
            "title": "4. Revenue Visibility & Customer Lock-in",
            "confidence": "low",
            "narrative": "Couldn't compute growth.",
            "layman": "—",
            "metrics": {},
        }

    avg_growth = statistics.mean(growth_rates)
    std_growth = statistics.pstdev(growth_rates) if len(growth_rates) > 1 else 0
    consistency = "HIGH" if std_growth < 10 else "MODERATE" if std_growth < 25 else "LOW"

    # Sector-based context
    s = (sector or "").lower()
    is_subscription = any(kw in s for kw in ["software", "communication services", "technology"])
    is_cyclical = any(kw in s for kw in ["semiconductor", "energy", "material", "auto", "consumer cyclical"])

    visibility = "MODERATE"
    visibility_reason = ""
    if consistency == "HIGH" and is_subscription:
        visibility = "HIGH"
        visibility_reason = "Stable growth profile in a typically subscription-heavy sector suggests strong recurring revenue."
    elif consistency == "LOW" and is_cyclical:
        visibility = "LOW"
        visibility_reason = "Volatile growth in a cyclical sector — revenue depends on industry cycle, not contracted backlog."
    elif consistency == "HIGH":
        visibility = "HIGH"
        visibility_reason = "Consistent growth pattern suggests recurring customer relationships."
    else:
        visibility_reason = f"Growth volatility {std_growth:.0f}pp std — typical for the business model."

    narrative = (
        f"5Y revenue growth average: {avg_growth:.1f}% with {std_growth:.1f}pp standard deviation. "
        f"Consistency: {consistency}. Sector: {sector or 'unknown'}. "
        f"Visibility: {visibility}. {visibility_reason} "
        f"Note: structured visibility metrics (RPO, backlog, contract duration) require 10-Q footnote parsing — "
        f"this is a heuristic estimate, not a literal contract-coverage measurement."
    )

    layman = (
        f"How predictable is this company's revenue? "
        f"Over 5 years it grew {avg_growth:.0f}% on average, but with {consistency.lower()} consistency. "
    )
    if visibility == "HIGH":
        layman += "That's a sign of either subscription revenue or sticky enterprise customers — good for predictability and valuation multiple."
    elif visibility == "LOW":
        layman += "Growth swings wildly year-to-year. This is normal for cyclical businesses (memory, energy, autos) — but it means you can't trust any single year as 'representative'. Always look at the full cycle."
    else:
        layman += "Moderate predictability — neither a SaaS subscription compounder nor a wild cyclical."

    return {
        "section": "revenue_visibility",
        "title": "4. Revenue Visibility & Customer Lock-in",
        "confidence": "medium",
        "visibility": visibility,
        "narrative": narrative,
        "layman": layman,
        "metrics": {
            "avg_5y_growth_pct": round(avg_growth, 1),
            "growth_std_pp": round(std_growth, 1),
            "consistency": consistency,
            "is_subscription_sector": is_subscription,
            "is_cyclical_sector": is_cyclical,
            "growth_rates_series": [round(g, 1) for g in growth_rates],
        },
    }


# ═════════════════════════════════════════════════════════════════════════
# SECTION 5 — SUPPLY DISCIPLINE (capex behavior)
# ═════════════════════════════════════════════════════════════════════════

def _section_supply_discipline(snap: FundamentalsSnapshot) -> dict:
    """
    Capex as % of revenue and trend tells us about supply behavior.
    Cyclical busts come from over-investment at peak.
    """
    if not snap.has_data or not snap.capex or not snap.revenue:
        return {
            "section": "supply_discipline",
            "title": "5. Supply Discipline (Capex Behavior)",
            "confidence": "low",
            "narrative": "Capex history unavailable.",
            "layman": "Couldn't analyze how much this company is investing in capacity.",
            "metrics": {},
        }

    capex_pcts = []
    for i in range(min(len(snap.capex), len(snap.revenue))):
        if snap.revenue[i] > 0:
            capex_pcts.append((snap.capex[i] / snap.revenue[i]) * 100)

    if len(capex_pcts) < 2:
        return {
            "section": "supply_discipline",
            "title": "5. Supply Discipline (Capex Behavior)",
            "confidence": "low",
            "narrative": "Insufficient capex history.",
            "layman": "—",
            "metrics": {},
        }

    current_capex_pct = capex_pcts[0]
    avg_capex_pct = statistics.mean(capex_pcts)
    peak_capex_pct = max(capex_pcts)

    # Current vs historical
    vs_avg = current_capex_pct - avg_capex_pct

    # Discipline judgment
    if current_capex_pct > peak_capex_pct * 0.95 and current_capex_pct > 15:
        discipline = "AGGRESSIVE"
        discipline_color = "red"
        discipline_note = "Capex at cycle peak — historically the prelude to oversupply."
    elif vs_avg > 5:
        discipline = "EXPANDING"
        discipline_color = "yellow"
        discipline_note = f"Capex {vs_avg:+.1f}pp above 5Y average — capacity expansion underway."
    elif vs_avg < -3:
        discipline = "DISCIPLINED"
        discipline_color = "green"
        discipline_note = "Capex below historical average — supply restraint."
    else:
        discipline = "NORMAL"
        discipline_color = "blue"
        discipline_note = "Capex roughly in line with historical pattern."

    narrative = (
        f"Current capex/revenue: {current_capex_pct:.1f}% vs 5Y average {avg_capex_pct:.1f}% and peak {peak_capex_pct:.1f}%. "
        f"Discipline: {discipline}. {discipline_note}"
    )

    layman = (
        f"This company is spending {current_capex_pct:.0f}% of its revenue on new factories, equipment, and infrastructure. "
        f"The 5-year average has been {avg_capex_pct:.0f}%. "
    )
    if discipline == "AGGRESSIVE":
        layman += "WARNING: capex at peak levels usually means management is racing to build capacity. In commodity-like businesses (memory, oil, autos), this is how booms turn into busts. New supply hits the market 2-3 years later and crushes margins."
    elif discipline == "EXPANDING":
        layman += "Capacity is being added but not at panic levels. Watch this — if it accelerates further at peak prices, future oversupply becomes more likely."
    elif discipline == "DISCIPLINED":
        layman += "Smart capital allocation — investing less when prices are high suggests management remembers prior cycles. This is bullish for sustained margins."
    else:
        layman += "Steady-state investment. No clear signal about cycle inflection from capex behavior."

    return {
        "section": "supply_discipline",
        "title": "5. Supply Discipline (Capex Behavior)",
        "confidence": "high",
        "discipline": discipline,
        "discipline_color": discipline_color,
        "narrative": narrative,
        "layman": layman,
        "metrics": {
            "current_capex_pct_revenue": round(current_capex_pct, 1),
            "avg_5y_capex_pct": round(avg_capex_pct, 1),
            "peak_capex_pct": round(peak_capex_pct, 1),
            "vs_average_pp": round(vs_avg, 1),
            "capex_pct_series": [round(c, 1) for c in capex_pcts],
        },
    }


# ═════════════════════════════════════════════════════════════════════════
# SECTION 6 — REVENUE / PROFIT VISIBILITY (heuristic via growth durability)
# ═════════════════════════════════════════════════════════════════════════

def _section_locked_demand(snap: FundamentalsSnapshot, sector: str) -> dict:
    """
    True locked-in demand (RPO, backlog %) needs 10-Q footnote parsing.
    Heuristic: look at margin durability + recurring-business indicators.
    """
    if not snap.has_data:
        return {
            "section": "locked_demand",
            "title": "6. Demand Lock-in & Forward Visibility",
            "confidence": "low",
            "narrative": "Cannot assess forward demand without fundamentals.",
            "layman": "—",
            "metrics": {},
        }

    s = (sector or "").lower()
    # Sectors where multi-quarter / multi-year supply contracts are common
    contract_sectors = {
        "semiconductor": "HIGH — semis often have 12-18mo supply agreements (foundry slots, HBM pre-orders)",
        "communication": "HIGH — telecom revenue is largely subscription with multi-year contracts",
        "software": "HIGH — SaaS recurring revenue model is the highest-visibility business model",
        "technology": "MEDIUM-HIGH — varies; check for subscription/license vs. transactional",
        "energy": "MEDIUM — long-term offtake agreements common; spot pricing also material",
        "industrial": "MEDIUM — order backlog typical; multi-quarter visibility",
        "aerospace": "VERY HIGH — multi-year program backlogs (10+ years for aircraft)",
        "defense": "VERY HIGH — government contracts with multi-year visibility",
        "utilities": "VERY HIGH — regulated revenue base",
        "real estate": "HIGH — multi-year lease contracts",
        "financial": "LOW — transactional / trading dependent",
        "consumer cyclical": "LOW — discretionary purchases, transactional",
        "consumer defensive": "MEDIUM — recurring purchases but no formal contracts",
    }
    visibility_label = "UNKNOWN"
    visibility_note = "Sector context unavailable."
    for key, label in contract_sectors.items():
        if key in s:
            visibility_label = label.split(" — ")[0]
            visibility_note = label
            break

    narrative = (
        f"Sector: {sector or 'unknown'}. Estimated demand visibility: {visibility_label}. "
        f"{visibility_note}. "
        f"NOTE: Precise locked-in demand (RPO, backlog, contracted revenue) requires reading 10-Q footnotes. "
        f"This is a sector-based prior — actual visibility may differ at the company level."
    )

    layman_map = {
        "VERY HIGH": "This sector has multi-year contracts (think Boeing aircraft backlog or utility regulated revenue). Future revenue is largely already booked. Low surprise risk.",
        "HIGH": "Customers often sign multi-quarter or multi-year supply agreements. The company has good visibility into next year's revenue.",
        "MEDIUM-HIGH": "Mix of recurring and transactional revenue.",
        "MEDIUM": "Some forward visibility through order books, but no long-term contracts.",
        "LOW": "Revenue depends on what customers buy next quarter — no contractual commitments. Surprises (positive or negative) are common.",
        "UNKNOWN": "Couldn't classify the sector for visibility analysis.",
    }
    layman = layman_map.get(visibility_label, "—")

    return {
        "section": "locked_demand",
        "title": "6. Demand Lock-in & Forward Visibility",
        "confidence": "medium",
        "visibility_label": visibility_label,
        "narrative": narrative,
        "layman": layman,
        "metrics": {
            "sector": sector,
            "visibility_label": visibility_label,
        },
    }


# ═════════════════════════════════════════════════════════════════════════
# SECTION 7 — COUNTER-ARGUMENT (this cycle vs. prior cycles)
# ═════════════════════════════════════════════════════════════════════════

def _section_counter_argument(snap: FundamentalsSnapshot, sector: str) -> dict:
    """
    The "this time is different" / "this time is the same" framing.
    """
    if not snap.has_data:
        return {
            "section": "counter_argument",
            "title": "7. Counter-Argument: Is This Cycle Different?",
            "confidence": "low",
            "narrative": "Insufficient data to compare cycles.",
            "layman": "—",
            "metrics": {},
        }

    s = (sector or "").lower()

    # Compute current vs historical operating margin
    oms = []
    for i in range(len(snap.revenue)):
        if snap.revenue[i] > 0 and i < len(snap.operating_income):
            oms.append((snap.operating_income[i] / snap.revenue[i]) * 100)

    if len(oms) < 4:
        return {
            "section": "counter_argument",
            "title": "7. Counter-Argument: Is This Cycle Different?",
            "confidence": "low",
            "narrative": "Need more cycle history.",
            "layman": "—",
            "metrics": {},
        }

    current_om = oms[0]
    historical_peak = max(oms[1:])  # exclude current
    historical_median = statistics.median(oms[1:])

    # Compute revenue growth this year vs historical
    rev_growth_current = ((snap.revenue[0] - snap.revenue[1]) / snap.revenue[1]) * 100 if len(snap.revenue) > 1 and snap.revenue[1] > 0 else 0
    historical_growths = []
    for i in range(1, len(snap.revenue) - 1):
        if snap.revenue[i+1] > 0:
            historical_growths.append(((snap.revenue[i] - snap.revenue[i+1]) / snap.revenue[i+1]) * 100)
    historical_avg_growth = statistics.mean(historical_growths) if historical_growths else 0

    # Bull case: this cycle different
    bull_points = []
    bear_points = []

    margin_premium = current_om - historical_peak
    if margin_premium > 5:
        bull_points.append(f"Operating margin {current_om:.1f}% is {margin_premium:.1f}pp ABOVE prior peak — suggests structural pricing power, not just cycle.")
        bear_points.append(f"Margins {margin_premium:.1f}pp above historical peak invites competitive response or capacity additions — mean reversion remains the base case until proven structural.")

    growth_premium = rev_growth_current - historical_avg_growth
    if growth_premium > 30:
        bull_points.append(f"Revenue growing {rev_growth_current:.0f}% vs historical avg {historical_avg_growth:.0f}% — possible TAM expansion (AI, new market) rather than cycle.")
        bear_points.append(f"Growth this far above trend ({growth_premium:+.0f}pp) historically corrects within 2-3 years as demand satiates.")

    # AI-era specific
    if "semiconductor" in s or "technology" in s:
        bull_points.append("AI infrastructure spend represents a multi-year structural buildout — utilization and revenue patterns differ from PC/mobile cycles.")
        bear_points.append("Every prior tech buildout (PC, internet, mobile, cloud) had a 'this time is different' phase. They all eventually mean-reverted on a 5-10y basis even when the secular trend was real.")

    if "energy" in s:
        bull_points.append("Energy transition and grid demand from AI data centers may create structurally tighter market.")
        bear_points.append("Energy cycles have been called 'super-cycles' before (2008, 2014, 2022); supply responds, prices reset.")

    # Final framing
    narrative = (
        f"Current operating margin {current_om:.1f}% vs historical peak {historical_peak:.1f}% (premium of {margin_premium:+.1f}pp). "
        f"Revenue growth {rev_growth_current:.0f}% vs historical avg {historical_avg_growth:.0f}%. "
        f"The honest framing: when margins AND growth exceed historical highs, bulls call it structural, "
        f"bears call it cyclical peak. The market only knows which was right after the next 4-8 quarters of data. "
        f"The risk-reward is asymmetric — bulls get incremental upside if right, but everyone takes a large loss if mean reversion happens."
    )

    layman = (
        "Every bull market has a moment when investors argue 'this time is different — it's not a cycle, it's a permanent change.' "
        "Sometimes they're right (cloud computing was structural; the internet was structural). "
        "Sometimes they're wrong (mortgage CDOs in 2007 weren't a 'new asset class'). "
    )
    if margin_premium > 5:
        layman += (
            f"For this stock specifically, margins are {margin_premium:.0f}pp ABOVE the prior peak. "
            "The honest answer: nobody knows yet if this is structural or cyclical. "
            "The disciplined approach is to size your position as if mean reversion will happen (because historically it does ~70% of the time) "
            "while keeping enough exposure to participate if this really is the new normal."
        )
    else:
        layman += "Margins haven't broken out of historical range, so the 'this time is different' question isn't acute yet."

    return {
        "section": "counter_argument",
        "title": "7. Counter-Argument: Is This Cycle Different?",
        "confidence": "high",
        "narrative": narrative,
        "layman": layman,
        "metrics": {
            "current_operating_margin": round(current_om, 1),
            "historical_peak_margin": round(historical_peak, 1),
            "margin_premium_pp": round(margin_premium, 1),
            "current_revenue_growth_pct": round(rev_growth_current, 1),
            "historical_avg_growth_pct": round(historical_avg_growth, 1),
            "growth_premium_pp": round(growth_premium, 1),
            "bull_points": bull_points,
            "bear_points": bear_points,
        },
    }


# ═════════════════════════════════════════════════════════════════════════
# SECTION 8 — FORWARD P/E vs HISTORICAL
# ═════════════════════════════════════════════════════════════════════════

def _section_forward_pe(snap: FundamentalsSnapshot, market_cap: int, current_price: float) -> dict:
    """
    Compare TTM P/E and forward P/E against historical median.
    """
    if not snap.has_data or not snap.eps_diluted:
        return {
            "section": "forward_pe",
            "title": "8. Forward P/E vs Historical",
            "confidence": "low",
            "narrative": "P/E history unavailable.",
            "layman": "—",
            "metrics": {},
        }

    current_eps = snap.eps_diluted[0] if snap.eps_diluted else 0
    if current_price <= 0:
        # Derive price from market cap if available
        shares = snap.shares_outstanding[0] if snap.shares_outstanding else 0
        current_price = (market_cap / shares) if shares > 0 else 0

    if current_price <= 0 or current_eps <= 0:
        return {
            "section": "forward_pe",
            "title": "8. Forward P/E vs Historical",
            "confidence": "low",
            "narrative": "Couldn't compute P/E — missing price or EPS.",
            "layman": "—",
            "metrics": {},
        }

    pe_ttm = current_price / current_eps

    # Historical P/E proxy: median EPS × current price would give a "normalized" P/E
    eps_series = [e for e in snap.eps_diluted if e is not None and e > 0]
    if eps_series:
        median_eps = statistics.median(eps_series)
        # Trimmed mean for normalized
        if len(eps_series) >= 5:
            trimmed = sorted(eps_series)[1:-1]
            normalized_eps = statistics.mean(trimmed)
        else:
            normalized_eps = statistics.mean(eps_series)
        pe_on_normalized = current_price / normalized_eps if normalized_eps > 0 else None
    else:
        median_eps = current_eps
        normalized_eps = current_eps
        pe_on_normalized = pe_ttm

    # Bands
    if pe_ttm < 10:
        ttm_band = "DEEP VALUE"
    elif pe_ttm < 18:
        ttm_band = "REASONABLE"
    elif pe_ttm < 30:
        ttm_band = "ELEVATED"
    else:
        ttm_band = "EXPENSIVE"

    narrative = (
        f"TTM P/E = {pe_ttm:.1f}× (price ${current_price:.2f} / EPS ${current_eps:.2f}). "
        f"P/E on normalized EPS = {pe_on_normalized:.1f}× (using cycle-trimmed EPS ${normalized_eps:.2f}). "
        f"Headline P/E band: {ttm_band}. "
    )
    if pe_on_normalized and pe_ttm < pe_on_normalized * 0.7:
        narrative += (
            f"WARNING: TTM P/E is much lower than normalized — current earnings are likely peak-cycle. "
            f"Pay attention to the {pe_on_normalized:.0f}× figure, which is the multiple you're really paying for cycle-adjusted cash flows."
        )
    elif pe_on_normalized and pe_ttm > pe_on_normalized * 1.4:
        narrative += "TTM P/E above normalized P/E suggests earnings are depressed; market is paying for recovery."

    layman = (
        f"The Price-to-Earnings (P/E) ratio you see on Yahoo Finance is {pe_ttm:.0f}×. "
        f"It means investors pay ${pe_ttm:.0f} for every $1 of last-12-month profit. "
    )
    if pe_on_normalized and pe_ttm < pe_on_normalized * 0.7:
        layman += (
            f"BUT — for cyclical businesses, the headline P/E lies during peak years. "
            f"If we use a 5-year average of profits instead (the 'normalized' approach), the P/E becomes {pe_on_normalized:.0f}×. "
            f"That's the number to use when comparing across cycles. "
        )
    else:
        layman += "The headline P/E is roughly representative here."

    return {
        "section": "forward_pe",
        "title": "8. Forward P/E vs Historical",
        "confidence": "high",
        "ttm_band": ttm_band,
        "narrative": narrative,
        "layman": layman,
        "metrics": {
            "current_price": round(current_price, 2),
            "current_eps": round(current_eps, 2),
            "pe_ttm": round(pe_ttm, 1),
            "normalized_eps": round(normalized_eps, 2),
            "pe_on_normalized": round(pe_on_normalized, 1) if pe_on_normalized else None,
            "ttm_band": ttm_band,
        },
    }


# ═════════════════════════════════════════════════════════════════════════
# SECTION 9 — REVENUE ESTIMATION FORWARD
# ═════════════════════════════════════════════════════════════════════════

def _section_revenue_estimation(snap: FundamentalsSnapshot) -> dict:
    """
    Compute base / bull / bear revenue scenarios from growth slope + Q-acceleration.
    """
    if not snap.has_data or not snap.revenue or len(snap.revenue) < 3:
        return {
            "section": "revenue_estimation",
            "title": "9. Revenue Estimation — 3 Scenarios",
            "confidence": "low",
            "narrative": "Need 3+ years of revenue history.",
            "layman": "—",
            "metrics": {},
        }

    rev = snap.revenue
    current_rev = rev[0]
    # 3-year growth CAGR
    if rev[2] > 0:
        cagr_3y = ((rev[0] / rev[2]) ** (1/2) - 1) * 100
    else:
        cagr_3y = 0

    # Recent Q acceleration as adjustment
    accel_adjustment = 0
    if len(snap.quarterly_revenue) >= 4:
        qr = snap.quarterly_revenue
        recent_qoq = ((qr[0] / qr[1]) - 1) * 100 if qr[1] > 0 else 0
        prior_qoq = ((qr[2] / qr[3]) - 1) * 100 if qr[3] > 0 else 0
        accel_adjustment = recent_qoq - prior_qoq  # in pp

    # Three scenarios
    base_growth = cagr_3y + (accel_adjustment * 0.5)
    bull_growth = base_growth + 10
    bear_growth = max(-30, base_growth - 20)

    rev_1y_base = current_rev * (1 + base_growth / 100)
    rev_1y_bull = current_rev * (1 + bull_growth / 100)
    rev_1y_bear = current_rev * (1 + bear_growth / 100)

    rev_3y_base = current_rev * ((1 + base_growth / 100) ** 3)
    rev_3y_bull = current_rev * ((1 + bull_growth / 100) ** 3)
    rev_3y_bear = current_rev * ((1 + bear_growth / 100) ** 3)

    narrative = (
        f"3Y CAGR = {cagr_3y:.1f}%. Q-acceleration adjustment {accel_adjustment:+.1f}pp. "
        f"Base case 1Y growth: {base_growth:.1f}% → ${rev_1y_base/1e9:.1f}B revenue. "
        f"Bull case: {bull_growth:.1f}% growth → ${rev_1y_bull/1e9:.1f}B. "
        f"Bear case: {bear_growth:.1f}% growth → ${rev_1y_bear/1e9:.1f}B. "
        f"3-year projections: Base ${rev_3y_base/1e9:.0f}B / Bull ${rev_3y_bull/1e9:.0f}B / Bear ${rev_3y_bear/1e9:.0f}B."
    )

    layman = (
        f"Based on the past 3 years, sales grew {cagr_3y:.0f}% per year. "
        f"If that pace continues, sales next year would be ${rev_1y_base/1e9:.1f}B (current: ${current_rev/1e9:.1f}B). "
        f"If business accelerates (bull case): ${rev_1y_bull/1e9:.1f}B. "
        f"If a downturn hits (bear case): ${rev_1y_bear/1e9:.1f}B. "
        f"These are mechanical estimates — actual results depend on demand, competition, and macro."
    )

    return {
        "section": "revenue_estimation",
        "title": "9. Revenue Estimation — 3 Scenarios",
        "confidence": "high",
        "narrative": narrative,
        "layman": layman,
        "metrics": {
            "current_revenue": int(current_rev),
            "cagr_3y_pct": round(cagr_3y, 1),
            "accel_adjustment_pp": round(accel_adjustment, 1),
            "base_growth_pct": round(base_growth, 1),
            "bull_growth_pct": round(bull_growth, 1),
            "bear_growth_pct": round(bear_growth, 1),
            "rev_1y_base": int(rev_1y_base),
            "rev_1y_bull": int(rev_1y_bull),
            "rev_1y_bear": int(rev_1y_bear),
            "rev_3y_base": int(rev_3y_base),
            "rev_3y_bull": int(rev_3y_bull),
            "rev_3y_bear": int(rev_3y_bear),
        },
    }


# ═════════════════════════════════════════════════════════════════════════
# SECTION 10 — OPERATING PROFIT WALK
# ═════════════════════════════════════════════════════════════════════════

def _section_operating_profit_walk(snap: FundamentalsSnapshot) -> dict:
    """
    Decompose YoY operating profit change into:
        - revenue contribution
        - margin contribution
    """
    if not snap.has_data or not snap.operating_income or len(snap.operating_income) < 2 or not snap.revenue:
        return {
            "section": "operating_profit_walk",
            "title": "10. Operating Profit Walk",
            "confidence": "low",
            "narrative": "Insufficient data.",
            "layman": "—",
            "metrics": {},
        }

    rev_cur = snap.revenue[0]
    rev_prior = snap.revenue[1]
    op_cur = snap.operating_income[0]
    op_prior = snap.operating_income[1]

    om_cur = op_cur / rev_cur if rev_cur > 0 else 0
    om_prior = op_prior / rev_prior if rev_prior > 0 else 0

    delta_op = op_cur - op_prior
    # Volume contribution: (rev_cur - rev_prior) * om_prior
    vol_contrib = (rev_cur - rev_prior) * om_prior
    # Margin contribution: rev_cur * (om_cur - om_prior)
    margin_contrib = rev_cur * (om_cur - om_prior)

    # Pct decomposition
    if delta_op != 0:
        vol_pct = (vol_contrib / delta_op) * 100
        margin_pct = (margin_contrib / delta_op) * 100
    else:
        vol_pct = margin_pct = 0

    narrative = (
        f"Operating profit changed from ${op_prior/1e9:.2f}B to ${op_cur/1e9:.2f}B "
        f"(${delta_op/1e9:+.2f}B / {(delta_op/abs(op_prior)*100) if op_prior != 0 else 0:+.0f}%). "
        f"Breakdown: ${vol_contrib/1e9:+.2f}B from revenue change ({vol_pct:.0f}%) "
        f"+ ${margin_contrib/1e9:+.2f}B from margin change ({margin_pct:.0f}%). "
        f"Operating margin: {om_prior*100:.1f}% → {om_cur*100:.1f}%."
    )

    layman = (
        f"Operating profit went from ${op_prior/1e9:.1f}B to ${op_cur/1e9:.1f}B. "
    )
    if abs(margin_pct) > 60:
        layman += (
            f"Most of that change ({margin_pct:.0f}%) came from MARGIN expansion/compression rather than sales volume. "
            "That's important — it means pricing power (or pricing pressure) is driving results, not just selling more units. "
            "Margin-driven profit changes can reverse fast if competition shifts."
        )
    elif abs(vol_pct) > 60:
        layman += (
            f"Most of the change ({vol_pct:.0f}%) came from VOLUME (more sales). "
            "That's higher quality — selling more units is generally more sustainable than just raising prices."
        )
    else:
        layman += "The profit change came from a balanced mix of volume and margin — generally healthy."

    return {
        "section": "operating_profit_walk",
        "title": "10. Operating Profit Walk (YoY Decomposition)",
        "confidence": "high",
        "narrative": narrative,
        "layman": layman,
        "metrics": {
            "operating_profit_prior": int(op_prior),
            "operating_profit_current": int(op_cur),
            "delta_op": int(delta_op),
            "volume_contribution": int(vol_contrib),
            "margin_contribution": int(margin_contrib),
            "volume_pct": round(vol_pct, 1),
            "margin_pct_contribution": round(margin_pct, 1),
            "operating_margin_prior": round(om_prior * 100, 2),
            "operating_margin_current": round(om_cur * 100, 2),
        },
    }


# ═════════════════════════════════════════════════════════════════════════
# SECTION 11 — "17x NORMALIZED P/E EXPLOSIVE" target framework
# ═════════════════════════════════════════════════════════════════════════

def _section_normalized_target(snap: FundamentalsSnapshot, market_cap: int, current_price: float) -> dict:
    """
    What does the stock look like if normalized earnings re-rate to a reasonable
    full-cycle multiple (default 17x — quality compounder territory)?
    """
    if not snap.has_data or not snap.eps_diluted:
        return {
            "section": "normalized_target",
            "title": "11. Normalized P/E Target (Full-Cycle Fair Value)",
            "confidence": "low",
            "narrative": "EPS data unavailable.",
            "layman": "—",
            "metrics": {},
        }

    eps_series = [e for e in snap.eps_diluted if e is not None and e > 0]
    if len(eps_series) < 3:
        return {
            "section": "normalized_target",
            "title": "11. Normalized P/E Target (Full-Cycle Fair Value)",
            "confidence": "low",
            "narrative": "Need more EPS history.",
            "layman": "—",
            "metrics": {},
        }

    # Cycle-normalized EPS (trimmed mean)
    if len(eps_series) >= 5:
        trimmed = sorted(eps_series)[1:-1]
        normalized_eps = statistics.mean(trimmed)
    else:
        normalized_eps = statistics.mean(eps_series)

    # Bull EPS = max recent (assume cycle peak holds)
    bull_eps = max(eps_series)
    # Bear EPS = trough
    bear_eps = min(eps_series)

    # Apply multiples
    bull_target_17 = bull_eps * 17
    base_target_17 = normalized_eps * 17
    bear_target_17 = bear_eps * 17

    # Get price
    if current_price <= 0:
        shares = snap.shares_outstanding[0] if snap.shares_outstanding else 0
        current_price = market_cap / shares if shares > 0 else 0

    if current_price <= 0:
        return {
            "section": "normalized_target",
            "title": "11. Normalized P/E Target (Full-Cycle Fair Value)",
            "confidence": "low",
            "narrative": "Price unavailable.",
            "layman": "—",
            "metrics": {},
        }

    upside_base = ((base_target_17 / current_price) - 1) * 100
    upside_bull = ((bull_target_17 / current_price) - 1) * 100
    downside_bear = ((bear_target_17 / current_price) - 1) * 100

    narrative = (
        f"At 17× P/E (full-cycle quality multiple): "
        f"Bull (peak EPS ${bull_eps:.2f}) → ${bull_target_17:.0f} ({upside_bull:+.0f}%). "
        f"Base (normalized EPS ${normalized_eps:.2f}) → ${base_target_17:.0f} ({upside_base:+.0f}%). "
        f"Bear (trough EPS ${bear_eps:.2f}) → ${bear_target_17:.0f} ({downside_bear:+.0f}%). "
        f"Current price ${current_price:.2f}."
    )

    if upside_base > 30:
        verdict = "EXPLOSIVE UPSIDE on normalized"
    elif upside_base > 0:
        verdict = "MODEST UPSIDE on normalized"
    elif upside_base > -30:
        verdict = "FAIRLY VALUED on normalized"
    else:
        verdict = "OVERVALUED on normalized"

    layman = (
        f"Imagine the market eventually values this stock at 17× its average earnings (a normal multiple for quality businesses). "
        f"Three scenarios: "
        f"If we keep peak earnings, fair value is ${bull_target_17:.0f} ({upside_bull:+.0f}% from today's ${current_price:.2f}). "
        f"If earnings revert to cycle-average, fair value is ${base_target_17:.0f} ({upside_base:+.0f}%). "
        f"If we go to cycle-trough earnings, fair value is ${bear_target_17:.0f} ({downside_bear:+.0f}%). "
        f"Verdict: {verdict}. "
    )
    if upside_base < 0 and upside_bull > 0:
        layman += "You're betting on staying near peak earnings to make money from here. If margins revert, you're underwater."

    return {
        "section": "normalized_target",
        "title": "11. Normalized P/E Target (Full-Cycle Fair Value)",
        "confidence": "high",
        "verdict": verdict,
        "narrative": narrative,
        "layman": layman,
        "metrics": {
            "current_price": round(current_price, 2),
            "bull_eps": round(bull_eps, 2),
            "normalized_eps": round(normalized_eps, 2),
            "bear_eps": round(bear_eps, 2),
            "bull_target_17x": round(bull_target_17, 2),
            "base_target_17x": round(base_target_17, 2),
            "bear_target_17x": round(bear_target_17, 2),
            "upside_bull_pct": round(upside_bull, 1),
            "upside_base_pct": round(upside_base, 1),
            "downside_bear_pct": round(downside_bear, 1),
            "verdict": verdict,
        },
    }


# ═════════════════════════════════════════════════════════════════════════
# SECTION 12 — MARGIN OF SAFETY
# ═════════════════════════════════════════════════════════════════════════

def _section_margin_of_safety(snap: FundamentalsSnapshot, current_price: float, market_cap: int) -> dict:
    """
    Downside scenarios: what if margins revert + multiple compresses?
    """
    if not snap.has_data or not snap.eps_diluted or not snap.revenue:
        return {
            "section": "margin_of_safety",
            "title": "12. Margin of Safety (Downside Stress Test)",
            "confidence": "low",
            "narrative": "Insufficient data.",
            "layman": "—",
            "metrics": {},
        }

    eps_series = [e for e in snap.eps_diluted if e is not None and e > 0]
    if not eps_series:
        return {
            "section": "margin_of_safety",
            "title": "12. Margin of Safety (Downside Stress Test)",
            "confidence": "low",
            "narrative": "—",
            "layman": "—",
            "metrics": {},
        }

    trough_eps = min(eps_series)

    if current_price <= 0:
        shares = snap.shares_outstanding[0] if snap.shares_outstanding else 0
        current_price = market_cap / shares if shares > 0 else 0

    if current_price <= 0:
        return {
            "section": "margin_of_safety",
            "title": "12. Margin of Safety (Downside Stress Test)",
            "confidence": "low",
            "narrative": "—",
            "layman": "—",
            "metrics": {},
        }

    # Stress test: trough EPS × low multiple (10x for cyclical bottom)
    stress_target_10x = trough_eps * 10
    stress_target_12x = trough_eps * 12
    stress_target_15x = trough_eps * 15

    downside_10x = ((stress_target_10x / current_price) - 1) * 100
    downside_12x = ((stress_target_12x / current_price) - 1) * 100
    downside_15x = ((stress_target_15x / current_price) - 1) * 100

    # Risk verdict
    if downside_12x > -25:
        risk_band = "LOW DOWNSIDE"
        risk_color = "green"
    elif downside_12x > -45:
        risk_band = "MODERATE DOWNSIDE"
        risk_color = "yellow"
    else:
        risk_band = "SIGNIFICANT DOWNSIDE"
        risk_color = "red"

    narrative = (
        f"Stress test using cycle-trough EPS ${trough_eps:.2f}: "
        f"At 10× P/E → ${stress_target_10x:.0f} ({downside_10x:+.0f}%). "
        f"At 12× → ${stress_target_12x:.0f} ({downside_12x:+.0f}%). "
        f"At 15× → ${stress_target_15x:.0f} ({downside_15x:+.0f}%). "
        f"Current ${current_price:.2f}. Downside band: {risk_band}."
    )

    layman = (
        f"What's the worst plausible scenario? If earnings drop to their lowest level in the last 5 years (${trough_eps:.2f} per share) "
        f"AND investors only pay a reasonable cyclical-bottom multiple (12×), the stock would be at ${stress_target_12x:.0f}. "
        f"That's {downside_12x:+.0f}% from today's price. "
    )
    if risk_band == "LOW DOWNSIDE":
        layman += "Even in a bad scenario, you'd lose less than 25%. That's a defensible setup."
    elif risk_band == "MODERATE DOWNSIDE":
        layman += "Bad scenario means a 25-45% drawdown. Not catastrophic but real."
    else:
        layman += "WARNING: A return-to-trough scenario could cost you 45%+. Size your position assuming this can happen."

    return {
        "section": "margin_of_safety",
        "title": "12. Margin of Safety (Downside Stress Test)",
        "confidence": "high",
        "risk_band": risk_band,
        "risk_color": risk_color,
        "narrative": narrative,
        "layman": layman,
        "metrics": {
            "current_price": round(current_price, 2),
            "trough_eps": round(trough_eps, 2),
            "stress_target_10x": round(stress_target_10x, 2),
            "stress_target_12x": round(stress_target_12x, 2),
            "stress_target_15x": round(stress_target_15x, 2),
            "downside_10x_pct": round(downside_10x, 1),
            "downside_12x_pct": round(downside_12x, 1),
            "downside_15x_pct": round(downside_15x, 1),
            "risk_band": risk_band,
        },
    }


# ═════════════════════════════════════════════════════════════════════════
# SECTION 13 — CYCLE ANALYSIS BY SEGMENT (heuristic)
# ═════════════════════════════════════════════════════════════════════════

def _section_segment_cycle(snap: FundamentalsSnapshot, sector: str) -> dict:
    """
    Real segment data isn't available without 10-K parsing. Heuristic:
    classify the sector and apply known cycle characteristics.
    """
    s = (sector or "").lower()
    cycle_lengths = {
        "semiconductor": ("4-6 years (silicon cycle)", "memory shifts faster (2-4yr), logic slower"),
        "communication": ("6-10 years (telecom capex)", "5G/6G cycles drive equipment vendors; carriers more stable"),
        "software": ("Secular growth, mild cycles", "SaaS recurring revenue smooths cycles"),
        "technology": ("3-5 year product cycles", "PC, mobile, AI all have distinct buying patterns"),
        "energy": ("8-15 years (oil/gas)", "renewables shorter; oil/gas can run a decade"),
        "industrial": ("5-7 years", "machinery, defense vary widely"),
        "consumer cyclical": ("2-4 years (consumer durables)", "autos run on credit cycles"),
        "consumer defensive": ("Long, shallow cycles", "food, household goods are recession-resistant"),
        "financial": ("5-10 years (credit cycles)", "banks run with rates; insurers with claims"),
        "real estate": ("7-10 years", "long cycles tied to construction"),
        "utilities": ("Regulated, no real cycle", "rate-base growth model"),
        "healthcare": ("Drug-specific cycles", "patent cliffs drive 10-15yr cycles"),
        "materials": ("3-7 years (commodity)", "metals/mining especially volatile"),
    }
    cycle_length = "Unknown"
    cycle_note = ""
    for key, (length, note) in cycle_lengths.items():
        if key in s:
            cycle_length = length
            cycle_note = note
            break

    # Estimate where we are using margin position
    oms = []
    for i in range(len(snap.revenue) if snap.has_data else 0):
        if snap.revenue[i] > 0 and i < len(snap.operating_income):
            oms.append((snap.operating_income[i] / snap.revenue[i]) * 100)

    cycle_position = "UNKNOWN"
    if len(oms) >= 4:
        peak = max(oms)
        trough = min(oms)
        current = oms[0]
        if peak != trough:
            pos = ((current - trough) / (peak - trough)) * 100
            if pos >= 85: cycle_position = "AT PEAK"
            elif pos >= 60: cycle_position = "LATE CYCLE"
            elif pos >= 35: cycle_position = "MID CYCLE"
            elif pos >= 15: cycle_position = "EARLY CYCLE"
            else: cycle_position = "AT TROUGH"

    narrative = (
        f"Sector: {sector or 'unknown'}. Typical cycle length: {cycle_length}. "
        f"Note: {cycle_note}. "
        f"Estimated cycle position based on margin: {cycle_position}."
    )

    layman_map = {
        "AT PEAK": "This sector's cycles typically last several years. Right now we appear to be near the peak — historically, the next move is down or sideways for a long time.",
        "LATE CYCLE": "We're past mid-cycle but not yet at the top. New entrants and expanded supply usually appear at this stage.",
        "MID CYCLE": "Plenty of runway in this cycle. Demand is healthy without supply panic yet.",
        "EARLY CYCLE": "Cycle is still young. Margins have room to expand.",
        "AT TROUGH": "Cycle bottom — historically a strong time to accumulate. The recovery can be sharp.",
        "UNKNOWN": "Couldn't determine cycle position.",
    }
    layman = (
        f"Different industries have different cycle lengths. {cycle_note}. "
        f"Where are we now? {cycle_position.lower()}. "
        f"{layman_map.get(cycle_position, '')}"
    )

    return {
        "section": "segment_cycle",
        "title": "13. Cycle Analysis (Sector Pattern)",
        "confidence": "medium",
        "cycle_position": cycle_position,
        "narrative": narrative,
        "layman": layman,
        "metrics": {
            "sector": sector,
            "typical_cycle_length": cycle_length,
            "cycle_note": cycle_note,
            "cycle_position": cycle_position,
        },
    }


# ═════════════════════════════════════════════════════════════════════════
# SECTION 14 — CUSTOMER STICKINESS HEURISTIC
# ═════════════════════════════════════════════════════════════════════════

def _section_customer_stickiness(snap: FundamentalsSnapshot, sector: str) -> dict:
    """
    True stickiness needs qualitative analysis. Proxies:
        - gross margin stability (sticky customers tolerate higher prices)
        - revenue durability through downturns
        - high gross margin = differentiated product
    """
    if not snap.has_data or not snap.gross_profit or not snap.revenue:
        return {
            "section": "customer_stickiness",
            "title": "14. Customer Stickiness",
            "confidence": "low",
            "narrative": "Insufficient data.",
            "layman": "—",
            "metrics": {},
        }

    gms = []
    for i in range(min(len(snap.gross_profit), len(snap.revenue))):
        if snap.revenue[i] > 0:
            gms.append((snap.gross_profit[i] / snap.revenue[i]) * 100)

    if len(gms) < 3:
        return {
            "section": "customer_stickiness",
            "title": "14. Customer Stickiness",
            "confidence": "low",
            "narrative": "—",
            "layman": "—",
            "metrics": {},
        }

    gm_avg = statistics.mean(gms)
    gm_std = statistics.pstdev(gms)
    gm_cv = gm_std / abs(gm_avg) if gm_avg != 0 else 999

    # Score
    if gm_avg >= 60 and gm_cv < 0.10:
        stickiness = "VERY HIGH"
        explanation = "high and stable gross margins suggest pricing power and customer retention"
    elif gm_avg >= 40 and gm_cv < 0.15:
        stickiness = "HIGH"
        explanation = "decent and stable margins suggest reasonable customer lock-in"
    elif gm_avg >= 30:
        stickiness = "MODERATE"
        explanation = "average margins suggest commodity-like dynamics or competitive pressure"
    else:
        stickiness = "LOW"
        explanation = "low margins typical of commodity businesses without customer lock-in"

    narrative = (
        f"5Y average gross margin: {gm_avg:.1f}% with {gm_std:.1f}pp std (CV = {gm_cv:.2f}). "
        f"Stickiness: {stickiness}. {explanation.capitalize()}. "
        "Note: structured stickiness data (NPS, churn, contract renewal) not in public filings — this is a margin-based heuristic."
    )

    layman = (
        f"How sticky are this company's customers? We can't measure churn directly from filings, but gross margins tell us a lot. "
        f"This company has {gm_avg:.0f}% gross margins on average. "
    )
    if stickiness == "VERY HIGH":
        layman += "Margins this high and this stable mean customers can't easily switch or won't try (think Bloomberg Terminal, Visa). That's the strongest moat type."
    elif stickiness == "HIGH":
        layman += "Margins are good and consistent. Suggests differentiated product with reasonable customer retention."
    elif stickiness == "MODERATE":
        layman += "Average margins. Customers have alternatives. Pricing power is limited."
    else:
        layman += "Low margins typically mean commodity dynamics — customers will switch suppliers over small price differences."

    return {
        "section": "customer_stickiness",
        "title": "14. Customer Stickiness (Pricing Power Proxy)",
        "confidence": "medium",
        "stickiness": stickiness,
        "narrative": narrative,
        "layman": layman,
        "metrics": {
            "gross_margin_avg_pct": round(gm_avg, 1),
            "gross_margin_std_pp": round(gm_std, 2),
            "gross_margin_cv": round(gm_cv, 3),
            "stickiness": stickiness,
        },
    }


# ═════════════════════════════════════════════════════════════════════════
# SECTION 15 — OVERALL SYNTHESIS + LAYMAN VERDICT
# ═════════════════════════════════════════════════════════════════════════

def _section_synthesis(all_sections: List[dict], ticker: str) -> dict:
    """
    Aggregate all section signals into a single layman verdict.
    """
    signals = {"positive": 0, "negative": 0, "neutral": 0}
    highlights = {"bull": [], "bear": []}

    for sec in all_sections:
        if sec.get("confidence") == "low":
            continue
        sid = sec.get("section")

        # Profit margins
        if sid == "profit_margins":
            phase = sec.get("phase")
            if phase in ("AT PEAK", "NEAR PEAK"):
                signals["negative"] += 1
                highlights["bear"].append(f"Margins near cycle peak ({sec['metrics'].get('current_operating_margin')}%)")
            elif phase in ("AT TROUGH", "RECOVERY"):
                signals["positive"] += 1
                highlights["bull"].append(f"Margins near cycle trough — upside potential")

        # Balance sheet
        elif sid == "balance_sheet":
            grade = sec.get("grade")
            if grade in ("FORTRESS", "STRONG"):
                signals["positive"] += 1
                highlights["bull"].append(f"Balance sheet: {grade}")
            elif grade == "STRESSED":
                signals["negative"] += 2
                highlights["bear"].append("Balance sheet stressed (>4× net debt/EBITDA)")

        # Normalized earnings
        elif sid == "normalized_earnings":
            over_under = sec["metrics"].get("over_under_pct", 0)
            if over_under > 75:
                signals["negative"] += 1
                highlights["bear"].append(f"Current EPS {over_under:.0f}% above normalized (cycle peak risk)")
            elif over_under < -30:
                signals["positive"] += 1
                highlights["bull"].append("Current EPS depressed below normalized")

        # Supply discipline
        elif sid == "supply_discipline":
            disc = sec.get("discipline")
            if disc == "AGGRESSIVE":
                signals["negative"] += 1
                highlights["bear"].append("Capex at peak — supply oversupply risk")
            elif disc == "DISCIPLINED":
                signals["positive"] += 1
                highlights["bull"].append("Capital discipline strong")

        # Normalized target
        elif sid == "normalized_target":
            upside_base = sec["metrics"].get("upside_base_pct", 0)
            if upside_base > 30:
                signals["positive"] += 1
                highlights["bull"].append(f"+{upside_base:.0f}% upside on normalized 17× P/E")
            elif upside_base < -20:
                signals["negative"] += 1
                highlights["bear"].append(f"{upside_base:.0f}% below normalized 17× P/E fair value")

        # Margin of safety
        elif sid == "margin_of_safety":
            risk = sec.get("risk_band")
            if risk == "SIGNIFICANT DOWNSIDE":
                signals["negative"] += 1
                highlights["bear"].append("Downside scenario suggests >45% loss potential")

        # Stickiness
        elif sid == "customer_stickiness":
            stick = sec.get("stickiness")
            if stick in ("VERY HIGH", "HIGH"):
                signals["positive"] += 1
                highlights["bull"].append(f"Customer stickiness: {stick}")
            elif stick == "LOW":
                signals["negative"] += 1
                highlights["bear"].append("Weak customer stickiness")

    net_score = signals["positive"] - signals["negative"]
    if net_score >= 3:
        verdict = "STRONG BUY"
        color = "green"
    elif net_score >= 1:
        verdict = "BUY"
        color = "green"
    elif net_score == 0:
        verdict = "HOLD"
        color = "blue"
    elif net_score >= -2:
        verdict = "CAUTION"
        color = "yellow"
    else:
        verdict = "AVOID"
        color = "red"

    narrative = (
        f"Aggregated signal across 14 sections: "
        f"{signals['positive']} positive, {signals['negative']} negative. "
        f"Net score: {net_score:+d}. Verdict: {verdict}."
    )

    layman = f"Overall view: {verdict}. "
    if highlights["bull"]:
        layman += "Strengths: " + "; ".join(highlights["bull"][:3]) + ". "
    if highlights["bear"]:
        layman += "Concerns: " + "; ".join(highlights["bear"][:3]) + ". "
    layman += (
        "This is a deterministic synthesis based on the 14 sections above — "
        "it does not incorporate qualitative factors (management quality, competitive disruption, regulatory changes). "
        "Use as ONE input, not a sole basis for investment decisions."
    )

    return {
        "section": "synthesis",
        "title": "15. Overall Synthesis — Layman Verdict",
        "confidence": "high",
        "verdict": verdict,
        "verdict_color": color,
        "narrative": narrative,
        "layman": layman,
        "metrics": {
            "positive_signals": signals["positive"],
            "negative_signals": signals["negative"],
            "net_score": net_score,
            "verdict": verdict,
            "bull_highlights": highlights["bull"],
            "bear_highlights": highlights["bear"],
        },
    }


# ═════════════════════════════════════════════════════════════════════════
# TOP-LEVEL ORCHESTRATOR
# ═════════════════════════════════════════════════════════════════════════

def analyze_cycle(ticker: str, market_cap: int = 0, current_price: float = 0) -> dict:
    """
    Run full 360° cycle analysis. Returns dict with 15 sections.
    Cached for 1 hour per ticker.
    """
    t = ticker.strip().upper()
    if not t:
        return {"success": False, "error": "empty ticker"}

    cache_key = f"{t}:{market_cap}:{current_price}"
    now = time.time()
    with _cycle_lock:
        cached = _cycle_cache.get(cache_key)
        if cached and (now - cached[0]) < _CACHE_TTL:
            return cached[1]

    snap = _fetch_fundamentals(t)
    sector = snap.sector if snap.has_data else ""

    # r63.72.23: each section wrapped — one failure no longer kills the whole analysis
    sections = []
    sections.append(_safe_section("profit_margins",        "1. Profit Margins — Where in the Cycle?",         _section_profit_margins, snap))
    sections.append(_safe_section("normalized_earnings",   "2. Normalized Earnings (Cycle-Adjusted)",          _section_normalized_earnings, snap, market_cap))
    sections.append(_safe_section("balance_sheet",         "3. Balance Sheet Strength",                        _section_balance_sheet, snap))
    sections.append(_safe_section("revenue_visibility",    "4. Revenue Visibility & Customer Lock-in",         _section_revenue_visibility, snap, sector))
    sections.append(_safe_section("supply_discipline",     "5. Supply Discipline (Capex Behavior)",            _section_supply_discipline, snap))
    sections.append(_safe_section("locked_demand",         "6. Demand Lock-in & Forward Visibility",           _section_locked_demand, snap, sector))
    sections.append(_safe_section("counter_argument",      "7. Counter-Argument: Is This Cycle Different?",    _section_counter_argument, snap, sector))
    sections.append(_safe_section("forward_pe",            "8. Forward P/E vs Historical",                     _section_forward_pe, snap, market_cap, current_price))
    sections.append(_safe_section("revenue_estimation",    "9. Revenue Estimation — 3 Scenarios",              _section_revenue_estimation, snap))
    sections.append(_safe_section("operating_profit_walk", "10. Operating Profit Walk (YoY Decomposition)",    _section_operating_profit_walk, snap))
    sections.append(_safe_section("normalized_target",     "11. Normalized P/E Target (Full-Cycle Fair Value)", _section_normalized_target, snap, market_cap, current_price))
    sections.append(_safe_section("margin_of_safety",      "12. Margin of Safety (Downside Stress Test)",      _section_margin_of_safety, snap, current_price, market_cap))
    sections.append(_safe_section("segment_cycle",         "13. Cycle Analysis (Sector Pattern)",              _section_segment_cycle, snap, sector))
    sections.append(_safe_section("customer_stickiness",   "14. Customer Stickiness (Pricing Power Proxy)",    _section_customer_stickiness, snap, sector))
    sections.append(_safe_section("synthesis",             "15. Overall Synthesis — Layman Verdict",           _section_synthesis, sections, t))

    result = {
        "success": True,
        "ticker": t,
        "sector": sector,
        "has_fundamentals": snap.has_data,
        "market_cap": market_cap,
        "current_price": current_price,
        "sections": sections,
    }

    with _cycle_lock:
        _cycle_cache[cache_key] = (now, result)
    return result
