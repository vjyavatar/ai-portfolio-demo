"""
r63.71.5 — Database cleanup: keep top-N filers only.

This script identifies the top-N institutional filers by aggregate AUM
across all currently-ingested holdings, then DELETES every filing,
holding, and CUSIP-map row that doesn't belong to those top filers.

Why: the unfiltered backfill from r63.71.x ingested ~7,500 filings
including a long tail of tiny RIAs and family offices that contribute
filing-count noise but no signal for the institutional positioning
scanner. With Neon's 512 MB free-tier cap nearly hit, we need to free
~60-80% of the storage before we can ingest more quarters.

Default: KEEP top 2000 filers, DELETE the rest.

Run:
    cd celesys_v4_FINAL_DEPLOY
    $env:NEON_DATABASE_URL = "postgresql://..."
    python tools\cleanup_db.py --top-filers 2000

The script is interactive — it shows you exactly what will be
deleted, asks "y/N", and only then runs the destructive query
inside a transaction. Ctrl-C at any prompt aborts cleanly.
"""

import argparse
import os
import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
_ROOT = _THIS.parent.parent
sys.path.insert(0, str(_ROOT))


def _confirm(prompt: str) -> bool:
    """Interactive y/N. Default no."""
    try:
        ans = input(f"{prompt} [y/N]: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\nAborted.")
        return False
    return ans in ("y", "yes")


def _format_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024.0:
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} TB"


