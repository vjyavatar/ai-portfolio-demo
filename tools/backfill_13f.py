"""
r63.71 — 8-quarter 13F-HR backfill orchestrator.

Run from your laptop, not from Render. Single-shot, resumable.

Setup:
    cd celesys_v4_FINAL_DEPLOY
    pip install -r requirements.txt
    export NEON_DATABASE_URL='postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require'
    export OPENFIGI_API_KEY='your-figi-key-here'
    export SEC_USER_AGENT='Celesys Research vjyavatar@gmail.com'

Run migration first (one time):
    python db/migrations/001_initial.py

Then backfill:
    python tools/backfill_13f.py --quarters 8

Resume after interrupt — re-run the same command. Already-ingested
filings are skipped via the unique constraint on filings.accession_no.

Estimated runtime for 8 quarters of all 13F-HR filings: 4–6 hours.
You can leave this running overnight. Progress is logged every filing.
"""

import argparse
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import List, Tuple

# Ensure the project root is on sys.path so we can import db / services
_THIS = Path(__file__).resolve()
_ROOT = _THIS.parent.parent
sys.path.insert(0, str(_ROOT))


def _quarters_back(n: int) -> List[Tuple[int, int]]:
    """Return the last N filing-quarters as (year, quarter) tuples, oldest first."""
    today = date.today()
    cur_q = (today.month - 1) // 3 + 1
    cur_y = today.year
    out = []
    for _ in range(n):
        out.append((cur_y, cur_q))
        cur_q -= 1
        if cur_q == 0:
            cur_q = 4
            cur_y -= 1
    out.reverse()
    return out


def _period_from_filing_date(filed_str: str) -> date:
    """13F-HR reports the prior quarter-end. Filed in Jan-Feb → prior Q (Sep 30)."""
    # We don't actually use filed_str to derive period — the parser handles it
    # via the primary_doc.xml header. But for index-level dedup we just need
    # SOMETHING reasonable. Use filed-date - ~60 days, snap to quarter end.
    try:
        d = datetime.strptime(filed_str, "%Y-%m-%d").date()
    except ValueError:
        d = date.today()
    # Snap to most recent quarter-end before filing date
    for cand_m, cand_d in [(12, 31), (9, 30), (6, 30), (3, 31)]:
        if (d.month, d.day) >= (cand_m, cand_d):
            return date(d.year, cand_m, cand_d)
        # Try previous year's Dec 31 for early-year filings
    return date(d.year - 1, 12, 31)


