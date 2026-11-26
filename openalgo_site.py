"""Separate read-only pilot for a self-hosted OpenAlgo deployment.
No orders, no embedded credentials, no legacy provider fallback.
"""
import math
import os
import threading
import time
from datetime import datetime, timedelta
from html import escape
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import requests
from fastapi import APIRouter, HTTPException
from starlette.responses import HTMLResponse, JSONResponse

router = APIRouter()
EXCHANGES = {"NIFTY": "NSE_INDEX", "BANKNIFTY": "NSE_INDEX", "SENSEX": "BSE_INDEX"}
IST = ZoneInfo("Asia/Kolkata")
_lock = threading.Lock()
_cache = {}


def config():
    url = os.getenv("CELESYS_OPENALGO_URL", "").strip().rstrip("/")
    key = os.getenv("CELESYS_OPENALGO_API_KEY", "").strip()
    parts = urlsplit(url)
    if not key or parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment or parts.path:
        return None
    return url, key


def call(cfg, method, fields):
    if method not in ("quotes", "history"):
        raise ValueError("Read-only API only")
    base, key = cfg
    with requests.post(base + "/api/v1/" + method, json={"apikey": key, **fields},
                       timeout=(3, 12), allow_redirects=False, stream=True) as response:
        if response.status_code != 200:
            raise ValueError("Upstream HTTP " + str(response.status_code))
        raw = bytearray()
        for chunk in response.iter_content(16384):
            raw.extend(chunk)
            if len(raw) > 1000000:
                raise ValueError("Response too large")
    import json
    payload = json.loads(raw)
    if not isinstance(payload, dict) or payload.get("status") != "success":
        raise ValueError("Upstream rejected request")
    return payload.get("data")


def num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None


def inspect_market(symbol, cfg, now):
    exchange = EXCHANGES[symbol]
    local = datetime.fromtimestamp(now, IST)
    result = dict(symbol=symbol, exchange=exchange, source="OpenAlgo", execution_enabled=False,
                  quote=None, last_closed_bar=None, closed_bars=0, quote_status="UNAVAILABLE",
                  history_status="UNAVAILABLE", decision="WAIT", live_verified=False)
    try:
        quote = call(cfg, "quotes", dict(symbol=symbol, exchange=exchange))
        price = num(quote.get("ltp")) if isinstance(quote, dict) else None
        if price and price > 0:
            result.update(quote=price, quote_status="SNAPSHOT_TIMESTAMP_UNVERIFIED")
    except (ValueError, requests.RequestException):
        pass
    try:
        history = call(cfg, "history", dict(symbol=symbol, exchange=exchange, interval="5m",
                       start_date=(local.date()-timedelta(days=7)).isoformat(), end_date=local.date().isoformat()))
        if isinstance(history, list):
            bars = []
            for row in history:
                if not isinstance(row, dict):
                    continue
                stamp, close = num(row.get("timestamp")), num(row.get("close"))
                if stamp and close and close > 0 and stamp % 300 == 0 and stamp + 300 <= now:
                    bars.append((stamp, close))
            bars = sorted(set(bars))
            if bars:
                stamp, close = bars[-1]
                result.update(last_closed_bar=dict(time=stamp+300, close=close), closed_bars=len(bars),
                              history_status="HISTORICAL_CANDLES_RECEIVED")
    except (ValueError, requests.RequestException):
        pass
    return result


@router.get("/api/trading-next/status")
def status():
    from secure_access import require_user
    require_user()
    return dict(configured=bool(config()), source="OpenAlgo", execution_enabled=False)


@router.get("/api/trading-next/research")
def research(symbol: str = "NIFTY"):
    from secure_access import require_user
    require_user()
    if symbol not in EXCHANGES:
        raise HTTPException(422, "Unsupported index")
    cfg = config()
    if not cfg:
        return JSONResponse({"symbol": symbol, "decision": "WAIT", "status": "OPENALGO_NOT_CONFIGURED",
                             "live_verified": False, "execution_enabled": False}, headers={"Cache-Control": "no-store"})
    if not _lock.acquire(blocking=False):
        raise HTTPException(429, "OpenAlgo request in progress")
    try:
        now = time.time()
        hit = _cache.get(symbol)
        if hit and 0 <= now-hit[0] < 60:
            data = hit[1]
        else:
            data = inspect_market(symbol, cfg, now)
            _cache[symbol] = (now, data)
        return JSONResponse(data, headers={"Cache-Control": "no-store"})
    finally:
        _lock.release()


@router.get("/trading-next/", response_class=HTMLResponse)
def page():
    return HTMLResponse("""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Celesys Trading Next</title><style>
body{font:16px system-ui,sans-serif;background:#f4f6f8;color:#172331;margin:0}
main{max-width:850px;margin:48px auto;padding:24px}section{background:white;border:1px solid #d7dfe7;border-radius:12px;padding:24px;margin:18px 0}
h1{font-size:32px;margin:0}a{color:#136347}li{margin:12px 0}p{line-height:1.5}
</style></head><body><main><h1>Trading Next</h1>
<p>Independent OpenAlgo connection pilot · India · Read-only</p>
<section><h2>Broker connection checks</h2><p>Authorized Celesys sign-in is required. These endpoints verify real responses from your configured OpenAlgo instance. No simulated prices or orders.</p>
<ul><li><a href="/api/trading-next/status">Connection configuration</a></li>
<li><a href="/api/trading-next/research?symbol=NIFTY">NIFTY quote and candles</a></li>
<li><a href="/api/trading-next/research?symbol=BANKNIFTY">BANKNIFTY quote and candles</a></li>
<li><a href="/api/trading-next/research?symbol=SENSEX">SENSEX quote and candles</a></li></ul></section>
<section><h2>Release gate</h2><p>Live signal generation remains disabled until source timestamps, option contracts and risk controls are verified. This pilot does not replace the existing desk yet.</p></section>
</main></body></html>""", headers={"Cache-Control": "no-store"})
