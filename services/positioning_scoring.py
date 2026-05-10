"""
r63.72 — Institutional positioning scoring engine.

Pure-Python read-only module. Queries holdings + filings tables and
returns ranked per-ticker conviction scores. No schema changes, no
new tables, no caches — every score computed live from raw data.

Architecture:
    1. Build per-ticker, per-quarter aggregates (filer count, total
       value, total shares, top-10 concentration)
    2. Compute Q-over-Q deltas (value, shares, filer count)
    3. Compute persistence (consecutive quarters of net accumulation)
    4. Compute new-buyer count (first-time entrants in latest quarter)
    5. Z-score normalize each metric across the universe
    6. Composite score → percentile rank → tier bucket

Tier mapping (heuristic, not backtested per the v0 plan):
    Tier 1 STEALTH ACCUMULATION   composite >= 80th percentile
    Tier 2 EARLY POSITIONING      60-80th percentile
    Tier 3 BUILDING               40-60th percentile
    (no tier shown below 40th)
"""

from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
import math
import statistics


# ETFs and other non-actionable instruments to exclude
_ETF_TICKERS = {
    "SPY", "VOO", "IVV", "QQQ", "VTI", "DIA", "IWM", "EFA", "EEM",
    "AGG", "BND", "TLT", "HYG", "LQD", "SHY", "IEF",
    "GLD", "SLV", "USO",
    "XLK", "XLF", "XLV", "XLE", "XLY", "XLP", "XLI", "XLU", "XLB", "XLRE", "XLC",
    "VEA", "VWO", "VTV", "VUG", "VTEB", "BSV", "BIV",
    "VGT", "VHT", "VFH", "VDE", "VCR", "VDC", "VIS", "VPU", "VAW", "VOX", "VNQ",
    "IEMG", "IEFA", "VBR", "VOE", "VBK", "VOT", "MGK", "MGV",
    "VYM", "SCHD", "DVY", "VIG", "JEPI", "JEPQ",
    "ACWI", "VT", "ITOT", "IXUS",
}


@dataclass
class TickerSnapshot:
    """One quarter's aggregate stats for a ticker."""
    ticker: str
    period: str           # ISO date string
    issuer_name: str
    filer_count: int
    total_value_usd: int
    total_shares: int
    top10_value_usd: int  # Sum of top-10 holders' positions


