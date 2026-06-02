"""
Celesys Cognitive Architecture — BOOTSTRAP
==========================================

Populates the Layer 1 ontology and the Layer 2 dependency graph with v1
content. Import this module ONCE at app startup to wire everything up.

Lays out:
  6 Dimensions    (Fundamentals, Valuation, Momentum, Smart Money,
                   Business Quality, Catalysts)
  ~20 Signals    (representative subset — easily extensible)
  Graph edges    (the institutional logic: catalyst→volume→vwap→breakout, etc.)

After import:
  - REGISTRY.dimensions() returns 6 entries
  - REGISTRY.signals()    returns ~20 entries
  - GRAPH.edges()         returns the dependency edges
"""
from __future__ import annotations

from celesys_ontology import (
    REGISTRY, DimensionDef, SignalDef, ScoreResult, SourceQuality,
    Verdict, score_to_verdict, register_signal,
)
from celesys_graph import GRAPH, add_edge


# ─────────────────────────────────────────────────────────────────────────────
# DIMENSIONS — 6 thematic clusters, weights sum to 1.0
# ─────────────────────────────────────────────────────────────────────────────

REGISTRY.register_dimension(DimensionDef(
    id="fundamentals", name="Fundamentals",
    description="Business quality fundamentals: growth, profitability, capital allocation.",
    weight=0.30, min_coverage_for_score=0.5,
))
REGISTRY.register_dimension(DimensionDef(
    id="valuation", name="Valuation",
    description="Price relative to earnings, book, cash flow, growth.",
    weight=0.20, min_coverage_for_score=0.5,
))
REGISTRY.register_dimension(DimensionDef(
    id="momentum", name="Momentum",
    description="Price action and trend strength.",
    weight=0.15, min_coverage_for_score=0.5,
))
REGISTRY.register_dimension(DimensionDef(
    id="smart_money", name="Smart Money",
    description="Institutional + insider activity.",
    weight=0.15, min_coverage_for_score=0.5,
))
REGISTRY.register_dimension(DimensionDef(
    id="business_quality", name="Business Quality",
    description="Moat, scale, pricing power, durability.",
    weight=0.10, min_coverage_for_score=0.5,
))
REGISTRY.register_dimension(DimensionDef(
    id="catalysts", name="Catalysts",
    description="Near-term events that move price: earnings, sector rotation, news.",
    weight=0.10, min_coverage_for_score=0.5,
))


# ─────────────────────────────────────────────────────────────────────────────
# SIGNALS — atomic scorers. Each returns ScoreResult.
# Scorers MUST: return None for score on missing data (never fake-neutral).
# ─────────────────────────────────────────────────────────────────────────────

# ─── FUNDAMENTALS ────────────────────────────────────────────────────────────

@register_signal(
    sig_id="revenue_growth_5y", dimension="fundamentals",
    name="Revenue growth 5y CAGR",
    description="5-year revenue CAGR. >15% = strong growth.",
    required_inputs=["revenue_cagr_5y"], source_quality=SourceQuality.SECONDARY,
    weight=1.0,
)
def _sc_rev_growth(b: dict) -> ScoreResult:
    r = b["revenue_cagr_5y"]
    # Bands: <0 → 10; 0-5 → 30; 5-10 → 50; 10-15 → 70; 15-25 → 85; >25 → 95
    if r < 0:     s = 10
    elif r < 5:   s = 30
    elif r < 10:  s = 50
    elif r < 15:  s = 70
    elif r < 25:  s = 85
    else:         s = 95
    return ScoreResult(score=s, raw=r, inputs_used={"revenue_cagr_5y": r},
                       provenance=[f"revenue CAGR {r:.1f}% → band {s}"])


