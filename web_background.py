"""Keep background scans from freezing the web event loop.

Spawned workers (the decision process) must not start these scans. A scan that
does run in the web process yields between tickers so the 12 second decision
timer can fire.
"""
from __future__ import annotations

import asyncio
import multiprocessing
import os
import time

YIELD_SEC = 0.05
_LAG_INTERVAL = 0.2
_lag = {"last_ms": 0.0, "max_ms": 0.0, "samples": 0, "interval_ms": int(_LAG_INTERVAL * 1000)}


def in_web_server() -> bool:
    """True only for the process that serves HTTP, not a spawned worker."""
    if os.getenv("CELESYS_DISABLE_BACKGROUND") == "1":
        return False
    return multiprocessing.parent_process() is None


def yield_worker() -> None:
    """Give the web event loop a turn between scan items."""
    time.sleep(YIELD_SEC)


async def monitor() -> None:
    """Record how late the event loop is, in milliseconds."""
    while True:
        started = time.perf_counter()
        await asyncio.sleep(_LAG_INTERVAL)
        lag_ms = max(0.0, (time.perf_counter() - started - _LAG_INTERVAL) * 1000)
        _lag["last_ms"] = round(lag_ms, 1)
        _lag["max_ms"] = round(max(float(_lag["max_ms"]), lag_ms), 1)
        _lag["samples"] = int(_lag["samples"]) + 1


def snapshot() -> dict:
    return dict(_lag)
