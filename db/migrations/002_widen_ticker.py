"""
r63.71.1 — Migration 002: widen ticker columns to VARCHAR(20).

Background: r63.71's smoke test surfaced a VARCHAR(10) overflow on the
ticker column. Root cause was a CIK overflow from a fragile EDGAR
form.idx parser (fixed in r63.71.1 by switching to master.idx), but
ticker columns also need defensive headroom — OpenFIGI returns
foreign-listing suffixes like "BRK/B US" and class-share variants that
can exceed 10 characters.

This migration widens ticker columns on holdings, cusip_ticker_map, and
mapping_overrides from VARCHAR(10) to VARCHAR(20). In Postgres, ALTER
COLUMN TYPE on a varlena type with no length constraint check failure
is a metadata-only operation — instant on any table size.

Idempotent: ALTER ... TYPE varchar(20) is a no-op if already that size,
but we use information_schema to skip it gracefully if already migrated.

Usage:
    export NEON_DATABASE_URL='postgresql://...'
    python db/migrations/002_widen_ticker.py
"""

import os
import sys
import time
from pathlib import Path

try:
    import psycopg
except ImportError:
    print("ERROR: psycopg not installed. Run: pip install 'psycopg[binary]>=3.1'")
    sys.exit(1)


_TARGETS = [
    ("holdings", "ticker", 20),
    ("cusip_ticker_map", "ticker", 20),
    ("mapping_overrides", "ticker", 20),
]


def _current_max_len(cur, table: str, column: str):
    cur.execute(
        """
        SELECT character_maximum_length
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
          AND column_name = %s
        """,
        (table, column),
    )
    row = cur.fetchone()
    return row[0] if row else None


def main():
    db_url = os.environ.get("NEON_DATABASE_URL", "").strip()
    if not db_url:
        print("ERROR: NEON_DATABASE_URL environment variable not set.")
        sys.exit(1)

    host_part = db_url.split("@")[-1].split("/")[0] if "@" in db_url else "(unknown)"
    print(f"Connecting to: {host_part}")

    t0 = time.time()
    altered = 0
    skipped = 0

    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                for table, column, target_len in _TARGETS:
                    cur_len = _current_max_len(cur, table, column)
                    if cur_len is None:
                        print(f"  SKIP {table}.{column}: column not found")
                        skipped += 1
                        continue
                    if cur_len >= target_len:
                        print(f"  SKIP {table}.{column}: already VARCHAR({cur_len})")
                        skipped += 1
                        continue
                    print(f"  ALTER {table}.{column}: VARCHAR({cur_len}) -> VARCHAR({target_len})")
                    cur.execute(
                        f"ALTER TABLE {table} ALTER COLUMN {column} TYPE VARCHAR({target_len})"
                    )
                    altered += 1
            conn.commit()
        print(f"OK — {altered} altered, {skipped} skipped in {time.time() - t0:.2f}s")

    except psycopg.OperationalError as e:
        print(f"ERROR connecting/executing: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