@register_signal(
    sig_id="eps_growth_5y", dimension="fundamentals",
    name="EPS growth 5y CAGR",
    description="5-year EPS CAGR. Captures earnings power compounding.",
    required_inputs=["eps_cagr_5y"], source_quality=SourceQuality.SECONDARY,
    weight=1.0,
)
def _sc_eps_growth(b: dict) -> ScoreResult:
    e = b["eps_cagr_5y"]
    if e < 0:     s = 10
    elif e < 5:   s = 30
    elif e < 10:  s = 50
    elif e < 15:  s = 70
    elif e < 25:  s = 85
    else:         s = 95
    return ScoreResult(score=s, raw=e,
                       provenance=[f"EPS CAGR {e:.1f}% → {s}"])


@register_signal(
    sig_id="roe", dimension="fundamentals",
    name="Return on Equity",
    description="ROE > 15% sustained = quality capital allocator.",
    required_inputs=["roe"], source_quality=SourceQuality.SECONDARY,
    weight=1.0,
)
def _sc_roe(b: dict) -> ScoreResult:
    r = b["roe"]
    if r < 5:     s = 15
    elif r < 10:  s = 35
    elif r < 15:  s = 55
    elif r < 20:  s = 75
    elif r < 30:  s = 88
    else:         s = 95
    return ScoreResult(score=s, raw=r,
                       provenance=[f"ROE {r:.1f}% → {s}"])


@register_signal(
    sig_id="op_margin", dimension="fundamentals",
    name="Operating margins",
    description="Operating margins reflect pricing power + cost discipline.",
    required_inputs=["op_margin"], source_quality=SourceQuality.SECONDARY,
    weight=0.7,
)
def _sc_op_margin(b: dict) -> ScoreResult:
    m = b["op_margin"]
    if m < 0:     s = 10
    elif m < 5:   s = 30
    elif m < 10:  s = 50
    elif m < 20:  s = 70
    elif m < 30:  s = 85
    else:         s = 95
    return ScoreResult(score=s, raw=m,
                       provenance=[f"Op margin {m:.1f}% → {s}"])


@register_signal(
    sig_id="debt_to_equity", dimension="fundamentals",
    name="Debt to Equity",
    description="Lower leverage = more durable; very high = fragile.",
    required_inputs=["debt_to_equity"], source_quality=SourceQuality.SECONDARY,
    weight=0.7,
)
def _sc_d2e(b: dict) -> ScoreResult:
    d = b["debt_to_equity"]
    # Higher debt → lower score
    if d < 0.3:   s = 90
    elif d < 0.6: s = 75
    elif d < 1.0: s = 55
    elif d < 1.5: s = 35
    else:         s = 15
    return ScoreResult(score=s, raw=d,
                       provenance=[f"D/E {d:.2f} → {s}"])


@register_signal(
    sig_id="share_dilution", dimension="fundamentals",
    name="Share dilution",
    description="Net buybacks/issuance over available years (split-detection aware).",
    required_inputs=["shares_outstanding_series"],
    source_quality=SourceQuality.SECONDARY, weight=0.8,
)
def _sc_dilution(b: dict) -> ScoreResult:
    series = b["shares_outstanding_series"]  # [(year, shares)] oldest-first or newest-first
    if not series or len(series) < 2:
        return ScoreResult(score=None, note="need ≥2 yearly data points",
                           missing_required=["shares_outstanding_series"])
    # Normalize to newest-first
    s_sorted = sorted(series, key=lambda t: t[0], reverse=True)
    # Stock split detection — adjacent ratio outside [0.65, 1.55]
    for i in range(len(s_sorted) - 1):
        newer = s_sorted[i][1]; older = s_sorted[i+1][1]
        if older <= 0: continue
        ratio = newer / older
        if ratio >= 1.5 or ratio <= 0.65:
            return ScoreResult(
                score=50, raw=ratio,
                verdict_override=Verdict.NEUTRAL,
                note=f"stock split detected near {s_sorted[i+1][0]} → dilution check skipped",
                provenance=[f"adjacent shares ratio {ratio:.2f} suggests split"],
            )
    latest = s_sorted[0][1]
    prior_idx = min(3, len(s_sorted) - 1)
    prior = s_sorted[prior_idx][1]
    years = s_sorted[0][0] - s_sorted[prior_idx][0]
    if prior <= 0:
        return ScoreResult(score=None, note="prior shares=0", missing_required=[])
    delta_pct = (latest - prior) / prior * 100
    # Bands: buyback (≤−2): 90; stable (≤0.5): 75; mild (≤2): 55; meaningful (≤5): 35; heavy (>5): 15
    if delta_pct <= -2:   s_score = 90
    elif delta_pct <= 0.5: s_score = 75
    elif delta_pct <= 2:   s_score = 55
    elif delta_pct <= 5:   s_score = 35
    else:                  s_score = 15
    return ScoreResult(
        score=s_score, raw=round(delta_pct, 2),
        note=f"{round(delta_pct, 2)}% over {years}y",
        provenance=[f"shares {prior:.0f}→{latest:.0f} over {years}y ({delta_pct:+.1f}%)"],
    )


