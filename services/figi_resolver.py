"""
r63.71 — CUSIP → ticker resolution via OpenFIGI.

Resolution priority (queried in order):
  1. mapping_overrides table (manual corrections — highest priority)
  2. cusip_ticker_map cache (previous OpenFIGI resolutions)
  3. OpenFIGI live API (caches result on success or failure)

OpenFIGI free tier: 5 req/sec, 25/min.
With OPENFIGI_API_KEY: 25 req/sec, 250/min.

OpenFIGI accepts up to 100 mapping requests per HTTP call (batch endpoint).
We exploit this to keep total wall time low during backfill.

Critical: a CUSIP that returns no FIGI match still gets cached as
"unresolved" so we don't re-query it on every backfill run.
"""

import os
import time
import threading
from typing import Dict, List, Optional, Tuple

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

OPENFIGI_API_KEY = os.environ.get("OPENFIGI_API_KEY", "").strip()
OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"

# Rate limiter (requests/sec depending on key presence)
_RPS = 25 if OPENFIGI_API_KEY else 5
_BATCH_SIZE = 100  # OpenFIGI per-call cap

_rate_lock = threading.Lock()
_request_times: list = []


def _wait_for_slot():
    with _rate_lock:
        now = time.monotonic()
        cutoff = now - 1.0
        while _request_times and _request_times[0] < cutoff:
            _request_times.pop(0)
        if len(_request_times) >= _RPS:
            sleep_for = 1.0 - (now - _request_times[0]) + 0.02
            if sleep_for > 0:
                time.sleep(sleep_for)
        _request_times.append(time.monotonic())


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if OPENFIGI_API_KEY:
        h["X-OPENFIGI-APIKEY"] = OPENFIGI_API_KEY
    return h


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True,
)
def _figi_batch_request(cusips: List[str]) -> List[dict]:
    """Send up to 100 CUSIPs in one OpenFIGI call. Returns parallel result list."""
    _wait_for_slot()
    payload = [{"idType": "ID_CUSIP", "idValue": c} for c in cusips]
    with httpx.Client(timeout=30.0) as client:
        r = client.post(OPENFIGI_URL, headers=_headers(), json=payload)
        r.raise_for_status()
        return r.json()


def resolve_cusips(cusips: List[str]) -> Dict[str, dict]:
    """
    Resolve a batch of CUSIPs via the database cache + OpenFIGI fallback.

    Returns: {cusip: {"ticker": str|None, "figi": str|None, "name": str,
                      "exchange": str, "security_type": str, "confidence": str}}

    Confidence values:
        "manual"     — from mapping_overrides
        "figi"       — resolved live or cached from FIGI
        "unresolved" — looked up but FIGI returned no match (cached)
    """
    if not cusips:
        return {}

    # Lazy import to avoid coupling at module load
    from db.connection import get_conn

    cusips = list(set(c.strip().upper() for c in cusips if c and c.strip()))
    out: Dict[str, dict] = {}
    to_query: List[str] = []

    with get_conn() as conn:
        with conn.cursor() as cur:
            # 1. Manual overrides take precedence
            cur.execute(
                "SELECT cusip, ticker, notes FROM mapping_overrides WHERE cusip = ANY(%s)",
                (cusips,),
            )
            for cusip, ticker, notes in cur.fetchall():
                out[cusip] = {
                    "ticker": ticker, "figi": None, "name": notes or "",
                    "exchange": "", "security_type": "", "confidence": "manual",
                }

            remaining = [c for c in cusips if c not in out]
            if remaining:
                cur.execute(
                    """SELECT cusip, ticker, figi, name, exchange, security_type, confidence
                       FROM cusip_ticker_map WHERE cusip = ANY(%s)""",
                    (remaining,),
                )
                for cusip, ticker, figi, name, exchange, sec_type, conf in cur.fetchall():
                    out[cusip] = {
                        "ticker": ticker, "figi": figi, "name": name or "",
                        "exchange": exchange or "", "security_type": sec_type or "",
                        "confidence": conf,
                    }

            to_query = [c for c in cusips if c not in out]

    # 3. Live OpenFIGI for the unresolved remainder, batched
    if to_query:
        for i in range(0, len(to_query), _BATCH_SIZE):
            batch = to_query[i:i + _BATCH_SIZE]
            try:
                results = _figi_batch_request(batch)
            except Exception as e:
                # Don't poison the whole backfill on transient FIGI failure;
                # leave these CUSIPs unresolved and the caller can retry later.
                print(f"  [figi] batch failed ({len(batch)} cusips): {e}")
                continue

            # results is parallel to batch
            new_rows: List[Tuple] = []
            for cusip, result in zip(batch, results):
                data = result.get("data") or []
                if data:
                    # Prefer US common stock entry if multiple FIGI hits
                    primary = None
                    for d in data:
                        if d.get("exchCode") == "US" or d.get("securityType2") == "Common Stock":
                            primary = d
                            break
                    if primary is None:
                        primary = data[0]
                    ticker = (primary.get("ticker") or "").strip().upper() or None
                    record = {
                        "ticker": ticker,
                        "figi": primary.get("figi"),
                        "name": primary.get("name") or "",
                        "exchange": primary.get("exchCode") or "",
                        "security_type": primary.get("securityType2") or primary.get("securityType") or "",
                        "confidence": "figi",
                    }
                else:
                    # No match — cache as unresolved to skip future retries
                    record = {
                        "ticker": None, "figi": None, "name": "",
                        "exchange": "", "security_type": "",
                        "confidence": "unresolved",
                    }
                out[cusip] = record
                new_rows.append((
                    cusip, record["ticker"], record["figi"], record["name"],
                    record["exchange"], record["security_type"], record["confidence"],
                ))

            # Persist new rows
            if new_rows:
                with get_conn() as conn:
                    with conn.cursor() as cur:
                        cur.executemany(
                            """INSERT INTO cusip_ticker_map
                               (cusip, ticker, figi, name, exchange, security_type, confidence)
                               VALUES (%s, %s, %s, %s, %s, %s, %s)
                               ON CONFLICT (cusip) DO UPDATE SET
                                 ticker = EXCLUDED.ticker,
                                 figi = EXCLUDED.figi,
                                 last_attempt_at = NOW(),
                                 attempt_count = cusip_ticker_map.attempt_count + 1""",
                            new_rows,
                        )
                    conn.commit()

    return out


def resolve_one(cusip: str) -> Optional[str]:
    """Convenience: resolve a single CUSIP, return ticker (or None)."""
    res = resolve_cusips([cusip])
    return res.get(cusip.strip().upper(), {}).get("ticker")