def main():
    ap = argparse.ArgumentParser(description="13F-HR backfill into Celesys positioning DB")
    ap.add_argument("--quarters", type=int, default=8, help="How many filing-quarters back to ingest")
    ap.add_argument("--max-filings", type=int, default=None, help="Cap total filings (testing)")
    ap.add_argument("--dry-run", action="store_true", help="List filings, do not ingest")
    args = ap.parse_args()

    # Validate env
    missing = [v for v in ("NEON_DATABASE_URL",) if not os.environ.get(v)]
    if missing:
        print(f"ERROR: missing env vars: {missing}")
        sys.exit(1)

    # Import after path setup
    from db.connection import get_conn, health_check
    from services.edgar_client import list_13f_filings_for_quarter, fetch_information_table_xml
    from services.holdings_parser import parse_information_table, total_value_and_count
    from services.figi_resolver import resolve_cusips

    h = health_check()
    if not h.get("ok"):
        print(f"ERROR: DB health check failed: {h}")
        sys.exit(1)
    print(f"DB health: OK")

    quarters = _quarters_back(args.quarters)
    print(f"Backfill plan: {quarters}")

    # Log job start
    job_name = f"backfill_{quarters[0][0]}Q{quarters[0][1]}_to_{quarters[-1][0]}Q{quarters[-1][1]}"
    log_id = None
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO ingestion_log (job_name, status) VALUES (%s, %s) RETURNING id""",
                (job_name, "started"),
            )
            log_id = cur.fetchone()[0]
        conn.commit()

    total_filings = 0
    total_holdings = 0
    total_resolved = 0
    job_start = time.time()

    try:
        for (yr, qtr) in quarters:
            print(f"\n=== Filing-quarter {yr}Q{qtr} ===")
            entries = list_13f_filings_for_quarter(yr, qtr)
            print(f"  index: {len(entries)} 13F-HR entries")

            if args.dry_run:
                continue

            for i, ent in enumerate(entries):
                if args.max_filings and total_filings >= args.max_filings:
                    print(f"  hit --max-filings cap, stopping")
                    break

                # Skip if already ingested
                with get_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT 1 FROM filings WHERE accession_no = %s",
                            (ent.accession_no,),
                        )
                        if cur.fetchone():
                            continue

                # Upsert filer
                with get_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """INSERT INTO filers (cik, name) VALUES (%s, %s)
                               ON CONFLICT (cik) DO UPDATE SET
                                 name = EXCLUDED.name, last_seen_at = NOW()""",
                            (ent.cik, ent.company_name),
                        )
                    conn.commit()

                # Fetch + parse the information table
                try:
                    xml = fetch_information_table_xml(ent.accession_no, ent.cik)
                except Exception as e:
                    print(f"  [{i+1}/{len(entries)}] fetch FAILED for {ent.accession_no}: {e}")
                    continue
                if not xml:
                    print(f"  [{i+1}/{len(entries)}] no info table for {ent.accession_no}")
                    continue

                holdings = parse_information_table(xml)
                if not holdings:
                    continue

                period = _period_from_filing_date(ent.date_filed)
                tot_val, tot_count = total_value_and_count(holdings)
                is_amend = ent.form_type.endswith("/A")

                # Resolve CUSIPs to tickers in batch
                cusip_set = list({h.cusip for h in holdings})
                resolved = resolve_cusips(cusip_set)
                resolved_count = sum(1 for r in resolved.values() if r.get("ticker"))

                # Insert filing + holdings transactionally
                try:
                    with get_conn() as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                """INSERT INTO filings
                                   (cik, accession_no, period_of_report, filed_at,
                                    form_type, is_amendment, total_value_usd, holdings_count)
                                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                   RETURNING id""",
                                (ent.cik, ent.accession_no, period,
                                 datetime.strptime(ent.date_filed, "%Y-%m-%d"),
                                 ent.form_type, is_amend, tot_val, tot_count),
                            )
                            filing_id = cur.fetchone()[0]

                            rows = [
                                (filing_id, h.cusip,
                                 resolved.get(h.cusip, {}).get("ticker"),
                                 h.issuer_name, h.title_of_class,
                                 h.value_usd, h.shares, h.put_call,
                                 h.investment_discretion, period, ent.cik)
                                for h in holdings
                            ]
                            cur.executemany(
                                """INSERT INTO holdings
                                   (filing_id, cusip, ticker, issuer_name, title_of_class,
                                    value_usd, shares, put_call, investment_discretion,
                                    period_of_report, cik)
                                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                                rows,
                            )
                        conn.commit()
                except Exception as e:
                    print(f"  [{i+1}/{len(entries)}] DB insert FAILED for {ent.accession_no}: {e}")
                    continue

                total_filings += 1
                total_holdings += len(holdings)
                total_resolved += resolved_count

                if total_filings % 25 == 0:
                    elapsed = time.time() - job_start
                    rate = total_filings / max(1, elapsed)
                    print(f"  progress: {total_filings} filings · {total_holdings:,} holdings · "
                          f"{total_resolved:,} resolved · {rate:.1f} filings/sec")

            if args.max_filings and total_filings >= args.max_filings:
                break

        status = "ok"
    except KeyboardInterrupt:
        print("\nInterrupted — partial progress preserved. Re-run to resume.")
        status = "partial"
    except Exception as e:
        print(f"\nFATAL: {e}")
        status = "failed"

    # Update ingestion log
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE ingestion_log SET status=%s, filings_processed=%s,
                   holdings_inserted=%s, cusips_resolved=%s, completed_at=NOW()
                   WHERE id=%s""",
                (status, total_filings, total_holdings, total_resolved, log_id),
            )
        conn.commit()

    elapsed_min = (time.time() - job_start) / 60
    print(f"\n=== DONE ({status}) ===")
    print(f"  filings ingested:  {total_filings:,}")
    print(f"  holdings inserted: {total_holdings:,}")
    print(f"  CUSIPs resolved:   {total_resolved:,}")
    print(f"  elapsed:           {elapsed_min:.1f} min")


if __name__ == "__main__":
    main()