# ─── VALUATION ───────────────────────────────────────────────────────────────

@register_signal(
    sig_id="trailing_pe", dimension="valuation",
    name="Trailing P/E",
    description="Price / trailing earnings. Lower = cheaper (sector context matters).",
    required_inputs=["pe"], source_quality=SourceQuality.SECONDARY,
)
def _sc_pe(b: dict) -> ScoreResult:
    p = b["pe"]
    if p <= 0:    return ScoreResult(score=None, raw=p,
                                     note="negative or zero P/E (loss-maker)",
                                     provenance=["P/E ≤ 0 → no comparable"])
    if p < 12:    s = 85
    elif p < 18:  s = 70
    elif p < 25:  s = 55
    elif p < 35:  s = 35
    else:         s = 15
    return ScoreResult(score=s, raw=p, provenance=[f"P/E {p:.1f} → {s}"])


@register_signal(
    sig_id="peg_ratio", dimension="valuation",
    name="PEG ratio",
    description="P/E adjusted for growth. <1 = cheap relative to growth.",
    required_inputs=["peg"], source_quality=SourceQuality.SECONDARY,
)
def _sc_peg(b: dict) -> ScoreResult:
    p = b["peg"]
    if p <= 0:
        return ScoreResult(score=None, raw=p, note="non-positive PEG")
    if p < 1.0:   s = 90
    elif p < 1.5: s = 70
    elif p < 2.5: s = 45
    else:         s = 20
    return ScoreResult(score=s, raw=p, provenance=[f"PEG {p:.2f} → {s}"])


@register_signal(
    sig_id="ev_ebitda", dimension="valuation",
    name="EV / EBITDA",
    description="Enterprise value / EBITDA. <10 = cheap, >25 = expensive.",
    required_inputs=["ev_to_ebitda"], source_quality=SourceQuality.SECONDARY,
)
def _sc_ev_ebitda(b: dict) -> ScoreResult:
    e = b["ev_to_ebitda"]
    if e <= 0:
        return ScoreResult(score=15, raw=e,
                           note="negative EV/EBITDA — loss-maker or distressed",
                           provenance=["EV/EBITDA ≤ 0"])
    if e < 10:    s = 85
    elif e < 15:  s = 70
    elif e < 25:  s = 45
    else:         s = 20
    return ScoreResult(score=s, raw=e, provenance=[f"EV/EBITDA {e:.1f} → {s}"])


@register_signal(
    sig_id="fcf_yield", dimension="valuation",
    name="FCF yield",
    description="Free cash flow / market cap. Higher = cheaper on cash basis.",
    required_inputs=["fcf_yield"], source_quality=SourceQuality.SECONDARY,
    weight=0.8,
)
def _sc_fcfy(b: dict) -> ScoreResult:
    y = b["fcf_yield"]
    if y < 0:     s = 15
    elif y < 2:   s = 35
    elif y < 5:   s = 55
    elif y < 8:   s = 75
    else:         s = 90
    return ScoreResult(score=s, raw=y, provenance=[f"FCF yield {y:.1f}% → {s}"])


# ─── MOMENTUM ────────────────────────────────────────────────────────────────

