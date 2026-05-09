"""
r63.71.1 — SEC EDGAR client for 13F-HR filings.

Switched from form.idx (fragile fixed-width parser) to master.idx
(pipe-delimited, unambiguous). master.idx schema:

    CIK|Company Name|Form Type|Date Filed|Filename

Respects SEC's 10 req/sec rate limit and required User-Agent policy.
All requests carry: "Celesys Research vjyavatar@gmail.com" by default.
"""

import os
import re
import time
import threading
from dataclasses import dataclass
from datetime import datetime
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
_last_request_times: list = []


def _wait_for_slot():
    """Token-bucket: ensure no more than _RATE_LIMIT_RPS requests in any 1s window."""
    with _rate_lock:
        now = time.monotonic()
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
    """A row from EDGAR's quarterly master index for 13F-HR filings."""
    cik: str             # zero-padded to 10
    company_name: str
    form_type: str       # "13F-HR" or "13F-HR/A"
    date_filed: str      # "YYYY-MM-DD" (validated)
    accession_no: str    # "0001752724-25-012345" format
    filing_url: str      # full URL to the filing primary doc


def _client() -> httpx.Client:
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
    """Rate-limited, retry-wrapped GET."""
    _wait_for_slot()
    with _client() as client:
        r = client.get(url)
        r.raise_for_status()
        return r.content


# Strict validators: reject malformed rows rather than corrupt the DB
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CIK_RE = re.compile(r"^\d{1,10}$")
_ACC_RE = re.compile(r"^\d{10}-\d{2}-\d{6}$")


def list_13f_filings_for_quarter(year: int, quarter: int) -> List[FilingIndexEntry]:
    """
    Return all 13F-HR filings indexed in a given calendar quarter via master.idx.

    Note: a 13F-HR filed in Q4 2024 reports period 2024-09-30 (Q3 2024).
    Filing-quarter ≠ period-of-report quarter.
    """
    if quarter not in (1, 2, 3, 4):
        raise ValueError(f"quarter must be 1-4, got {quarter}")

    url = f"https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{quarter}/master.idx"
    raw = _get(url)
    text = raw.decode("latin-1")

    entries: List[FilingIndexEntry] = []
    in_data = False
    for line in text.splitlines():
        if not in_data:
            if line.startswith("-" * 10):
                in_data = True
            continue
        if not line or "|" not in line:
            continue

        parts = line.split("|")
        if len(parts) != 5:
            continue

        cik_raw, company, form_type, date_filed, filename = (p.strip() for p in parts)

        if not form_type.startswith("13F-HR"):
            continue

        # Validate every field rather than trust the file
        if not _CIK_RE.match(cik_raw):
            continue
        if not _DATE_RE.match(date_filed):
            continue
        try:
            datetime.strptime(date_filed, "%Y-%m-%d")
        except ValueError:
            continue
        if not filename:
            continue

        # Filename: edgar/data/1234567/0001752724-25-012345.txt
        base = filename.rsplit("/", 1)[-1]
        accession = base[:-4] if base.endswith(".txt") else base
        if not _ACC_RE.match(accession):
            continue

        entries.append(FilingIndexEntry(
            cik=cik_raw.zfill(10),
            company_name=company[:255],
            form_type=form_type,
            date_filed=date_filed,
            accession_no=accession,
            filing_url=f"https://www.sec.gov/Archives/{filename}",
        ))
    return entries


def fetch_information_table_xml(accession_no: str, cik: str) -> Optional[bytes]:
    """
    Fetch the 13F information table XML for a given filing.
    Returns the raw XML bytes, or None if the table can't be located.
    """
    cik_int = str(int(cik))
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
    for it in items:
        nm = (it.get("name") or "").lower()
        if nm.endswith(".xml") and ("infotable" in nm or "informationtable" in nm or "form13f" in nm):
            if "primary_doc" in nm or "primarydoc" in nm:
                continue
            info_table_name = it["name"]
            break
    if not info_table_name:
        for it in items:
            nm = (it.get("name") or "").lower()
            if nm.endswith(".xml") and "primary_doc" not in nm and "primarydoc" not in nm:
                info_table_name = it["name"]
                break
    if not info_table_name:
        return None

    return _get(f"{base}/{info_table_name}")


def fetch_primary_doc_xml(accession_no: str, cik: str) -> Optional[bytes]:
    """
    r63.71.5: Fetch the filing's primary_doc.xml (cover page).

    The cover page is the only place the actual `periodOfReport` lives.
    Without it, we have to heuristic-snap based on filing date, which
    fails on amendments and late filings — that's exactly what caused
    the r63.71.4 backfill to put 7,500+ filings all in the same
    2024-06-30 bucket.

    Returns raw XML bytes, or None if not located.
    """
    cik_int = str(int(cik))
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
    primary_name = None
    for it in items:
        nm = (it.get("name") or "").lower()
        if nm.endswith(".xml") and ("primary_doc" in nm or "primarydoc" in nm):
            primary_name = it["name"]
            break
    if not primary_name:
        return None
    return _get(f"{base}/{primary_name}")