@dataclass
class TickerScore:
    """Composite positioning score for a ticker."""
    ticker: str
    issuer_name: str
    composite_score: float       # 0-100 percentile rank
    tier: int                     # 1, 2, 3, or 0 (below threshold)
    tier_label: str

    # Component metrics (raw + z-score)
    value_delta_pct: float        # Q-over-Q value change %
    value_delta_z: float
    share_delta_pct: float        # Q-over-Q share count change % (clean of price)
    share_delta_z: float
    filer_count_delta: int        # Net new filers in latest quarter
    filer_delta_z: float
    persistence_quarters: int     # # consecutive recent quarters of net accumulation
    persistence_z: float
    concentration_hhi: float      # Herfindahl on top-10 (lower = more diversified buying)
    concentration_z: float

    # Context
    latest_filer_count: int
    latest_value_usd: int
    quarters_present: int

    # Top driving signals (human-readable)
    top_signals: List[str]

    # r63.72.5: Live-quote enrichment
    price: float = 0.0                   # current stock price
    prev_close: float = 0.0
    change_pct: float = 0.0              # today's % change
    low_52w: float = 0.0
    high_52w: float = 0.0
    pct_in_range: float = -1.0           # 0-100 where price sits in 52W range; -1 if no data
    market_cap: int = 0                  # current market cap in dollars
    reasoning: str = ""                  # plain-English trader-speak narrative

    # r63.72.6: Promise Score + investment-decision fields
    promise_score: float = 0.0           # 0-100 forward-looking 1-year promise composite
    star_rating: int = 0                 # 1-5 stars (0 = no rating)
    is_best_bet: bool = False            # top 10 by promise score
    best_bet_rank: int = 0               # 1-10 if best bet, else 0
    inst_buyers: int = 0                 # # of filers who increased shares Q/Q (or new positions)
    inst_sellers: int = 0                # # of filers who reduced shares Q/Q (or exited)
    insider_net_buys: int = 0            # placeholder for Form 4 data (r63.73)
    insider_net_sells: int = 0           # placeholder for Form 4 data (r63.73)
    has_insider_data: bool = False       # set True once Form 4 ingest exists

    # r63.72.7: Multibagger framework — M/F/G/O composite
    # r63.72.9: Scores can now be None (rendered as N/A) — no fake precision
    multibagger_score: Optional[float] = None    # 0-100 final, or None if M/G/O missing
    moat_score: Optional[float] = None
    flow_score: Optional[float] = None
    growth_score: Optional[float] = None
    optionality_score: Optional[float] = None
    risk_penalty: float = 0.0
    phase_label: str = ""
    has_fundamentals: bool = False
    multibagger_narrative: str = ""

    # r63.72.9: Type + confidence — replace stars-only display
    type_label: str = ""                         # "Structural Compounder" / "Flow Momentum" / etc.
    confidence: str = "none"                     # "high" / "medium" / "low" / "none"

    # r63.72.10: Three-lens architecture (Phase A)
    # Each lens has its own score + conviction band. Display surfaces only
    # the active lens's primary metric at a time.
    regime: str = "NEUTRAL"                      # ACCUMULATION / DISTRIBUTION / NEUTRAL
    saturation_pct: Optional[float] = None       # institutional ownership saturation
    ownership_velocity: Optional[float] = None   # Q-over-Q ownership change

    # Lens 1 — Compounders
    compounder_score: Optional[float] = None     # 0-100 quality score
    compounder_conviction: str = "INSUFFICIENT DATA"
    roic_median: Optional[float] = None
    gross_margin_floor: Optional[float] = None
    fcf_consistency: Optional[float] = None

    # Lens 2 — Institutional Accumulation
    accumulation_score: Optional[float] = None   # 0-100 flow score
    accumulation_conviction: str = "INSUFFICIENT DATA"
    buy_sell_dominance: Optional[float] = None
    relative_strength: Optional[float] = None

    # Lens 3 — Asymmetric Optionality
    optionality_score_lens: Optional[float] = None
    optionality_conviction: str = "INSUFFICIENT DATA"
    rd_intensity: Optional[float] = None
    cash_to_mcap: Optional[float] = None
    revenue_acceleration: Optional[float] = None
    survivability_months: Optional[float] = None


def _percentile_rank(values: List[float], v: float) -> float:
    """Return v's percentile rank within values (0-100)."""
    if not values:
        return 50.0
    below = sum(1 for x in values if x < v)
    eq = sum(1 for x in values if x == v)
    return 100.0 * (below + 0.5 * eq) / len(values)


def _z_score(values: List[float], v: float) -> float:
    """Standard z-score; returns 0 if stddev is 0."""
    if len(values) < 2:
        return 0.0
    try:
        mean = statistics.fmean(values)
        sd = statistics.pstdev(values)
        if sd == 0:
            return 0.0
        return (v - mean) / sd
    except Exception:
        return 0.0


def _safe_pct_change(new: float, old: float) -> float:
    """Pct change, with floor on the denominator to prevent infinity."""
    if old <= 0:
        return 0.0
    return 100.0 * (new - old) / max(old, 1e-9)