@register_signal(
    sig_id="above_sma_50", dimension="momentum",
    name="Above 50-day SMA",
    description="Trend filter: price > 50-day moving average.",
    required_inputs=["price", "sma_50"],
    source_quality=SourceQuality.SECONDARY, weight=1.0,
)
def _sc_sma50(b: dict) -> ScoreResult:
    p = b["price"]; m = b["sma_50"]
    if m <= 0:
        return ScoreResult(score=None, raw=m, note="SMA50 invalid")
    ratio = p / m
    if ratio < 0.95:    s = 15
    elif ratio < 1.0:   s = 35
    elif ratio < 1.05:  s = 65
    elif ratio < 1.15:  s = 80
    else:               s = 90
    return ScoreResult(score=s, raw=round(ratio, 3),
                       provenance=[f"price/SMA50 = {ratio:.3f} → {s}"])


@register_signal(
    sig_id="above_sma_200", dimension="momentum",
    name="Above 200-day SMA",
    description="Long-term trend filter: price > 200-day moving average.",
    required_inputs=["price", "sma_200"],
    source_quality=SourceQuality.SECONDARY, weight=1.0,
)
def _sc_sma200(b: dict) -> ScoreResult:
    p = b["price"]; m = b["sma_200"]
    if m <= 0:
        return ScoreResult(score=None, raw=m, note="SMA200 invalid")
    ratio = p / m
    if ratio < 0.95:    s = 15
    elif ratio < 1.0:   s = 35
    elif ratio < 1.05:  s = 65
    elif ratio < 1.20:  s = 80
    else:               s = 90
    return ScoreResult(score=s, raw=round(ratio, 3),
                       provenance=[f"price/SMA200 = {ratio:.3f} → {s}"])


@register_signal(
    sig_id="rvol_today", dimension="momentum",
    name="Relative volume today",
    description="Today's volume / 20-day average. >1.5x = institutional interest.",
    required_inputs=["rvol"], source_quality=SourceQuality.SECONDARY,
    weight=0.8,
)
def _sc_rvol(b: dict) -> ScoreResult:
    r = b["rvol"]
    if r < 0.5:    s = 20
    elif r < 0.8:  s = 40
    elif r < 1.2:  s = 55
    elif r < 1.8:  s = 75
    elif r < 3.0:  s = 88
    else:          s = 95
    return ScoreResult(score=s, raw=r, provenance=[f"RVOL {r:.2f}x → {s}"])


@register_signal(
    sig_id="vwap_hold", dimension="momentum",
    name="VWAP hold",
    description="Price holding above VWAP intraday = institutional support.",
    required_inputs=["price", "vwap"], source_quality=SourceQuality.SECONDARY,
    weight=0.6,
)
def _sc_vwap(b: dict) -> ScoreResult:
    p = b["price"]; v = b["vwap"]
    if v <= 0:
        return ScoreResult(score=None, raw=v, note="VWAP invalid")
    delta_pct = (p - v) / v * 100
    if delta_pct < -2:   s = 20
    elif delta_pct < 0:  s = 40
    elif delta_pct < 1:  s = 65
    elif delta_pct < 3:  s = 80
    else:                s = 90
    return ScoreResult(score=s, raw=round(delta_pct, 2),
                       provenance=[f"price vs VWAP {delta_pct:+.2f}% → {s}"])


@register_signal(
    sig_id="breakout_20d", dimension="momentum",
    name="20-day breakout",
    description="Close at or near 20-day high (with volume confirmation).",
    required_inputs=["price", "high_20d"],
    optional_inputs=["rvol"],
    source_quality=SourceQuality.SECONDARY, weight=0.7,
)
def _sc_breakout(b: dict) -> ScoreResult:
    p = b["price"]; h = b["high_20d"]; rv = b.get("rvol")
    if h <= 0:
        return ScoreResult(score=None, raw=h, note="20d high invalid")
    proximity = p / h
    if proximity >= 0.995:
        # Volume confirmation
        if rv is not None and rv > 1.0:
            return ScoreResult(score=90, raw=round(proximity, 3),
                               provenance=[f"close {proximity:.3f} of 20dH × RVOL {rv:.2f}x → breakout"])
        else:
            return ScoreResult(score=60, raw=round(proximity, 3),
                               note="breakout on low volume — weak signal",
                               provenance=[f"close at 20dH but RVOL {rv}x or unknown"])
    elif proximity >= 0.97:
        return ScoreResult(score=55, raw=round(proximity, 3),
                           provenance=[f"within 3% of 20dH → near breakout"])
    else:
        return ScoreResult(score=25, raw=round(proximity, 3),
                           provenance=[f"{(1-proximity)*100:.1f}% below 20dH"])


