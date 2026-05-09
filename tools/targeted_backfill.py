"""
r63.72 — Targeted backfill via data.sec.gov/submissions per-CIK API.

Replaces the calendar-quarter index crawl with a deterministic per-filer
fetch. For each top-N filer, we hit:

    https://data.sec.gov/submissions/CIK##########.json

This returns the filer's complete filing history as JSON. We pick the
last 8 13F-HR submissions (one per quarter), fetch each information
table, parse, and insert.

Why this is better than the index crawl:
- Bounded: top 100 filers × ≤8 quarters = ≤800 work units
- Predictable: each filer's history fits in one JSON response
- No DNS chaos: ~800 deterministic requests, 1-hour run
- Multi-quarter coverage GUARANTEED — we explicitly select 8 most-recent
  filings per filer rather than hoping the calendar crawl ingests them

Usage:
    python tools\\targeted_backfill.py --top-filers 100 --quarters 8
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

_THIS = Path(__file__).resolve()
_ROOT = _THIS.parent.parent
sys.path.insert(0, str(_ROOT))


def _fetch_filer_submissions(cik_padded: str):
    """
    Fetch one filer's complete submissions JSON from data.sec.gov.

    Note: data.sec.gov is a separate hostname from www.sec.gov; we
    construct a fresh httpx client rather than reusing edgar_client's
    (which has Host: www.sec.gov hardcoded).
    """
    import httpx
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    ua = os.environ.get("SEC_USER_AGENT", "Celesys Research vjyavatar@gmail.com")
    headers = {"User-Agent": ua, "Accept-Encoding": "gzip, deflate", "Host": "data.sec.gov"}
    with httpx.Client(timeout=30.0, headers=headers) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.json()


def _extract_13f_filings(submissions_json, max_count: int) -> List[dict]:
    """
    Pull the most recent 13F-HR filings from a filer's submissions JSON.

    Returns list of dicts: {accession_no, filed_date, period_of_report,
                            form_type, primary_document}
    """
    out = []
    recent = submissions_json.get("filings", {}).get("recent", {})
    if not recent:
        return out

    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    filed_dates = recent.get("filingDate", [])
    periods = recent.get("reportDate", [])
    primary_docs = recent.get("primaryDocument", [])

    n = min(len(forms), len(accessions), len(filed_dates), len(periods), len(primary_docs))
    for i in range(n):
        form = forms[i]
        if not (form == "13F-HR" or form == "13F-HR/A"):
            continue
        out.append({
            "accession_no": accessions[i],          # already in dashed format
            "filed_date": filed_dates[i],
            "period_of_report": periods[i],         # YYYY-MM-DD
            "form_type": form,
            "primary_document": primary_docs[i],
        })
        if len(out) >= max_count:
            break
    return out


def main():
    ap = argparse.ArgumentParser(description="Targeted 13F backfill via data.sec.gov submissions API")
    ap.add_argument("--top-filers", type=int, default=100,
                    help="Top-N filers by AUM to fetch from existing DB (default 100)")
    ap.add_argument("--quarters", type=int, default=8,
                    help="Most-recent N quarterly 13F-HR filings per filer (default 8)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Preview filers + filings only; no DB writes")
    args = ap.parse_args()

    if not os.environ.get("NEON_DATABASE_URL", "").strip():
        print("ERROR: NEON_DATABASE_URL not set in this shell.")
        sys.exit(1)
    if not os.environ.get("OPENFIGI_API_KEY", "").strip():
        print("ERROR: OPENFIGI_API_KEY not set in this shell.")
        sys.exit(1)

    from db.connection import get_conn, health_check, close_pool
    from services.edgar_client import fetch_information_table_xml
    from services.holdings_parser import parse_information_table, total_value_and_count
    from services.figi_resolver import resolve_cusips, verify_credentials

    if not health_check().get("ok"):
        print("ERROR: DB unreachable.")
        sys.exit(1)
    print("DB health: OK")

    probe = verify_credentials()
    if not probe.get("ok"):
        print(f"ERROR: OpenFIGI probe failed: {probe.get('reason')}")
        sys.exit(1)
    print(f"OpenFIGI probe: OK (mode={probe['mode']})")

    # Load top-N filer CIKs from existing DB
    print(f"\nLoading top {args.top_filers} filers from existing holdings...")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT h.cik, COALESCE(f.name, ''), SUM(h.value_usd) AS aum
                FROM holdings h
                LEFT JOIN filers f ON f.cik = h.cik
                GROUP BY h.cik, f.name
                ORDER BY aum DESC
                LIMIT %s
                """,
                (args.top_filers,),
            )
            top = cur.fetchall()
    if not top:
        print("ERROR: no filers in DB. Need to run an initial ingest first.")
        sys.exit(1)
    print(f"  loaded {len(top)} filers")
    print(f"  top: {top[0][1][:50]:<50} aum=${float(top[0][2])/1e9:,.0f}B")
    print(f"  cut: {top[-1][1][:50]:<50} aum=${float(top[-1][2])/1e9:,.0f}B")

    # Fetch each filer's submissions, pick last N 13F-HR filings
    print(f"\nFetching submissions JSON for each filer...")
    plan: List[Tuple[str, str, dict]] = []  # (cik, filer_name, filing_dict)
    failed = 0
    for idx, (cik, name, _aum) in enumerate(top):
        try:
            sj = _fetch_filer_submissions(cik)
        except Exception as e:
            print(f"  [{idx+1}/{len(top)}] FAILED submissions for cik={cik} name={name[:30]}: {e}")
            failed += 1
            time.sleep(0.5)
            continue
        filings = _extract_13f_filings(sj, args.quarters)
        for f in filings:
            plan.append((cik, name, f))
        if (idx + 1) % 25 == 0:
            print(f"  [{idx+1}/{len(top)}] queued; total filings to fetch: {len(plan)}")
        # SEC fair-use: 10 req/sec — sleep 0.15s = ~6.6 req/sec, comfortable
        time.sleep(0.15)

    print(f"\nPlan: {len(plan)} filings to fetch from {len(top)} filers ({failed} filers failed)")
    if args.dry_run:
        # Show a sample
        for cik, name, f in plan[:10]:
            print(f"  {cik} {name[:30]:<30} {f['form_type']:<10} period={f['period_of_report']} acc={f['accession_no']}")
        return

    # Ingest each filing
    job_start = time.time()
    inserted = 0
    skipped = 0
    failed_ingest = 0
    holdings_total = 0
    resolved_total = 0

    # Log job
    log_id = None
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO ingestion_log (job_name, status) VALUES (%s, %s) RETURNING id",
                (f"targeted_top{args.top_filers}_q{args.quarters}", "started"),
            )
            log_id = cur.fetchone()[0]
        conn.commit()

    print(f"\nIngesting {len(plan)} filings...")
    for idx, (cik, name, f) in enumerate(plan):
        # Dedup
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM filings WHERE accession_no = %s", (f["accession_no"],))
                    if cur.fetchone():
                        skipped += 1
                        continue
        except Exception as e:
            print(f"  [{idx+1}/{len(plan)}] dedup FAILED: {e}")
            failed_ingest += 1
            continue

        # Upsert filer
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO filers (cik, name) VALUES (%s, %s)
                           ON CONFLICT (cik) DO UPDATE SET name=EXCLUDED.name, last_seen_at=NOW()""",
                        (cik, name),
                    )
                conn.commit()
        except Exception as e:
            print(f"  [{idx+1}/{len(plan)}] filer upsert FAILED for cik={cik}: {e}")
            failed_ingest += 1
            continue

        # Fetch info table
        try:
            xml = fetch_information_table_xml(f["accession_no"], cik)
        except Exception as e:
            print(f"  [{idx+1}/{len(plan)}] info table fetch FAILED {f['accession_no']}: {e}")
            failed_ingest += 1
            continue
        if not xml:
            failed_ingest += 1
            continue

        try:
            holdings = parse_information_table(xml)
        except Exception as e:
            print(f"  [{idx+1}/{len(plan)}] parse FAILED {f['accession_no']}: {e}")
            failed_ingest += 1
            continue
        if not holdings:
            failed_ingest += 1
            continue

        # Resolve CUSIPs
        cusips = list({h.cusip for h in holdings})
        try:
            resolved = resolve_cusips(cusips)
        except Exception as e:
            print(f"  [{idx+1}/{len(plan)}] CUSIP resolve FAILED {f['accession_no']}: {e}")
            resolved = {}
        resolved_count = sum(1 for r in resolved.values() if r.get("ticker"))

        # Insert
        try:
            period = datetime.strptime(f["period_of_report"], "%Y-%m-%d").date()
            filed_at = datetime.strptime(f["filed_date"], "%Y-%m-%d")
            tot_val, tot_count = total_value_and_count(holdings)
            is_amend = f["form_type"].endswith("/A")
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO filings
                           (cik, accession_no, period_of_report, filed_at, form_type,
                            is_amendment, total_value_usd, holdings_count)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                        (cik, f["accession_no"], period, filed_at, f["form_type"],
                         is_amend, tot_val, tot_count),
                    )
                    filing_id = cur.fetchone()[0]
                    rows = [
                        (filing_id, h.cusip, resolved.get(h.cusip, {}).get("ticker"),
                         h.issuer_name, h.title_of_class, h.value_usd, h.shares,
                         h.put_call, h.investment_discretion, period, cik)
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
            inserted += 1
            holdings_total += len(holdings)
            resolved_total += resolved_count
        except Exception as e:
            print(f"  [{idx+1}/{len(plan)}] DB insert FAILED {f['accession_no']}: {e}")
            failed_ingest += 1
            continue

        if (idx + 1) % 25 == 0:
            elapsed = time.time() - job_start
            rate = (inserted + skipped) / max(1, elapsed)
            print(f"  [{idx+1}/{len(plan)}] inserted={inserted} skipped={skipped} "
                  f"failed={failed_ingest} holdings={holdings_total:,} "
                  f"rate={rate:.1f}/s")

    # Wrap up
    elapsed = time.time() - job_start
    print(f"\n=== DONE ===")
    print(f"  filings inserted: {inserted}")
    print(f"  filings skipped (dedup): {skipped}")
    print(f"  filings failed: {failed_ingest}")
    print(f"  holdings inserted: {holdings_total:,}")
    print(f"  CUSIPs resolved:   {resolved_total:,}")
    print(f"  elapsed:           {elapsed/60:.1f} min")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE ingestion_log SET status='ok', filings_processed=%s,
                   holdings_inserted=%s, cusips_resolved=%s, completed_at=NOW()
                   WHERE id=%s""",
                (inserted, holdings_total, resolved_total, log_id),
            )
        conn.commit()

    close_pool()


if __name__ == "__main__":
    main()