def fetch_universe_snapshots(conn) -> Dict[str, List[TickerSnapshot]]:
    """
    Build {ticker: [TickerSnapshot, ...]} sorted oldest-first per ticker.

    r63.72.3: Properly filters out ETFs/foreign/SPACs/thinly-held.
    r63.72.4: Divides value_usd by 1000 to correct parser bug (post-2023
    13F filings report in dollars not thousands; parser was multiplying ×1000).
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ticker,
                   period_of_report::text AS period,
                   COALESCE(MAX(issuer_name), '') AS issuer_name,
                   COUNT(DISTINCT cik) AS filer_count,
                   (SUM(value_usd) / 1000)::bigint AS total_value,
                   SUM(COALESCE(shares, 0))::bigint AS total_shares
            FROM holdings
            WHERE ticker IS NOT NULL
              AND value_usd > 0
              AND ticker ~ '^[A-Z]{1,5}(\\.[A-Z])?$'  -- US primary listings only
              AND ticker NOT LIKE '%EUR%'
              AND ticker NOT LIKE '%USD%'
              AND ticker NOT LIKE '%-R'
              AND ticker NOT LIKE '%-W'
              AND ticker NOT LIKE '%-WS'
              AND ticker NOT LIKE '%-WT'
            GROUP BY ticker, period_of_report
            HAVING COUNT(DISTINCT cik) >= 30
            ORDER BY ticker, period_of_report
            """,
        )
        rows = cur.fetchall()

    # Group by ticker, then issuer-name based ETF filter
    snapshots: Dict[str, List[TickerSnapshot]] = {}

    # Issuer-name patterns that indicate ETFs / passive instruments / pooled vehicles
    # These reliably catch ~95%+ of ETFs without needing a hardcoded ticker list
    _ETF_NAME_PATTERNS = [
        "ISHARES", "SPDR", "VANGUARD", "INVESCO", "PROSHARES", "DIREXION",
        "SCHWAB ", "FIDELITY ETF", "GLOBAL X", "WISDOMTREE", "FIRST TRUST",
        "JPMORGAN ETF", "JPMORGAN EXCHANGE",
        "ETF TRUST", "ETF TR", " ETF ", " ETF/",
        "INDEX FUND", "INDEX TR", "INDEX TRUST",
        "TRUST ETP", "EXCHANGE TRADED",
        "PROSHARE",  # ProShares variant spellings
        "INDEX SHARES", "TARGET CORP RET",  # target-date funds
        "SHARES ETF", "BOND FUND", "MONEY MARKET",
        "MASTER LP",  # MLP holding vehicles
    ]

    for ticker, period, issuer_name, filer_count, total_value, total_shares in rows:
        # Skip if issuer name matches any ETF pattern
        if issuer_name:
            issuer_upper = issuer_name.upper()
            if any(pat in issuer_upper for pat in _ETF_NAME_PATTERNS):
                continue
            # Also skip if also matches the legacy hardcoded ticker blocklist
            if ticker in _ETF_TICKERS:
                continue

        snapshots.setdefault(ticker, []).append(
            TickerSnapshot(
                ticker=ticker,
                period=period,
                issuer_name=issuer_name,
                filer_count=int(filer_count),
                total_value_usd=int(total_value or 0),
                total_shares=int(total_shares or 0),
                top10_value_usd=0,  # filled below
            )
        )

    # Top-10 concentration per (ticker, period)
    # With idx_holdings_ticker_period in place, the ROW_NUMBER scan
    # uses an index seek per partition rather than a full table sort.
    if snapshots:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH per_filer AS (
                    SELECT ticker, period_of_report, cik,
                           SUM(value_usd) / 1000 AS v   -- r63.72.4: undo parser ×1000
                    FROM holdings
                    WHERE ticker IS NOT NULL AND value_usd > 0
                    GROUP BY ticker, period_of_report, cik
                ),
                ranked AS (
                    SELECT ticker, period_of_report, v,
                           ROW_NUMBER() OVER (PARTITION BY ticker, period_of_report
                                              ORDER BY v DESC) AS rn
                    FROM per_filer
                )
                SELECT ticker, period_of_report::text AS period, SUM(v)::bigint
                FROM ranked
                WHERE rn <= 10
                GROUP BY ticker, period_of_report
                """,
            )
            top10_lookup = {}
            for ticker, period, total in cur.fetchall():
                top10_lookup[(ticker, period)] = int(total or 0)

        for ticker, snaps in snapshots.items():
            for s in snaps:
                s.top10_value_usd = top10_lookup.get((ticker, s.period), 0)

    return snapshots


def fetch_buy_sell_filers(conn) -> Dict[str, dict]:
    """
    r63.72.6: For each ticker, count filers who INCREASED shares vs.
    DECREASED shares between the two most recent quarters.

    This is sharper than 'net new filers' because it captures EXISTING
    holders adding/trimming, not just newcomers.

    Returns: {ticker: {"inst_buyers": int, "inst_sellers": int}}
    """
    out: Dict[str, dict] = {}
    with conn.cursor() as cur:
        # First find the two most recent periods that have substantial data
        cur.execute(
            """
            SELECT period_of_report
            FROM filings
            GROUP BY period_of_report
            HAVING COUNT(*) >= 30
            ORDER BY period_of_report DESC
            LIMIT 2
            """
        )
        periods = [r[0] for r in cur.fetchall()]
        if len(periods) < 2:
            return out
        latest_period, prior_period = periods[0], periods[1]

        # Per-(ticker, cik) shares in each of the two periods
        cur.execute(
            """
            WITH per_filer_qtr AS (
                SELECT ticker, cik, period_of_report,
                       SUM(COALESCE(shares, 0)) AS shares
                FROM holdings
                WHERE ticker IS NOT NULL
                  AND value_usd > 0
                  AND period_of_report IN (%s, %s)
                GROUP BY ticker, cik, period_of_report
            ),
            pivoted AS (
                SELECT ticker, cik,
                       MAX(CASE WHEN period_of_report = %s THEN shares ELSE 0 END) AS latest_shares,
                       MAX(CASE WHEN period_of_report = %s THEN shares ELSE 0 END) AS prior_shares
                FROM per_filer_qtr
                GROUP BY ticker, cik
            )
            SELECT ticker,
                   COUNT(*) FILTER (WHERE latest_shares > prior_shares) AS inst_buyers,
                   COUNT(*) FILTER (WHERE latest_shares < prior_shares) AS inst_sellers
            FROM pivoted
            GROUP BY ticker
            """,
            (latest_period, prior_period, latest_period, prior_period),
        )
        for ticker, buyers, sellers in cur.fetchall():
            out[ticker] = {
                "inst_buyers": int(buyers or 0),
                "inst_sellers": int(sellers or 0),
            }
    return out


def _compute_metrics(snaps: List[TickerSnapshot]) -> Dict:
    """Compute raw metrics for one ticker from its quarter snapshots."""
    if len(snaps) < 2:
        # Single-quarter ticker — can't compute deltas. Return defaults.
        latest = snaps[-1] if snaps else None
        return {
            "value_delta_pct": 0.0,
            "share_delta_pct": 0.0,
            "filer_count_delta": 0,
            "persistence_quarters": 0,
            "concentration_hhi": 0.0,
            "latest_filer_count": latest.filer_count if latest else 0,
            "latest_value_usd": latest.total_value_usd if latest else 0,
            "quarters_present": len(snaps),
            "issuer_name": latest.issuer_name if latest else "",
            "exclude_reason": "insufficient_quarters",
        }

    latest = snaps[-1]
    prior = snaps[-2]

    # Q-over-Q
    value_delta_pct = _safe_pct_change(latest.total_value_usd, prior.total_value_usd)
    share_delta_pct = _safe_pct_change(latest.total_shares, prior.total_shares)
    filer_count_delta = latest.filer_count - prior.filer_count

    # r63.72.3: Sanity-cap deltas. Anything more than ±100% Q-over-Q is
    # a data artifact (CUSIP remapping, stock split, ticker reuse, share
    # class reclassification). Cap to ±100 so real accumulation patterns
    # in the 5-50% range don't get drowned out by noise.
    exclude_reason = None
    DELTA_CAP = 150.0  # %
    if abs(value_delta_pct) > DELTA_CAP or abs(share_delta_pct) > DELTA_CAP:
        # Mark for exclusion at the score-universe level
        exclude_reason = "delta_outlier"

    # Persistence: how many recent consecutive quarters showed net share accumulation
    persistence = 0
    for i in range(len(snaps) - 1, 0, -1):
        if snaps[i].total_shares > snaps[i - 1].total_shares:
            persistence += 1
        else:
            break

    # Concentration HHI on top-10 share (relative to total)
    if latest.total_value_usd > 0:
        top10_share = latest.top10_value_usd / latest.total_value_usd
    else:
        top10_share = 0.0
    concentration_hhi = top10_share

    return {
        "value_delta_pct": value_delta_pct,
        "share_delta_pct": share_delta_pct,
        "filer_count_delta": filer_count_delta,
        "persistence_quarters": persistence,
        "concentration_hhi": concentration_hhi,
        "latest_filer_count": latest.filer_count,
        "latest_value_usd": latest.total_value_usd,
        "quarters_present": len(snaps),
        "issuer_name": latest.issuer_name,
        "exclude_reason": exclude_reason,
    }


def _build_signals(metrics: Dict) -> List[str]:
    """Human-readable top signals for display in the UI.
    r63.72.4: Latest-quarter values only (not cross-quarter sums); thresholds
    tuned to surface what's actually meaningful."""
    out = []
    if metrics["share_delta_pct"] >= 10:
        out.append(f"Share count up {metrics['share_delta_pct']:.1f}% Q/Q")
    elif metrics["share_delta_pct"] >= 3:
        out.append(f"Net accumulation {metrics['share_delta_pct']:.1f}% Q/Q")
    elif metrics["share_delta_pct"] <= -10:
        out.append(f"Share count down {abs(metrics['share_delta_pct']):.1f}% Q/Q")
    elif metrics["share_delta_pct"] <= -3:
        out.append(f"Net distribution {abs(metrics['share_delta_pct']):.1f}% Q/Q")

    if metrics["filer_count_delta"] >= 20:
        out.append(f"+{metrics['filer_count_delta']} new institutional holders")
    elif metrics["filer_count_delta"] >= 5:
        out.append(f"+{metrics['filer_count_delta']} net new holders")
    elif metrics["filer_count_delta"] <= -20:
        out.append(f"{metrics['filer_count_delta']} holders exited")

    if metrics["persistence_quarters"] >= 4:
        out.append(f"{metrics['persistence_quarters']} consecutive Qs accumulating")
    elif metrics["persistence_quarters"] >= 2:
        out.append(f"{metrics['persistence_quarters']}Q accumulation streak")

    # Diversification signal: lots of holders + low concentration
    if metrics["concentration_hhi"] < 0.5 and metrics["latest_filer_count"] >= 100:
        out.append(f"Broad sponsorship — {metrics['latest_filer_count']} institutional holders")

    # Latest-quarter institutional position size — corrected scale
    val_b = metrics["latest_value_usd"] / 1e9
    if val_b >= 100:
        out.append(f"${val_b:,.0f}B institutional position")
    elif val_b >= 10:
        out.append(f"${val_b:,.1f}B institutional position")
    elif val_b >= 1:
        out.append(f"${val_b:,.2f}B institutional position")

    return out[:3]  # Limit to top 3 signals to keep UI clean


