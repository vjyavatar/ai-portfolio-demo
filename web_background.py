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
_LAG_WINDOW = 60.0
_lag = {"last_ms": 0.0, "samples": 0, "interval_ms": int(_LAG_INTERVAL * 1000)}
_recent: list[tuple[float, float]] = []
_deadline: float | None = None


def in_web_server() -> bool:
    """True only for the process that serves HTTP, not a spawned worker."""
    if os.getenv("CELESYS_DISABLE_BACKGROUND") == "1":
        return False
    return multiprocessing.parent_process() is None


def yield_worker() -> None:
    """Give the web event loop a turn between scan items."""
    time.sleep(YIELD_SEC)


def start_deadline(seconds: float) -> None:
    """Shared clock every NIFTY thread can see. The route and the chain both stop here."""
    global _deadline
    nxt = time.monotonic() + seconds
    if _deadline is None or nxt < _deadline:
        _deadline = nxt


def budget_hit() -> bool:
    return _deadline is not None and time.monotonic() >= _deadline


async def monitor() -> None:
    """Record how late the event loop is, in milliseconds. max_ms is the last minute."""
    while True:
        started = time.perf_counter()
        await asyncio.sleep(_LAG_INTERVAL)
        lag_ms = max(0.0, (time.perf_counter() - started - _LAG_INTERVAL) * 1000)
        _lag["last_ms"] = round(lag_ms, 1)
        _lag["samples"] = int(_lag["samples"]) + 1
        _recent.append((time.monotonic(), lag_ms))
        cutoff = time.monotonic() - _LAG_WINDOW
        while _recent and _recent[0][0] < cutoff:
            _recent.pop(0)


def snapshot() -> dict:
    cutoff = time.monotonic() - _LAG_WINDOW
    recent = [value for stamped, value in _recent if stamped >= cutoff]
    return {
        "last_ms": _lag["last_ms"],
        "max_ms": round(max(recent), 1) if recent else 0.0,
        "samples": _lag["samples"],
        "interval_ms": _lag["interval_ms"],
    }
