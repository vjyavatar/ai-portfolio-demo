"""
r63.71 — Database migration runner

Applies db/schema.sql to the database pointed to by NEON_DATABASE_URL.
Idempotent: safe to run multiple times. Uses CREATE TABLE IF NOT EXISTS
and CREATE INDEX IF NOT EXISTS throughout schema.sql.

Usage (local, before deploy):
    export NEON_DATABASE_URL="postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require"
    python db/migrations/001_initial.py

Usage (Render shell, post-deploy):
    python db/migrations/001_initial.py
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


def main():
    db_url = os.environ.get("NEON_DATABASE_URL", "").strip()
    if not db_url:
        print("ERROR: NEON_DATABASE_URL environment variable not set.")
        print("Set it to your Neon pooled connection string (with ?sslmode=require).")
        sys.exit(1)

    # Locate schema.sql relative to this file
    schema_path = Path(__file__).resolve().parent.parent / "schema.sql"
    if not schema_path.exists():
        print(f"ERROR: schema.sql not found at {schema_path}")
        sys.exit(1)

    schema_sql = schema_path.read_text(encoding="utf-8")
    print(f"Applying schema from: {schema_path}")
    print(f"Schema size: {len(schema_sql):,} chars")

    t0 = time.time()
    try:
        # Connection string sanity — never echo password
        host_part = db_url.split("@")[-1].split("/")[0] if "@" in db_url else "(unknown)"
        print(f"Connecting to: {host_part}")

        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(schema_sql)
            conn.commit()
        print(f"OK — schema applied in {time.time() - t0:.2f}s")

        # Verify tables
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                """)
                tables = [r[0] for r in cur.fetchall()]
        expected = {"filers", "filings", "holdings", "cusip_ticker_map",
                    "mapping_overrides", "ingestion_log"}
        present = set(tables)
        missing = expected - present
        if missing:
            print(f"WARNING: expected tables missing: {missing}")
            sys.exit(2)
        print(f"Verified {len(expected)} tables present: {sorted(expected)}")

    except psycopg.OperationalError as e:
        print(f"ERROR connecting/executing: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