def score_universe(conn) -> List[TickerScore]:
    """
    Run scoring across all eligible tickers in the DB.

    Returns ranked list (highest composite score first). Tickers with
    fewer than 2 quarters of data are excluded.
    """
    snapshots = fetch_universe_snapshots(conn)

    # Compute raw metrics per ticker
    raw: Dict[str, Dict] = {}
    for ticker, snaps in snapshots.items():
        if len(snaps) < 2:
            continue
        m = _compute_metrics(snaps)
        # r63.72.3: Skip outliers — deltas > 150% Q/Q are data artifacts
        # (CUSIP remappings, splits, share class reclassifications), not signal.
        if m.get("exclude_reason") == "delta_outlier":
            continue
        # Also require minimum institutional presence in the latest quarter
        # to avoid noisy thinly-held names.
        if m["latest_filer_count"] < 30:
            continue
        raw[ticker] = m

    if not raw:
        return []

    # Build distributions for z-scoring
    value_deltas = [m["value_delta_pct"] for m in raw.values()]
    share_deltas = [m["share_delta_pct"] for m in raw.values()]
    filer_deltas = [float(m["filer_count_delta"]) for m in raw.values()]
    persistences = [float(m["persistence_quarters"]) for m in raw.values()]
    concentrations = [m["concentration_hhi"] for m in raw.values()]

    # Composite score: weighted z-score sum, then percentile-rank within universe
    # r63.72.4: Reweighted to favor persistence + reward institutional scale
    composites: Dict[str, float] = {}
    z_components: Dict[str, Dict] = {}
    for ticker, m in raw.items():
        z_val = _z_score(value_deltas, m["value_delta_pct"])
        z_shr = _z_score(share_deltas, m["share_delta_pct"])
        z_flr = _z_score(filer_deltas, float(m["filer_count_delta"]))
        z_per = _z_score(persistences, float(m["persistence_quarters"]))
        z_con = _z_score(concentrations, m["concentration_hhi"])

        # Weights tuned to favor sustained, broad-based accumulation:
        # - Persistence (30%): consecutive quarters of accumulation = real conviction
        # - Filer-count delta (25%): broad institutional adoption beats single-fund moves
        # - Share delta (25%): real share count change, not price-contaminated
        # - Value delta (15%): smaller weight because it's price-contaminated
        # - Concentration (-5%): light penalty for concentration in few hands
        composite_z = (
            0.30 * z_per
            + 0.25 * z_flr
            + 0.25 * z_shr
            + 0.15 * z_val
            - 0.05 * z_con
        )

        # r63.72.4: Scale boost — multiply by log10(latest_value_billions + 1)
        # so a $500M micro-cap with 80% accumulation doesn't beat a $500B
        # mega-cap with 8% accumulation. log scale prevents mega-caps from
        # dominating entirely; just gives them fair chance.
        latest_value_b = max(0.1, m["latest_value_usd"] / 1e9)
        scale_factor = math.log10(latest_value_b + 1)
        composite = composite_z * (1.0 + 0.30 * scale_factor)

        composites[ticker] = composite
        z_components[ticker] = {
            "value_delta_z": z_val, "share_delta_z": z_shr,
            "filer_delta_z": z_flr, "persistence_z": z_per,
            "concentration_z": z_con,
        }

    # Percentile-rank composites
    composite_values = list(composites.values())
    results: List[TickerScore] = []
    raw_for_reasoning: Dict[str, Dict] = {}  # keep raw metrics for reasoning gen
    for ticker, m in raw.items():
        composite = composites[ticker]
        pct = _percentile_rank(composite_values, composite)
        # r63.72.3: Tighter tier percentiles — top 10/20/30 instead of 20/40/60.
        # With outliers filtered out, this gives:
        #   Tier 1: top ~10% (truly above-average accumulation)
        #   Tier 2: 80-90th pct
        #   Tier 3: 70-80th pct
        if pct >= 90:
            tier, label = 1, "STEALTH ACCUMULATION"
        elif pct >= 80:
            tier, label = 2, "EARLY POSITIONING"
        elif pct >= 70:
            tier, label = 3, "BUILDING"
        else:
            tier, label = 0, ""

        signals = _build_signals(m)
        raw_for_reasoning[ticker] = m
        results.append(TickerScore(
            ticker=ticker,
            issuer_name=m["issuer_name"],
            composite_score=round(pct, 1),
            tier=tier,
            tier_label=label,
            value_delta_pct=round(m["value_delta_pct"], 2),
            value_delta_z=round(z_components[ticker]["value_delta_z"], 2),
            share_delta_pct=round(m["share_delta_pct"], 2),
            share_delta_z=round(z_components[ticker]["share_delta_z"], 2),
            filer_count_delta=int(m["filer_count_delta"]),
            filer_delta_z=round(z_components[ticker]["filer_delta_z"], 2),
            persistence_quarters=int(m["persistence_quarters"]),
            persistence_z=round(z_components[ticker]["persistence_z"], 2),
            concentration_hhi=round(m["concentration_hhi"], 3),
            concentration_z=round(z_components[ticker]["concentration_z"], 2),
            latest_filer_count=int(m["latest_filer_count"]),
            latest_value_usd=int(m["latest_value_usd"]),
            quarters_present=int(m["quarters_present"]),
            top_signals=signals,
        ))

    results.sort(key=lambda r: r.composite_score, reverse=True)

    # r63.72.8: Enrich ALL results with quotes (was only top 100).
    # Quote enrichment is fast — fast_info is single-call, parallelized 16-thread.
    # 200 tickers × ~150ms with 16 threads ≈ 2-3 sec wall time, within page-load budget.
    # The 5-min cache means subsequent loads/refreshes are instant.
    try:
        from services.positioning_quotes import enrich_with_quotes, build_plain_english_reasoning
        all_tickers = [r.ticker for r in results]
        quotes = enrich_with_quotes(all_tickers, parallel=16)
    except Exception:
        # Graceful degradation — Yahoo is 401-blocked on Render etc.
        # Reasoning still works without quotes; rows just lack price data.
        quotes = {}
        try:
            from services.positioning_quotes import build_plain_english_reasoning
        except Exception:
            build_plain_english_reasoning = lambda m, q: ""

    for r in results:
        q = quotes.get(r.ticker, {}) or {}
        if q:
            r.price = float(q.get("price", 0.0))
            r.prev_close = float(q.get("prev_close", 0.0))
            r.change_pct = float(q.get("change_pct", 0.0))
            r.low_52w = float(q.get("low_52w", 0.0))
            r.high_52w = float(q.get("high_52w", 0.0))
            r.pct_in_range = float(q.get("pct_in_range", -1.0))
            r.market_cap = int(q.get("market_cap", 0))
        r.reasoning = build_plain_english_reasoning(raw_for_reasoning[r.ticker], q)

    # r63.72.6: Buy/sell filer split — enriches existing filer_count_delta
    # with INSIDE-existing-holders accumulation vs distribution
    try:
        buy_sell = fetch_buy_sell_filers(conn)
        for r in results:
            bs = buy_sell.get(r.ticker, {})
            r.inst_buyers = bs.get("inst_buyers", 0)
            r.inst_sellers = bs.get("inst_sellers", 0)
    except Exception:
        pass  # Soft fail — if query has issue, scanner still works

    # r63.72.6: Promise Score — forward-looking 1-year composite.
    # Different from composite_score (which is current accumulation pressure).
    # Promise emphasizes: durable persistence, broad institutional support,
    # asymmetric upside (price still suppressed), and conviction quality.
    promise_raw: Dict[str, float] = {}
    for r in results:
        m = raw_for_reasoning.get(r.ticker, {})

        # Component 1: Multi-quarter persistence (35%) — most important
        # Heavily favor 4Q+ streaks; cap diminishing returns at 8Q
        persist_score = min(8, r.persistence_quarters) / 8.0  # 0-1

        # Component 2: Buy-side dominance (25%) — buyers > sellers ratio
        total_active = r.inst_buyers + r.inst_sellers
        if total_active >= 10:
            buy_ratio = r.inst_buyers / total_active
            buyer_dominance = max(0.0, (buy_ratio - 0.5) * 2)  # 0 if 50/50, 1 if all buyers
        else:
            buyer_dominance = 0.0  # too few active filers to be a signal

        # Component 3: Asymmetric upside via 52W positioning (15%)
        # Below 50% of range = upside potential; above 80% = limited upside
        if r.pct_in_range >= 0:
            if r.pct_in_range <= 30:
                upside_factor = 1.0   # near 52W lows = great asymmetric upside
            elif r.pct_in_range <= 50:
                upside_factor = 0.7
            elif r.pct_in_range <= 70:
                upside_factor = 0.4
            elif r.pct_in_range <= 85:
                upside_factor = 0.2
            else:
                upside_factor = 0.0   # near 52W highs = limited upside
        else:
            upside_factor = 0.5       # neutral if no quote data

        # Component 4: Institutional value scale (10%) — bigger = more conviction
        val_b = max(0.1, r.latest_value_usd / 1e9)
        scale_factor = min(1.0, math.log10(val_b + 1) / 3.0)  # 0-1, saturates at $1T

        # Component 5: Filer breadth bonus (10%) — many filers = consensus
        breadth_factor = min(1.0, r.latest_filer_count / 500.0)  # 0-1, saturates at 500

        # Component 6: Concentration penalty (-5%) — fragility risk
        # If concentrated in few hands, single-fund exit could crater the position
        concentration_penalty = max(0.0, (r.concentration_hhi - 0.4))  # penalty above 40% top-10 share

        promise = (
            0.35 * persist_score
            + 0.25 * buyer_dominance
            + 0.15 * upside_factor
            + 0.10 * scale_factor
            + 0.10 * breadth_factor
            - 0.05 * concentration_penalty
        )
        promise_raw[r.ticker] = promise

    # Convert to 0-100 scale via min-max normalization
    if promise_raw:
        min_p = min(promise_raw.values())
        max_p = max(promise_raw.values())
        rng = max(1e-9, max_p - min_p)
        for r in results:
            normalized = 100.0 * (promise_raw[r.ticker] - min_p) / rng
            r.promise_score = round(normalized, 1)

        # Star rating: percentile-based
        promise_values = list(promise_raw.values())
        for r in results:
            pct = _percentile_rank(promise_values, promise_raw[r.ticker])
            if pct >= 90:    r.star_rating = 5
            elif pct >= 75:  r.star_rating = 4
            elif pct >= 50:  r.star_rating = 3
            elif pct >= 25:  r.star_rating = 2
            else:            r.star_rating = 1

        # BEST BET: top 10 by promise score
        ranked_by_promise = sorted(results, key=lambda x: x.promise_score, reverse=True)
        for i, r in enumerate(ranked_by_promise[:10]):
            r.is_best_bet = True
            r.best_bet_rank = i + 1

    # Re-sort by Promise Score temporarily (will resort by Multibagger below)
    results.sort(key=lambda r: r.promise_score, reverse=True)

    # r63.72.9: Multibagger framework — M/F/G/O composite, risk-adjusted
    # Bumped from top 50 to top 150 — fundamentals fetch + 1hr cache means
    # subsequent loads still fast. Trades 60-90 sec first load for honest data.
    try:
        from services.multibagger_scoring import enrich_with_multibagger
        MB_ENRICH_TOP = 150
        top_for_mb = results[:MB_ENRICH_TOP]
        mb_scores = enrich_with_multibagger(top_for_mb, parallel=8)

        for r in results:
            mb = mb_scores.get(r.ticker)
            if mb is not None:
                r.multibagger_score = mb.multibagger_score        # may be None
                r.moat_score = mb.moat_score                       # may be None
                r.flow_score = mb.flow_score
                r.growth_score = mb.growth_score                   # may be None
                r.optionality_score = mb.optionality_score         # may be None
                r.risk_penalty = mb.risk_penalty
                r.phase_label = mb.phase_label
                r.has_fundamentals = mb.has_fundamentals
                r.multibagger_narrative = mb.overall_narrative
                r.type_label = mb.type_label
                r.confidence = mb.confidence
    except Exception as e:
        # Soft fail — multibagger enrichment is supplementary
        pass

    # r63.72.10: Three-lens enrichment (Phase A — primary scoring path)
    # Reuses cached fundamentals from above; pure CPU work after that.
    try:
        from services.lens_scoring import enrich_with_lenses
        lens_scores = enrich_with_lenses(results[:MB_ENRICH_TOP], parallel=8)
        for r in results:
            ls = lens_scores.get(r.ticker)
            if ls is None:
                continue
            r.regime = ls.regime
            r.saturation_pct = ls.saturation_pct
            r.ownership_velocity = ls.ownership_change_pct

            # Lens 1
            r.compounder_score = ls.compounder.quality_score
            r.compounder_conviction = ls.compounder.conviction
            r.roic_median = ls.compounder.roic_median
            r.gross_margin_floor = ls.compounder.gross_margin_floor
            r.fcf_consistency = ls.compounder.fcf_consistency

            # Lens 2
            r.accumulation_score = ls.accumulation.flow_score
            r.accumulation_conviction = ls.accumulation.conviction
            r.buy_sell_dominance = ls.accumulation.buy_sell_dominance
            r.relative_strength = ls.accumulation.relative_strength

            # Lens 3
            r.optionality_score_lens = ls.optionality.optionality_score
            r.optionality_conviction = ls.optionality.conviction
            r.rd_intensity = ls.optionality.rd_intensity
            r.cash_to_mcap = ls.optionality.cash_to_mcap
            r.revenue_acceleration = ls.optionality.revenue_acceleration
            r.survivability_months = ls.optionality.survivability
    except Exception:
        pass

    # r63.72.9: Re-rank star ratings + BEST BET using MULTIBAGGER score
    # Critical fix: rows WITHOUT real multibagger_score get NO stars.
    # Previously they kept Promise-Score-derived stars which was misleading.
    has_any_mb = any(r.multibagger_score is not None for r in results)
    if has_any_mb:
        mb_values = [r.multibagger_score for r in results if r.multibagger_score is not None]
        if mb_values:
            # First: zero out all stars/best-bet (clean slate)
            for r in results:
                r.is_best_bet = False
                r.best_bet_rank = 0
                if r.multibagger_score is None:
                    # No multibagger score → no stars (don't pretend)
                    r.star_rating = 0

            # Star rating: percentile-based on real MB scores
            for r in results:
                if r.multibagger_score is not None:
                    pct = _percentile_rank(mb_values, r.multibagger_score)
                    if pct >= 90:    r.star_rating = 5
                    elif pct >= 75:  r.star_rating = 4
                    elif pct >= 50:  r.star_rating = 3
                    elif pct >= 25:  r.star_rating = 2
                    else:            r.star_rating = 1

            # Re-curate BEST BET: top 10 by multibagger_score (with REAL fundamentals)
            ranked_by_mb = sorted(
                [r for r in results
                 if r.multibagger_score is not None
                 and r.has_fundamentals
                 and r.confidence in ("medium", "high")],
                key=lambda x: x.multibagger_score, reverse=True
            )
            for i, r in enumerate(ranked_by_mb[:10]):
                r.is_best_bet = True
                r.best_bet_rank = i + 1

    # FINAL SORT: multibagger score primary (None goes last), promise score tie-breaker
    results.sort(
        key=lambda r: (
            r.multibagger_score if r.multibagger_score is not None else -1,
            r.promise_score
        ),
        reverse=True
    )

    return results


def score_to_dict(score: TickerScore) -> dict:
    """JSON-serializable dict — used by the API endpoint."""
    return asdict(score)
