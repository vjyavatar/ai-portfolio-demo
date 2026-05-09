"""
r63.72 — Score dryrun. Runs the scoring engine locally and prints
ranked output. Use to verify rankings make sense before deploying.

    python tools\\score_dryrun.py
    python tools\\score_dryrun.py --top 50
    python tools\\score_dryrun.py --tier 1
"""

import argparse
import os
import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
_ROOT = _THIS.parent.parent
sys.path.insert(0, str(_ROOT))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=25, help="Show top-N (default 25)")
    ap.add_argument("--tier", type=int, default=None, help="Filter to tier 1/2/3")
    args = ap.parse_args()

    if not os.environ.get("NEON_DATABASE_URL", "").strip():
        print("ERROR: NEON_DATABASE_URL not set.")
        sys.exit(1)

    from db.connection import get_conn, close_pool
    from services.positioning_scoring import score_universe

    print("Computing institutional positioning scores across universe...")
    print()

    with get_conn() as conn:
        results = score_universe(conn)

    if not results:
        print("No results. Need at least 2 quarters of data per ticker.")
        sys.exit(0)

    print(f"Universe: {len(results)} tickers scored")
    print()

    # Filter
    show = results
    if args.tier is not None:
        show = [r for r in results if r.tier == args.tier]
    show = show[:args.top]

    # Print
    header = f"{'#':>3}  {'TIER':<4} {'TICKER':<8} {'ISSUER':<32} {'SCORE':>6}  {'SHR Δ%':>8} {'VAL Δ%':>8} {'+FLRS':>6} {'PERSIST':>7}  SIGNALS"
    print(header)
    print("-" * len(header))
    for i, r in enumerate(show, 1):
        tier_str = f"T{r.tier}" if r.tier else "-"
        signals = "; ".join(r.top_signals) if r.top_signals else ""
        print(
            f"{i:>3}  {tier_str:<4} {r.ticker:<8} {r.issuer_name[:30]:<32} "
            f"{r.composite_score:>6.1f}  {r.share_delta_pct:>7.1f}% {r.value_delta_pct:>7.1f}% "
            f"{r.filer_count_delta:>+6d} {r.persistence_quarters:>7d}  {signals[:80]}"
        )

    # Tier counts
    t1 = sum(1 for r in results if r.tier == 1)
    t2 = sum(1 for r in results if r.tier == 2)
    t3 = sum(1 for r in results if r.tier == 3)
    print()
    print(f"Tier 1 (STEALTH ACCUMULATION):  {t1}")
    print(f"Tier 2 (EARLY POSITIONING):     {t2}")
    print(f"Tier 3 (BUILDING):              {t3}")
    print(f"Below threshold:                {len(results) - t1 - t2 - t3}")

    close_pool()


if __name__ == "__main__":
    main()
