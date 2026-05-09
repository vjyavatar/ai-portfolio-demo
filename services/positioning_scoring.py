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
    Excludes ETFs and tickers with insufficient data.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ticker,
                   period_of_report::text AS period,
                   COALESCE(MAX(issuer_name), '') AS issuer_name,
                   COUNT(DISTINCT cik) AS filer_count,
                   SUM(value_usd)::bigint AS total_value,
                   SUM(COALESCE(shares, 0))::bigint AS total_shares
            FROM holdings
            WHERE ticker IS NOT NULL
              AND ticker NOT IN %s
              AND value_usd > 0
            GROUP BY ticker, period_of_report
            HAVING COUNT(DISTINCT cik) >= 3
            ORDER BY ticker, period_of_report
            """,
            (tuple(_ETF_TICKERS),),
        )
        rows = cur.fetchall()

    # Group by ticker, fetch top-10 concentration in a second pass to avoid window-fn cost
    snapshots: Dict[str, List[TickerSnapshot]] = {}
    for ticker, period, issuer_name, filer_count, total_value, total_shares in rows:
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
    if snapshots:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH ranked AS (
                    SELECT ticker, period_of_report, cik, SUM(value_usd) AS v,
                           ROW_NUMBER() OVER (PARTITION BY ticker, period_of_report
                                              ORDER BY SUM(value_usd) DESC) AS rn
                    FROM holdings
                    WHERE ticker IS NOT NULL AND value_usd > 0
                    GROUP BY ticker, period_of_report, cik
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
        }

    latest = snaps[-1]
    prior = snaps[-2]

    # Q-over-Q
    value_delta_pct = _safe_pct_change(latest.total_value_usd, prior.total_value_usd)
    share_delta_pct = _safe_pct_change(latest.total_shares, prior.total_shares)
    filer_count_delta = latest.filer_count - prior.filer_count

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
    # Lower top10_share = more diversified accumulation = stronger signal
    # We invert so higher concentration_hhi metric = MORE concentrated (less ideal)
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
    }


def _build_signals(metrics: Dict) -> List[str]:
    """Human-readable top signals for display in the UI."""
    out = []
    if metrics["share_delta_pct"] > 5:
        out.append(f"Share count up {metrics['share_delta_pct']:.1f}% Q/Q")
    elif metrics["share_delta_pct"] < -5:
        out.append(f"Share count down {abs(metrics['share_delta_pct']):.1f}% Q/Q")
    if metrics["filer_count_delta"] > 0:
        out.append(f"+{metrics['filer_count_delta']} net new institutional holders")
    elif metrics["filer_count_delta"] < 0:
        out.append(f"{metrics['filer_count_delta']} net institutional holders")
    if metrics["persistence_quarters"] >= 3:
        out.append(f"{metrics['persistence_quarters']} consecutive Qs of accumulation")
    if metrics["concentration_hhi"] < 0.4 and metrics["latest_filer_count"] > 50:
        out.append(f"Diversified accumulation across {metrics['latest_filer_count']} holders")
    if metrics["latest_value_usd"] >= 100e9:
        out.append(f"${metrics['latest_value_usd']/1e9:,.0f}B aggregate institutional position")
    return out[:4]


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
        raw[ticker] = _compute_metrics(snaps)

    if not raw:
        return []

    # Build distributions for z-scoring
    value_deltas = [m["value_delta_pct"] for m in raw.values()]
    share_deltas = [m["share_delta_pct"] for m in raw.values()]
    filer_deltas = [float(m["filer_count_delta"]) for m in raw.values()]
    persistences = [float(m["persistence_quarters"]) for m in raw.values()]
    concentrations = [m["concentration_hhi"] for m in raw.values()]

    # Composite score: weighted z-score sum, then percentile-rank within universe
    composites: Dict[str, float] = {}
    z_components: Dict[str, Dict] = {}
    for ticker, m in raw.items():
        z_val = _z_score(value_deltas, m["value_delta_pct"])
        z_shr = _z_score(share_deltas, m["share_delta_pct"])
        z_flr = _z_score(filer_deltas, float(m["filer_count_delta"]))
        z_per = _z_score(persistences, float(m["persistence_quarters"]))
        z_con = _z_score(concentrations, m["concentration_hhi"])  # invert below

        # Weights: share delta is the cleanest accumulation signal;
        # value delta is contaminated by price; concentration is inverted.
        composite_z = (
            0.35 * z_shr
            + 0.20 * z_val
            + 0.25 * z_flr
            + 0.15 * z_per
            - 0.05 * z_con  # subtract because high concentration is a negative signal
        )
        composites[ticker] = composite_z
        z_components[ticker] = {
            "value_delta_z": z_val, "share_delta_z": z_shr,
            "filer_delta_z": z_flr, "persistence_z": z_per,
            "concentration_z": z_con,
        }

    # Percentile-rank composites
    composite_values = list(composites.values())
    results: List[TickerScore] = []
    for ticker, m in raw.items():
        composite = composites[ticker]
        pct = _percentile_rank(composite_values, composite)
        if pct >= 80:
            tier, label = 1, "STEALTH ACCUMULATION"
        elif pct >= 60:
            tier, label = 2, "EARLY POSITIONING"
        elif pct >= 40:
            tier, label = 3, "BUILDING"
        else:
            tier, label = 0, ""

        signals = _build_signals(m)
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
    return results


def score_to_dict(score: TickerScore) -> dict:
    """JSON-serializable dict — used by the API endpoint."""
    return asdict(score)