# ─── SMART MONEY ─────────────────────────────────────────────────────────────

@register_signal(
    sig_id="insider_net_buying", dimension="smart_money",
    name="Net insider buying 180d",
    description="Net insider buying as % of float over last 180 days.",
    required_inputs=["insider_net_180d_pct"],
    source_quality=SourceQuality.SECONDARY, weight=1.0,
)
def _sc_insider(b: dict) -> ScoreResult:
    x = b["insider_net_180d_pct"]
    if x > 0.5:     s = 90
    elif x > 0.1:   s = 75
    elif x > -0.1:  s = 50
    elif x > -0.5:  s = 30
    else:           s = 15
    return ScoreResult(score=s, raw=x, provenance=[f"insider net {x:+.2f}% → {s}"])


@register_signal(
    sig_id="institutional_ownership", dimension="smart_money",
    name="Institutional ownership %",
    description="% of shares held by institutions. >50% = institutional presence.",
    required_inputs=["institutional_ownership_pct"],
    source_quality=SourceQuality.SECONDARY, weight=0.7,
)
def _sc_inst_own(b: dict) -> ScoreResult:
    x = b["institutional_ownership_pct"]
    if x < 20:    s = 30
    elif x < 50:  s = 55
    elif x < 75:  s = 75
    else:         s = 88
    return ScoreResult(score=s, raw=x, provenance=[f"inst own {x:.0f}% → {s}"])


@register_signal(
    sig_id="smv3", dimension="smart_money",
    name="Smart Money v3 score",
    description="External SMv3 institutional rating (0-100).",
    required_inputs=["smv3_score"], source_quality=SourceQuality.HEURISTIC,
    weight=0.8,
)
def _sc_smv3(b: dict) -> ScoreResult:
    x = b["smv3_score"]
    # SMv3 already 0-100; pass through clamped
    s = max(0.0, min(100.0, x))
    return ScoreResult(score=s, raw=x, provenance=[f"SMv3 passthrough {s:.0f}"])


# ─── BUSINESS QUALITY ────────────────────────────────────────────────────────

@register_signal(
    sig_id="moat_proxy_margin_stability", dimension="business_quality",
    name="Pricing power (op margin proxy)",
    description="Sustained high op margin = pricing power moat (heuristic).",
    required_inputs=["op_margin"], source_quality=SourceQuality.HEURISTIC,
)
def _sc_moat(b: dict) -> ScoreResult:
    m = b["op_margin"]
    if m < 10:    s = 25
    elif m < 20:  s = 55
    elif m < 30:  s = 75
    else:         s = 90
    return ScoreResult(score=s, raw=m,
                       provenance=[f"op margin {m:.1f}% as moat proxy → {s}"])


@register_signal(
    sig_id="capital_efficiency", dimension="business_quality",
    name="Capital efficiency (ROE proxy)",
    description="High ROE = efficient capital deployer.",
    required_inputs=["roe"], source_quality=SourceQuality.HEURISTIC,
)
def _sc_cap_eff(b: dict) -> ScoreResult:
    r = b["roe"]
    if r < 10:    s = 25
    elif r < 20:  s = 60
    elif r < 30:  s = 80
    else:         s = 92
    return ScoreResult(score=s, raw=r, provenance=[f"ROE {r:.1f}% → {s}"])


# ─── CATALYSTS ───────────────────────────────────────────────────────────────

