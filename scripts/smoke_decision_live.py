"""Smoke decision routes.

Local mode checks market_data.layer candles without the network name celesys.ai.
Live mode curls the deployed decision engine after v4.63.113 is on the host.

    PYTHONPATH=. python3 scripts/smoke_decision_live.py --local
    python3 scripts/smoke_decision_live.py --live https://celesys.ai
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request

SYMBOLS = [
    ("MU", "US"),
    ("AAPL", "US"),
    ("NVDA", "US"),
    ("RELIANCE.NS", "IN"),
    ("KAYNES.NS", "IN"),
    ("TCS.NS", "IN"),
    ("NIFTY", "IN"),
]


def local() -> int:
    from market_data.yfcompat import history_frame
    failed = 0
    print("| symbol | source | bars | close | seconds |")
    print("| --- | --- | --- | --- | --- |")
    for symbol, region in SYMBOLS:
        started = time.perf_counter()
        frame = history_frame(symbol, period="1y", interval="1d", region=region)
        elapsed = time.perf_counter() - started
        bars = 0 if frame is None else len(frame)
        close = None
        if bars:
            close = float(frame["Close"].iloc[-1])
        source = getattr(frame, "attrs", {}).get("source")
        ok = bars >= 5 and close
        if not ok:
            failed += 1
        print(f"| {symbol} | {source} | {bars} | {close} | {elapsed:.2f} |")
    return failed


def live(base: str) -> int:
    failed = 0
    version = json.loads(_get(base + "/api/version").decode())
    print("version", version.get("version") or version.get("build_version") or version)
    print("| endpoint | symbol | status | detail | seconds |")
    print("| --- | --- | --- | --- | --- |")
    routes = ["/api/decision-engine", "/api/decision-360"]
    for route in routes:
        for symbol, region in SYMBOLS:
            query = urllib.parse.urlencode({"symbol": symbol, "region": region})
            started = time.perf_counter()
            status, body = _get_status(f"{base}{route}?{query}")
            elapsed = time.perf_counter() - started
            detail = ""
            ok = False
            try:
                payload = json.loads(body.decode())
                if payload.get("success") is False or payload.get("error"):
                    detail = str(payload.get("error") or "")[:80]
                else:
                    price = payload.get("spot") or payload.get("price") or (payload.get("trade") or {}).get("spot")
                    detail = f"ok price={price}" if price else "ok"
                    ok = True
            except Exception:
                detail = body[:80].decode("utf-8", "replace")
            if status != 200 or not ok:
                failed += 1
            print(f"| {route} | {symbol} | {status} | {detail} | {elapsed:.2f} |")
    return failed


def _get(url: str) -> bytes:
    status, body = _get_status(url)
    if status != 200:
        raise RuntimeError(f"{status} {url}")
    return body


def _get_status(url: str) -> tuple[int, bytes]:
    request = urllib.request.Request(url, headers={"User-Agent": "CelesysSmoke/4.63.113", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", default="")
    parser.add_argument("--local", action="store_true")
    args = parser.parse_args()
    if args.live:
        raise SystemExit(live(args.live.rstrip("/")))
    raise SystemExit(local())
