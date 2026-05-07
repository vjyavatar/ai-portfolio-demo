"""
r63.71 — SEC EDGAR client for 13F-HR filings.

Respects SEC's 10 req/sec rate limit and required User-Agent policy.
All requests carry: "Celesys Research vjyavatar@gmail.com"

This module provides:
- list_13f_filings_for_quarter(period_end) → list of filing index entries
- fetch_13f_information_table(accession_no, cik) → raw XML bytes
- A token-bucket rate limiter shared across all calls

References:
- https://www.sec.gov/os/accessing-edgar-data
- https://www.sec.gov/Archives/edgar/full-index/  (quarterly indices)
"""

import os
import time
import threading
from dataclasses import dataclass
from typing import List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# ─── Compliance: SEC requires User-Agent with contact info ───
SEC_USER_AGENT = os.environ.get(
    "SEC_USER_AGENT",
    "Celesys Research vjyavatar@gmail.com"
)

# ─── Rate limiting: SEC allows ~10 req/sec; we target 8 to leave headroom ───
_RATE_LIMIT_RPS = 8
_rate_lock = threading.Lock()
_last_request_times: list = []  # rolling window of request timestamps


def _wait_for_slot():
    """Token-bucket: ensure no more than _RATE_LIMIT_RPS requests in any 1s window."""
    with _rate_lock:
        now = time.monotonic()
        # Drop timestamps older than 1 second
        cutoff = now - 1.0
        while _last_request_times and _last_request_times[0] < cutoff:
            _last_request_times.pop(0)
        if len(_last_request_times) >= _RATE_LIMIT_RPS:
            sleep_for = 1.0 - (now - _last_request_times[0]) + 0.01
            if sleep_for > 0:
                time.sleep(sleep_for)
        _last_request_times.append(time.monotonic())


@dataclass
class FilingIndexEntry:
    """A row from EDGAR's quarterly form index for 13F-HR filings."""
    cik: str             # zero-padded to 10
    company_name: str
    form_type: str       # "13F-HR" or "13F-HR/A"
    date_filed: str      # "YYYY-MM-DD"
    accession_no: str    # "0001752724-25-012345" format
    filing_url: str      # full URL to the filing index


def _client() -> httpx.Client:
    """Create an httpx client with SEC-compliant headers."""
    return httpx.Client(
        headers={
            "User-Agent": SEC_USER_AGENT,
            "Accept-Encoding": "gzip, deflate",
            "Host": "www.sec.gov",
        },
        timeout=30.0,
        follow_redirects=True,
    )


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True,
)
def _get(url: str) -> bytes:
    """Rate-limited, retry-wrapped GET. Returns raw bytes."""
    _wait_for_slot()
    with _client() as client:
        r = client.get(url)
        r.raise_for_status()
        return r.content


def list_13f_filings_for_quarter(year: int, quarter: int) -> List[FilingIndexEntry]:
    """
    Return all 13F-HR filings indexed in a given calendar quarter.

    Note: a 13F-HR filed in Q4 2024 typically reports period 2024-09-30
    (Q3 2024). Filing-quarter ≠ period-of-report quarter.

    Args:
        year: 4-digit calendar year of the FILING quarter (not period-of-report)
        quarter: 1, 2, 3, or 4

    Returns:
        List of FilingIndexEntry, filtered to form_type starting with "13F-HR".
    """
    if quarter not in (1, 2, 3, 4):
        raise ValueError(f"quarter must be 1-4, got {quarter}")

    url = f"https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{quarter}/form.idx"
    raw = _get(url)
    text = raw.decode("latin-1")  # form.idx is latin-1, not utf-8

    entries: List[FilingIndexEntry] = []
    # form.idx header is variable-length; data rows are fixed-width.
    # Skip until we hit the dashed separator line, then parse columns.
    in_data = False
    for line in text.splitlines():
        if not in_data:
            if line.startswith("-" * 10):
                in_data = True
            continue
        # Filter to 13F-HR or 13F-HR/A only (cheaper to substring-check first)
        if not line.startswith("13F-HR"):
            continue
        # Fixed-width parse — columns documented in form.idx header
        # Form Type | Company Name | CIK | Date Filed | Filename
        try:
            form_type = line[0:12].strip()
            company   = line[12:74].strip()
            cik       = line[74:86].strip()
            date_fld  = line[86:98].strip()
            filename  = line[98:].strip()
            if not (form_type.startswith("13F-HR") and cik and filename):
                continue
            # Extract accession no from filename like:
            # edgar/data/1234567/0001752724-25-012345-index.htm
            accession = filename.rsplit("/", 1)[-1].replace("-index.htm", "").replace(".txt", "")
            entries.append(FilingIndexEntry(
                cik=cik.zfill(10),
                company_name=company,
                form_type=form_type,
                date_filed=date_fld,
                accession_no=accession,
                filing_url=f"https://www.sec.gov/Archives/{filename}",
            ))
        except Exception:
            continue
    return entries


def fetch_information_table_xml(accession_no: str, cik: str) -> Optional[bytes]:
    """
    Fetch the 13F information table XML for a given filing.

    EDGAR stores filings at:
        https://www.sec.gov/Archives/edgar/data/{cik_no_pad}/{accession_no_dashes_removed}/

    The information table is typically named:
        Form13FInfoTable.xml  OR  infotable.xml  OR  primary_doc_xxxxx.xml

    We fetch the filing index JSON first, then locate the information table.

    Returns the raw XML bytes, or None if the table can't be located.
    """
    cik_int = str(int(cik))  # strip leading zeros for URL
    accession_clean = accession_no.replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_clean}"
    index_url = f"{base}/index.json"

    raw = _get(index_url)
    import json
    try:
        idx = json.loads(raw)
    except Exception:
        return None

    items = idx.get("directory", {}).get("item", [])
    info_table_name = None
    # Heuristic search: the information table XML is usually named with
    # "infotable", "informationtable", or "Form13FInfoTable" in it.
    for it in items:
        nm = (it.get("name") or "").lower()
        if nm.endswith(".xml") and ("infotable" in nm or "informationtable" in nm or "form13f" in nm):
            # Skip the primary_doc.xml (header) — we want info table only
            if "primary_doc" in nm or "primarydoc" in nm:
                continue
            info_table_name = it["name"]
            break
    # Fallback: any non-primary_doc XML
    if not info_table_name:
        for it in items:
            nm = (it.get("name") or "").lower()
            if nm.endswith(".xml") and "primary_doc" not in nm and "primarydoc" not in nm:
                info_table_name = it["name"]
                break
    if not info_table_name:
        return None

    return _get(f"{base}/{info_table_name}")