def main():
    ap = argparse.ArgumentParser(description="Trim DB to top-N filers by AUM")
    ap.add_argument("--top-filers", type=int, default=2000,
                    help="Number of top filers to keep (default: 2000)")
    ap.add_argument("--yes", action="store_true",
                    help="Skip the confirmation prompt (DANGEROUS — for scripted use only)")
    args = ap.parse_args()

    if not os.environ.get("NEON_DATABASE_URL", "").strip():
        print("ERROR: NEON_DATABASE_URL not set.")
        sys.exit(1)

    # Lazy import after path setup
    from db.connection import get_conn, health_check, close_pool

    h = health_check()
    if not h.get("ok"):
        print(f"ERROR: DB health check failed: {h}")
        sys.exit(1)

    print(f"Cleanup target: keep top {args.top_filers} filers by aggregate AUM")
    print(f"All other filings, holdings, and CUSIPs will be DELETED.")
    print()

    # ─── Pre-flight: show current state ───────────────────────────────────
    print("Current database state:")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM filers")
            n_filers = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM filings")
            n_filings = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM holdings")
            n_holdings = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM cusip_ticker_map")
            n_cusips = cur.fetchone()[0]
            cur.execute("""SELECT pg_size_pretty(SUM(pg_total_relation_size(relid))),
                                  SUM(pg_total_relation_size(relid))
                           FROM pg_catalog.pg_statio_user_tables""")
            row = cur.fetchone()
            size_human, size_bytes = row[0], row[1]
    print(f"  filers:           {n_filers:,}")
    print(f"  filings:          {n_filings:,}")
    print(f"  holdings:         {n_holdings:,}")
    print(f"  cusip_ticker_map: {n_cusips:,}")
    print(f"  storage used:     {size_human} ({size_bytes:,} bytes)")
    print()

    # ─── Identify top filers by aggregate AUM across all their filings ───
    print(f"Computing top {args.top_filers} filers by aggregate AUM...")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH filer_aum AS (
                    SELECT cik, SUM(value_usd) AS total_aum, COUNT(*) AS holdings
                    FROM holdings
                    GROUP BY cik
                )
                SELECT cik, total_aum, holdings
                FROM filer_aum
                ORDER BY total_aum DESC
                LIMIT %s
                """,
                (args.top_filers,),
            )
            top_filers = cur.fetchall()

    if not top_filers:
        print("ERROR: no filers in DB. Did the backfill ever run?")
        sys.exit(1)

    keep_ciks = {row[0] for row in top_filers}
    print(f"  identified {len(keep_ciks):,} top filers")
    print(f"  AUM range: ${top_filers[0][1]/1e9:,.1f}B (top) "
          f"-> ${top_filers[-1][1]/1e9:,.2f}B (cutoff)")
    print()

    # ─── Show what will be deleted ────────────────────────────────────────
    print("Computing impact of cleanup...")
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Use a temp table for the keep-set to avoid a giant IN-list parameter
            cur.execute("CREATE TEMP TABLE _keep_ciks (cik VARCHAR(10) PRIMARY KEY) ON COMMIT DROP")
            cur.executemany("INSERT INTO _keep_ciks (cik) VALUES (%s)",
                            [(c,) for c in keep_ciks])

            cur.execute("""SELECT COUNT(*) FROM filings
                           WHERE cik NOT IN (SELECT cik FROM _keep_ciks)""")
            del_filings = cur.fetchone()[0]

            cur.execute("""SELECT COUNT(*) FROM holdings
                           WHERE cik NOT IN (SELECT cik FROM _keep_ciks)""")
            del_holdings = cur.fetchone()[0]

            cur.execute("""SELECT COUNT(*) FROM filers
                           WHERE cik NOT IN (SELECT cik FROM _keep_ciks)""")
            del_filers = cur.fetchone()[0]

            # CUSIPs that ONLY appear in to-be-deleted holdings (orphans we can drop)
            cur.execute("""
                SELECT COUNT(*)
                FROM cusip_ticker_map m
                WHERE NOT EXISTS (
                    SELECT 1 FROM holdings h
                    WHERE h.cusip = m.cusip
                      AND h.cik IN (SELECT cik FROM _keep_ciks)
                )
            """)
            del_cusips = cur.fetchone()[0]
            conn.commit()

    print(f"  filings to delete:  {del_filings:,} of {n_filings:,} "
          f"({100*del_filings/max(n_filings,1):.1f}%)")
    print(f"  holdings to delete: {del_holdings:,} of {n_holdings:,} "
          f"({100*del_holdings/max(n_holdings,1):.1f}%)")
    print(f"  filers to delete:   {del_filers:,} of {n_filers:,}")
    print(f"  CUSIPs to drop:     {del_cusips:,} of {n_cusips:,} (orphans only)")
    print()
    print(f"  filings AFTER:  {n_filings - del_filings:,}")
    print(f"  holdings AFTER: {n_holdings - del_holdings:,}")
    print(f"  filers AFTER:   {n_filers - del_filers:,}")
    print()

    # ─── Confirm ──────────────────────────────────────────────────────────
    if not args.yes:
        if not _confirm("Proceed with deletion?"):
            print("Aborted.")
            return

    # ─── Execute inside a transaction ────────────────────────────────────
    print("\nExecuting cleanup transaction...")
    with get_conn() as conn:
        try:
            with conn.cursor() as cur:
                # Recreate the keep-set inside this connection (TEMP tables are per-conn)
                cur.execute("CREATE TEMP TABLE _keep_ciks (cik VARCHAR(10) PRIMARY KEY) ON COMMIT DROP")
                cur.executemany("INSERT INTO _keep_ciks (cik) VALUES (%s)",
                                [(c,) for c in keep_ciks])

                # Order matters for FK integrity:
                #   1. holdings (FK -> filings) — but we use ON DELETE CASCADE,
                #      so deleting filings deletes holdings automatically.
                #      We delete holdings explicitly first to avoid timeout on
                #      cascade.
                #   2. filings
                #   3. filers
                #   4. orphan CUSIPs in cusip_ticker_map
                print("  deleting holdings (large table — may take 30-90 sec)...")
                cur.execute("""DELETE FROM holdings
                               WHERE cik NOT IN (SELECT cik FROM _keep_ciks)""")
                print(f"    deleted {cur.rowcount:,} rows")

                print("  deleting filings...")
                cur.execute("""DELETE FROM filings
                               WHERE cik NOT IN (SELECT cik FROM _keep_ciks)""")
                print(f"    deleted {cur.rowcount:,} rows")

                print("  deleting filers...")
                cur.execute("""DELETE FROM filers
                               WHERE cik NOT IN (SELECT cik FROM _keep_ciks)""")
                print(f"    deleted {cur.rowcount:,} rows")

                print("  dropping orphan CUSIPs...")
                cur.execute("""
                    DELETE FROM cusip_ticker_map m
                    WHERE NOT EXISTS (
                        SELECT 1 FROM holdings h
                        WHERE h.cusip = m.cusip
                    )
                """)
                print(f"    deleted {cur.rowcount:,} rows")

            conn.commit()
            print("  COMMITTED")
        except Exception as e:
            conn.rollback()
            print(f"  ROLLED BACK due to error: {e}")
            close_pool()
            sys.exit(1)

    # ─── VACUUM to actually reclaim disk space ───────────────────────────
    # Postgres DELETEs mark rows dead but don't free pages until VACUUM runs.
    # On Neon, autovacuum will eventually reclaim, but VACUUM FULL is
    # immediate — at the cost of an exclusive lock and disk-rewrite time.
    print("\nRunning VACUUM (no FULL, autovacuum-style — will reclaim asynchronously)")
    print("This is non-blocking. Postgres will reclaim space over the next few minutes.")
    with get_conn() as conn:
        # VACUUM cannot run inside a transaction
        conn.autocommit = True
        with conn.cursor() as cur:
            for tbl in ("holdings", "filings", "filers", "cusip_ticker_map"):
                print(f"  VACUUM ANALYZE {tbl}...")
                cur.execute(f"VACUUM ANALYZE {tbl}")
        conn.autocommit = False

    # ─── Final state ─────────────────────────────────────────────────────
    print("\nPost-cleanup state:")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM filers")
            n_filers = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM filings")
            n_filings = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM holdings")
            n_holdings = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM cusip_ticker_map")
            n_cusips = cur.fetchone()[0]
            cur.execute("""SELECT pg_size_pretty(SUM(pg_total_relation_size(relid))),
                                  SUM(pg_total_relation_size(relid))
                           FROM pg_catalog.pg_statio_user_tables""")
            row = cur.fetchone()
            size_human, size_bytes = row[0], row[1]
    print(f"  filers:           {n_filers:,}")
    print(f"  filings:          {n_filings:,}")
    print(f"  holdings:         {n_holdings:,}")
    print(f"  cusip_ticker_map: {n_cusips:,}")
    print(f"  storage used:     {size_human} ({size_bytes:,} bytes)")
    print()
    print("Note: pg_total_relation_size may not drop immediately. Postgres")
    print("autovacuum reclaims space asynchronously — check again in 10-15 min.")
    print()
    print("DONE. Next step: run the focused backfill with:")
    print("  python tools\\backfill_13f.py --quarters 8 --top-filers 2000")

    close_pool()


if __name__ == "__main__":
    main()
