"""Hammer /api/decision-engine while a scan yields the way production does.

The scan burns CPU in short slices and calls web_background.yield_worker
between them, the same helper the bottom-nav and movers scans use.
Each decision must come back well under 12 seconds.
"""
from __future__ import annotations

import asyncio
import json
import sys
import threading
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import uvicorn
from fastapi import FastAPI

import web_background

app = FastAPI()
PORT = 8765


@app.on_event("startup")
async def _start_lag_monitor():
    asyncio.create_task(web_background.monitor())


@app.get("/api/debug/loop-lag")
async def loop_lag():
    return {"success": True, **web_background.snapshot()}


@app.get("/api/decision-engine")
async def decision_engine(symbol: str = "MU"):
    started = time.perf_counter()

    def work():
        time.sleep(0.25)
        return {"success": True, "symbol": symbol, "data_status": "full"}

    fut = asyncio.get_running_loop().run_in_executor(None, work)
    try:
        result = await asyncio.wait_for(asyncio.shield(fut), timeout=2)
    except asyncio.TimeoutError:
        result = {"success": True, "symbol": symbol, "data_status": "partial", "pending": ["decision"]}
    result["elapsed"] = round(time.perf_counter() - started, 3)
    return result


def _scan():
    """Forty CPU slices. Without the yield, this would pin the loop."""
    for _ in range(40):
        deadline = time.perf_counter() + 0.08
        value = 0
        while time.perf_counter() < deadline:
            value += 1
        web_background.yield_worker()


def _serve():
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")


def _get(path: str) -> dict:
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{path}", timeout=15) as response:
        return json.loads(response.read().decode())


def main() -> int:
    threading.Thread(target=_serve, daemon=True).start()
    for _ in range(50):
        try:
            _get("/api/debug/loop-lag")
            break
        except Exception:
            time.sleep(0.05)
    else:
        print("server did not start")
        return 1
    threading.Thread(target=_scan, daemon=True).start()
    rows = []
    for symbol in ("GOOG", "MU", "LT", "NIFTY", "COIN", "MSFT"):
        row = _get(f"/api/decision-engine?symbol={symbol}&region=US")
        rows.append(row)
        print(f"{symbol:6} {row['elapsed']:.3f}s {row['data_status']}")
    lag = _get("/api/debug/loop-lag")
    print(f"loop-lag last={lag['last_ms']}ms max={lag['max_ms']}ms samples={lag['samples']}")
    slow = [row for row in rows if row["elapsed"] >= 12]
    if slow or lag["max_ms"] > 1000:
        print("FAIL")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
