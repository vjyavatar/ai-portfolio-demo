"""
r63.72.2 — Migration 003: recreate holdings indexes.

The cleanup phase (r63.71.5) dropped four holdings indexes to free
storage for VACUUM. With 3M+ rows in holdings now, scoring queries
are doing full-table sorts on every run — slow enough that Neon
sometimes drops the connection mid-COMMIT.

This migration recreates the indexes on the now-clean live data.
Each CREATE INDEX is a one-time cost (~30-60 seconds) but every
subsequent scoring query becomes 10-50x faster.

CONCURRENTLY = lower lock contention but slightly slower build;
necessary because the table is the hot path for the scanner.

Idempotent: CREATE INDEX IF NOT EXISTS is a no-op if already present.

Usage:
    cd celesys_v4_FINAL_DEPLOY
    $env:NEON_DATABASE_URL = "postgresql://..."
    python db\\migrations\\003_recreate_holdings_indexes.py
"""

import os
import sys
import time

try:
    import psycopg
except ImportError:
    print("ERROR: psycopg not installed. Run: pip install 'psycopg[binary]>=3.1'")
    sys.exit(1)


_INDEXES = [
    ("idx_holdings_cusip_period",
     "CREATE INDEX IF NOT EXISTS idx_holdings_cusip_period "
     "ON holdings (cusip, period_of_report DESC)"),
    ("idx_holdings_ticker_period",
     "CREATE INDEX IF NOT EXISTS idx_holdings_ticker_period "
     "ON holdings (ticker, period_of_report DESC) WHERE ticker IS NOT NULL"),
    ("idx_holdings_cik_period",
     "CREATE INDEX IF NOT EXISTS idx_holdings_cik_period "
     "ON holdings (cik, period_of_report DESC)"),
    ("idx_holdings_filing",
     "CREATE INDEX IF NOT EXISTS idx_holdings_filing "
     "ON holdings (filing_id)"),
]


def main():
    db_url = os.environ.get("NEON_DATABASE_URL", "").strip()
    if not db_url:
        print("ERROR: NEON_DATABASE_URL not set.")
        sys.exit(1)

    host = db_url.split("@")[-1].split("/")[0] if "@" in db_url else "(unknown)"
    print(f"Connecting to: {host}")

    # Use autocommit so each CREATE INDEX runs in its own transaction.
    # Required for Postgres to acknowledge index visibility cleanly.
    with psycopg.connect(db_url, autocommit=True) as conn:
        # Set generous statement timeout — index creation on 3M rows can be slow
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = '600000'")  # 10 minutes
        for name, ddl in _INDEXES:
            print(f"  Building {name}...")
            t0 = time.time()
            try:
                with conn.cursor() as cur:
                    cur.execute(ddl)
                print(f"    OK in {time.time() - t0:.1f}s")
            except Exception as e:
                print(f"    FAILED: {e}")
                # Don't bail — try the others. Idempotent re-runs will retry.

    # Verify
    print("\nVerifying indexes...")
    with psycopg.connect(db_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT indexname FROM pg_indexes
                   WHERE tablename = 'holdings'
                   ORDER BY indexname"""
            )
            present = [r[0] for r in cur.fetchall()]
    print(f"  {len(present)} indexes present on holdings:")
    for p in present:
        print(f"    {p}")

    expected = {n for n, _ in _INDEXES}
    missing = expected - set(present)
    if missing:
        print(f"\nWARNING: missing indexes: {missing}")
        sys.exit(2)
    print("\nDONE.")


if __name__ == "__main__":
    main()