@register_signal(
    sig_id="earnings_proximity", dimension="catalysts",
    name="Earnings proximity",
    description="Days to next earnings. <14 days = strong near-term catalyst.",
    required_inputs=["days_to_earnings"], source_quality=SourceQuality.SECONDARY,
    weight=1.0,
)
def _sc_earnings(b: dict) -> ScoreResult:
    d = b["days_to_earnings"]
    if d < 7:     s = 85
    elif d < 14:  s = 70
    elif d < 30:  s = 55
    elif d < 60:  s = 40
    else:         s = 25
    return ScoreResult(score=s, raw=d, provenance=[f"earnings in {d}d → {s}"])


@register_signal(
    sig_id="relative_strength_vs_market", dimension="catalysts",
    name="RS vs market",
    description="20-day return vs market. Strong RS = leadership.",
    required_inputs=["relative_strength_pct"],
    source_quality=SourceQuality.SECONDARY, weight=0.8,
)
def _sc_rs(b: dict) -> ScoreResult:
    r = b["relative_strength_pct"]
    if r < -10:   s = 15
    elif r < 0:   s = 35
    elif r < 5:   s = 55
    elif r < 15:  s = 75
    else:         s = 90
    return ScoreResult(score=s, raw=r, provenance=[f"RS {r:+.1f}% → {s}"])


@register_signal(
    sig_id="sector_momentum", dimension="catalysts",
    name="Sector momentum",
    description="Parent sector's 20-day return. Sector tailwinds matter.",
    required_inputs=["sector_momentum_pct"],
    source_quality=SourceQuality.SECONDARY, weight=0.6,
)
def _sc_sector_mom(b: dict) -> ScoreResult:
    s_pct = b["sector_momentum_pct"]
    if s_pct < -5:    s = 20
    elif s_pct < 0:   s = 40
    elif s_pct < 5:   s = 60
    elif s_pct < 10:  s = 75
    else:             s = 88
    return ScoreResult(score=s, raw=s_pct,
                       provenance=[f"sector {s_pct:+.1f}% 20d → {s}"])


# ─────────────────────────────────────────────────────────────────────────────
# DEPENDENCY GRAPH — institutional truth logic
# ─────────────────────────────────────────────────────────────────────────────
# The doc's example: Catalyst → Volume Expansion → VWAP Acceptance → Breakout
#
# We encode this plus a few more:
#   - Breakout's quality depends on RVOL (volume confirms) AND sector momentum
#   - VWAP hold depends on RVOL (price can't hold VWAP on no volume)
#   - PEG depends on EPS growth (no growth → no PEG denominator)
#   - Institutional ownership and SMv3 are independent SmartMoney signals
#   - RS-vs-market depends on sector momentum (sector context matters)

add_edge("rvol_today", "vwap_hold", required=False, weight_modifier=1.0,
         description="VWAP hold on shrinking volume is weak — degrade weight")
add_edge("rvol_today", "breakout_20d", required=False, weight_modifier=1.0,
         description="Breakout without volume = fake — but optional (some breakouts are scarce-volume continuations)")
add_edge("sector_momentum", "relative_strength_vs_market", required=False, weight_modifier=0.7,
         description="RS is more meaningful when sector context is known")
add_edge("eps_growth_5y", "peg_ratio", required=False, weight_modifier=1.0,
         description="PEG needs growth context; missing growth = degrade")
add_edge("earnings_proximity", "breakout_20d", required=False, weight_modifier=0.6,
         description="Breakouts near earnings carry catalyst weight")


def bootstrap() -> dict:
    """Call to ensure all registrations have happened.

    Returns a summary dict of what was wired up. Safe to call multiple times
    (registry rejects duplicate registrations, but this function only runs
    its registration calls at module import time).
    """
    return {
        "ontology_dimensions": len(REGISTRY.dimensions()),
        "ontology_signals": len(REGISTRY.signals()),
        "graph_edges": len(GRAPH.edges()),
        "issues_ontology": REGISTRY.validate(),
        "issues_graph": GRAPH.validate(),
    }


# Auto-bootstrap at import time
_SUMMARY = bootstrap()
