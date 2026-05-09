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

# r63.71.2: Conservative batch sizes. OpenFIGI's documented limits are:
#   - With API key:    100 jobs/req, 25 req/6sec
#   - Without API key:   5 jobs/req, 25 req/min
# We use 50 (keyed) / 5 (unkeyed) for headroom against payload-size 413s
# that can hit even when count limits are respected. Adapts down on 413.
_INITIAL_BATCH_SIZE = 50 if OPENFIGI_API_KEY else 5
_MIN_BATCH_SIZE = 1
_RPS = 25 if OPENFIGI_API_KEY else 5

_rate_lock = threading.Lock()
_request_times: list = []

# r63.71.2: One-time mode log on first use
_mode_logged = False
_batch_size_lock = threading.Lock()
_current_batch_size = _INITIAL_BATCH_SIZE


def _log_mode_once():
    global _mode_logged
    if _mode_logged:
        return
    _mode_logged = True
    if OPENFIGI_API_KEY:
        masked = OPENFIGI_API_KEY[:4] + "..." + OPENFIGI_API_KEY[-2:] if len(OPENFIGI_API_KEY) > 8 else "(short)"
        print(f"[figi] AUTHENTICATED mode — key={masked}, batch={_INITIAL_BATCH_SIZE}, rps={_RPS}")
    else:
        print(f"[figi] UNAUTHENTICATED mode — no API key, batch={_INITIAL_BATCH_SIZE}, rps={_RPS}")
        print(f"[figi] WARNING: backfill will be ~20x slower without API key.")


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
    retry=retry_if_exception_type((httpx.TimeoutException,)),  # don't retry HTTP 4xx
    reraise=True,
)
def _figi_post(cusips: List[str]) -> List[dict]:
    """Single OpenFIGI POST. Caller handles 413 by splitting."""
    _wait_for_slot()
    payload = [{"idType": "ID_CUSIP", "idValue": c} for c in cusips]
    with httpx.Client(timeout=30.0) as client:
        r = client.post(OPENFIGI_URL, headers=_headers(), json=payload)
        r.raise_for_status()
        return r.json()


def _figi_batch_request(cusips: List[str]) -> List[dict]:
    """
    r63.71.2: Adaptive batch dispatch.

    Sends `cusips` as a single POST. On 413 (payload too large), splits in
    half and recurses. Permanently shrinks the global batch size hint on
    success so subsequent calls use the working size.

    Result list is parallel to input order.
    """
    global _current_batch_size
    _log_mode_once()
    if not cusips:
        return []
    try:
        result = _figi_post(cusips)
        # Success — record this batch size as known-good
        with _batch_size_lock:
            if len(cusips) > _current_batch_size:
                _current_batch_size = len(cusips)
        return result
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 413 and len(cusips) > _MIN_BATCH_SIZE:
            # Payload too large — split in half and retry
            new_size = max(_MIN_BATCH_SIZE, len(cusips) // 2)
            with _batch_size_lock:
                if new_size < _current_batch_size:
                    _current_batch_size = new_size
                    print(f"[figi] 413 received — adaptive batch size now {new_size}")
            mid = len(cusips) // 2
            left = _figi_batch_request(cusips[:mid])
            right = _figi_batch_request(cusips[mid:])
            return left + right
        # Other HTTP errors (401 invalid key, 429 rate limit, etc.) bubble up
        raise


def verify_credentials() -> dict:
    """
    r63.71.2: Single-CUSIP probe to verify OpenFIGI credentials before
    a long-running backfill. Uses Apple's CUSIP (037833100) as the
    test instrument — guaranteed to resolve to ticker AAPL.

    Returns:
        {"ok": True,  "ticker": "AAPL", "mode": "authenticated"|"unauthenticated"}
        {"ok": False, "reason": "..."}
    """
    test_cusip = "037833100"  # AAPL
    try:
        result = _figi_post([test_cusip])
    except httpx.HTTPStatusError as e:
        return {"ok": False, "reason": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:
        return {"ok": False, "reason": f"network/parse error: {e}"}

    if not result or not isinstance(result, list) or not result[0].get("data"):
        return {"ok": False, "reason": f"unexpected response shape: {str(result)[:200]}"}

    data0 = result[0]["data"][0] if result[0]["data"] else {}
    ticker = (data0.get("ticker") or "").upper().strip().split()[0] if data0 else ""
    if ticker != "AAPL":
        return {"ok": False, "reason": f"probe returned unexpected ticker {ticker!r}"}

    return {
        "ok": True,
        "ticker": ticker,
        "mode": "authenticated" if OPENFIGI_API_KEY else "unauthenticated",
    }


# r63.71.1: Schema-safe ticker cleaning. Handles:
#   - Whitespace ("AAPL ")
#   - Exchange-suffixed strings ("BRK/B US", "AAPL UN")
#   - Overlong tickers from foreign listings
#   - Non-string OpenFIGI return values
_TICKER_MAX_LEN = 20  # matches schema VARCHAR(20) post-migration 002


def _safe_ticker(raw) -> Optional[str]:
    """Normalize a raw ticker value to a DB-safe string or None."""
    if raw is None:
        return None
    try:
        t = str(raw).strip().upper()
    except Exception:
        return None
    if not t:
        return None
    # Take only the first whitespace-separated token — drops "AAPL UN" suffix
    t = t.split()[0]
    # Defensive truncation in case of pathological FIGI return
    if len(t) > _TICKER_MAX_LEN:
        t = t[:_TICKER_MAX_LEN]
    return t or None


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
                    "ticker": _safe_ticker(ticker), "figi": None, "name": notes or "",
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
                        "ticker": _safe_ticker(ticker), "figi": figi, "name": name or "",
                        "exchange": exchange or "", "security_type": sec_type or "",
                        "confidence": conf,
                    }

            to_query = [c for c in cusips if c not in out]

    # 3. Live OpenFIGI for the unresolved remainder, batched
    if to_query:
        with _batch_size_lock:
            cur_batch = _current_batch_size
        for i in range(0, len(to_query), cur_batch):
            batch = to_query[i:i + cur_batch]
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
                    ticker = _safe_ticker(primary.get("ticker"))  # r63.71.1
                    record = {
                        "ticker": ticker,
                        "figi": primary.get("figi"),
                        "name": (primary.get("name") or "")[:255],
                        "exchange": (primary.get("exchCode") or "")[:20],
                        "security_type": (primary.get("securityType2") or primary.get("securityType") or "")[:40],
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
