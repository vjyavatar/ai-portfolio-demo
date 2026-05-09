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
import threading
import time
from datetime import date, datetime
from pathlib import Path
from typing import List, Tuple


# r63.71.3: Heartbeat thread — keeps Neon compute awake during long
# FIGI batches (Vanguard with 5K holdings can take 1–2 min of pure
# network I/O, well past Neon's 5-min idle threshold of 300s).
_heartbeat_stop = threading.Event()
_heartbeat_thread = None


def _heartbeat_loop():
    """Ping DB every 120s to prevent Neon scale-to-zero."""
    while not _heartbeat_stop.is_set():
        # Sleep first so we don't double-ping at startup
        if _heartbeat_stop.wait(timeout=120):
            return
        try:
            from db.connection import get_conn
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
        except Exception:
            # Heartbeat is best-effort; don't spam logs if it fails
            pass


def _start_heartbeat():
    global _heartbeat_thread
    _heartbeat_stop.clear()
    _heartbeat_thread = threading.Thread(
        target=_heartbeat_loop, name="neon-heartbeat", daemon=True
    )
    _heartbeat_thread.start()


def _stop_heartbeat():
    _heartbeat_stop.set()
    if _heartbeat_thread is not None:
        _heartbeat_thread.join(timeout=3)

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
    ap.add_argument("--top-filers", type=int, default=None,
                    help="r63.71.5: ingest filings ONLY from the top-N filers by AUM "
                         "already present in the DB. Skip filings from other CIKs entirely. "
                         "Pass 2000 to filter to top 2K filers (recommended for free-tier Neon).")
    ap.add_argument("--dry-run", action="store_true", help="List filings, do not ingest")
    args = ap.parse_args()

    # Validate env (r63.71.2: hard-check OpenFIGI key too)
    missing = [v for v in ("NEON_DATABASE_URL",) if not os.environ.get(v)]
    if missing:
        print(f"ERROR: missing env vars: {missing}")
        sys.exit(1)

    # r63.71.2: OpenFIGI key check — without it the backfill will be ~20x slower
    # and consistently 413 on batches >5. Better to fail loud than grind.
    if not os.environ.get("OPENFIGI_API_KEY", "").strip():
        print("ERROR: OPENFIGI_API_KEY is not set in this shell.")
        print()
        print("In PowerShell:")
        print("    $env:OPENFIGI_API_KEY = 'your-openfigi-api-key'")
        print()
        print("Note: PowerShell env vars do NOT persist across windows.")
        print("If you set it in another window, set it again here.")
        sys.exit(1)

    # Import after path setup
    from db.connection import get_conn, health_check
    from services.edgar_client import (
        list_13f_filings_for_quarter,
        fetch_information_table_xml,
        fetch_primary_doc_xml,
    )
    from services.holdings_parser import (
        parse_information_table,
        total_value_and_count,
        parse_period_of_report,
    )
    from services.figi_resolver import resolve_cusips, verify_credentials

    h = health_check()
    if not h.get("ok"):
        print(f"ERROR: DB health check failed: {h}")
        sys.exit(1)
    print(f"DB health: OK")

    # r63.71.2: Probe OpenFIGI before kicking off the backfill loop.
    # Catches: invalid keys, network blocks, suspended accounts, etc.
    print("Verifying OpenFIGI credentials...")
    probe = verify_credentials()
    if not probe.get("ok"):
        print(f"ERROR: OpenFIGI probe failed: {probe.get('reason')}")
        print("Backfill aborted — fix the FIGI access issue and re-run.")
        sys.exit(1)
    print(f"OpenFIGI probe: OK (ticker={probe['ticker']}, mode={probe['mode']})")

    # r63.71.5: Load top-filer CIK whitelist if --top-filers was passed
    top_filer_ciks = None  # None = no filter; set = filter active
    if args.top_filers is not None and args.top_filers > 0:
        from db.connection import get_conn as _gc
        with _gc() as _conn:
            with _conn.cursor() as _cur:
                _cur.execute(
                    """
                    SELECT cik
                    FROM (
                        SELECT cik, SUM(value_usd) AS total_aum
                        FROM holdings
                        GROUP BY cik
                    ) AS x
                    ORDER BY total_aum DESC
                    LIMIT %s
                    """,
                    (args.top_filers,),
                )
                top_filer_ciks = {r[0] for r in _cur.fetchall()}
        if not top_filer_ciks:
            print(f"ERROR: --top-filers={args.top_filers} but DB has no holdings to compute top filers from.")
            print("       Run an unfiltered ingest of at least one quarter first.")
            sys.exit(1)
        print(f"Filter mode: top {len(top_filer_ciks):,} filers loaded from existing holdings")

    # r63.71.3: Start Neon-keepalive heartbeat
    _start_heartbeat()
    print("Heartbeat thread started (pings DB every 120s to prevent Neon scale-to-zero)")

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

                # r63.71.5: Top-filer filter — skip filings outside the whitelist
                # before doing any DB or network work. This is the primary
                # mechanism that keeps the focused backfill within Neon's storage.
                if top_filer_ciks is not None and ent.cik not in top_filer_ciks:
                    continue

                # Skip if already ingested (r63.71.3: retry on stale connection)
                _dedup_skip = False
                _dedup_attempts = 0
                while _dedup_attempts < 2:
                    _dedup_attempts += 1
                    try:
                        with get_conn() as conn:
                            with conn.cursor() as cur:
                                cur.execute(
                                    "SELECT 1 FROM filings WHERE accession_no = %s",
                                    (ent.accession_no,),
                                )
                                if cur.fetchone():
                                    _dedup_skip = True
                        break
                    except Exception as e:
                        if _dedup_attempts < 2 and any(s in str(e).lower() for s in
                            ("server closed", "consuming input failed", "connection is closed",
                             "ssl syscall", "connection bad")):
                            try:
                                from db.connection import close_pool
                                close_pool()
                            except Exception:
                                pass
                            time.sleep(2)
                            continue
                        print(f"  [{i+1}/{len(entries)}] dedup check FAILED: {e}")
                        _dedup_skip = True
                        break
                if _dedup_skip:
                    continue

                # Upsert filer (r63.71.1: error-isolated; r63.71.3: retry on stale)
                _upsert_attempts = 0
                _upsert_ok = False
                while _upsert_attempts < 2:
                    _upsert_attempts += 1
                    try:
                        with get_conn() as conn:
                            with conn.cursor() as cur:
                                cur.execute(
                                    """INSERT INTO filers (cik, name) VALUES (%s, %s)
                                       ON CONFLICT (cik) DO UPDATE SET
                                         name = EXCLUDED.name, last_seen_at = NOW()""",
                                    (ent.cik, ent.company_name),
                                )
                            conn.commit()
                        _upsert_ok = True
                        break
                    except Exception as e:
                        if _upsert_attempts < 2 and any(s in str(e).lower() for s in
                            ("server closed", "consuming input failed", "connection is closed",
                             "ssl syscall", "connection bad")):
                            try:
                                from db.connection import close_pool
                                close_pool()
                            except Exception:
                                pass
                            time.sleep(2)
                            continue
                        print(f"  [{i+1}/{len(entries)}] filer upsert FAILED for cik={ent.cik!r}: {e}")
                        break
                if not _upsert_ok:
                    continue

                # Fetch + parse the information table
                try:
                    xml = fetch_information_table_xml(ent.accession_no, ent.cik)
                except Exception as e:
                    print(f"  [{i+1}/{len(entries)}] fetch FAILED for {ent.accession_no}: {e}")
                    continue
                if not xml:
                    print(f"  [{i+1}/{len(entries)}] no info table for {ent.accession_no}")
                    continue

                # r63.71.4: parser must never FATAL the run — wrap in try/except
                try:
                    holdings = parse_information_table(xml)
                except Exception as e:
                    print(f"  [{i+1}/{len(entries)}] parse FAILED for {ent.accession_no}: {e}")
                    continue
                if not holdings:
                    continue

                # r63.71.5: Fetch the cover page to get the AUTHORITATIVE
                # periodOfReport. The old heuristic snapped to most-recent
                # quarter-end before filing date — wrong for amendments and
                # late filings. That bug is what put 7,500 filings in the
                # 2024-06-30 bucket in r63.71.4.
                try:
                    primary_xml = fetch_primary_doc_xml(ent.accession_no, ent.cik)
                except Exception as e:
                    print(f"  [{i+1}/{len(entries)}] primary_doc fetch FAILED for {ent.accession_no}: {e}")
                    continue
                period = parse_period_of_report(primary_xml) if primary_xml else None
                if period is None:
                    # Fall back to heuristic only if cover page is missing/unparseable
                    period = _period_from_filing_date(ent.date_filed)
                    print(f"  [{i+1}/{len(entries)}] WARN: period from heuristic for {ent.accession_no}")

                tot_val, tot_count = total_value_and_count(holdings)
                is_amend = ent.form_type.endswith("/A")

                # Resolve CUSIPs to tickers in batch (r63.71.4: never FATAL)
                cusip_set = list({h.cusip for h in holdings})
                try:
                    resolved = resolve_cusips(cusip_set)
                except Exception as e:
                    print(f"  [{i+1}/{len(entries)}] CUSIP resolve FAILED for {ent.accession_no}: {e}")
                    print(f"  [{i+1}/{len(entries)}] continuing with no ticker resolutions for this filing")
                    resolved = {}
                resolved_count = sum(1 for r in resolved.values() if r.get("ticker"))

                # Insert filing + holdings transactionally
                # r63.71.3: Retry once on stale-connection errors (Neon scale-to-zero)
                _insert_attempts = 0
                _insert_max_attempts = 2
                while _insert_attempts < _insert_max_attempts:
                    _insert_attempts += 1
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
                        break  # success — exit retry loop
                    except Exception as e:
                        emsg = str(e).lower()
                        is_stale = (
                            "server closed the connection unexpectedly" in emsg
                            or "consuming input failed" in emsg
                            or "connection is closed" in emsg
                            or "ssl syscall" in emsg
                            or "connection bad" in emsg
                        )
                        if is_stale and _insert_attempts < _insert_max_attempts:
                            print(f"  [{i+1}/{len(entries)}] stale connection — retrying once "
                                  f"(Neon scale-to-zero recovery)")
                            # Trigger pool reconnect by closing it; lazy-init on next call
                            try:
                                from db.connection import close_pool
                                close_pool()
                            except Exception:
                                pass
                            time.sleep(2)
                            continue
                        # Other error or retries exhausted — log and skip
                        print(f"  [{i+1}/{len(entries)}] DB insert FAILED for {ent.accession_no}: {e}")
                        break
                else:
                    # while-else: only runs if while exits without break
                    continue
                # Check whether the loop broke on success or on failure
                # by looking at whether filing was actually inserted (defensive)
                try:
                    with get_conn() as _vc:
                        with _vc.cursor() as _vcur:
                            _vcur.execute(
                                "SELECT 1 FROM filings WHERE accession_no = %s",
                                (ent.accession_no,))
                            if not _vcur.fetchone():
                                continue  # insert failed — skip the counter bump
                except Exception:
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

    # r63.71.3: Stop heartbeat thread cleanly
    _stop_heartbeat()

    # r63.71.1: Explicit pool close — silences "couldn't stop thread" warnings
    try:
        from db.connection import close_pool
        close_pool()
    except Exception:
        pass


if __name__ == "__main__":
    main()
