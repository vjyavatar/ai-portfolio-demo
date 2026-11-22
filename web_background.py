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
_lag = {"last_ms": 0.0, "samples": 0, "interval_ms": int(_LAG_INTERVAL * 1000), "stack": ""}
_recent: list[tuple[float, float]] = []
_deadline: float | None = None
_heartbeat = time.monotonic()
_last_dump_at = 0.0
_watchdog_started = False


def in_web_server() -> bool:
    """True only for the process that serves HTTP, not a spawned worker."""
    if os.getenv("CELESYS_DISABLE_BACKGROUND") == "1":
        return False
    return multiprocessing.parent_process() is None


def yield_worker() -> None:
    """Give the web event loop a turn between scan items."""
    time.sleep(YIELD_SEC)


def start_deadline(seconds: float) -> None:
    """This job's clock. A new request replaces the previous one.

    The old clock only moved earlier, so after the first 12 seconds every
    later symbol looked late and came back partial.
    """
    global _deadline
    _deadline = time.monotonic() + seconds


def clear_budget() -> None:
    global _deadline
    _deadline = None


def expire_budget() -> None:
    """The clock is over. A job that is still running has to stop."""
    global _deadline
    _deadline = time.monotonic() - 1


def budget_hit() -> bool:
    return _deadline is not None and time.monotonic() >= _deadline


def _dump_stacks() -> str:
    """Every parent thread, captured while the loop is still late."""
    import sys
    import traceback
    chunks = []
    for ident, frame in sys._current_frames().items():
        chunks.append(f"\n--- thread {ident} ---\n")
        chunks.append("".join(traceback.format_stack(frame)))
    text = "".join(chunks)
    return text[-12000:]


def _watchdog() -> None:
    """A thread, not a loop task. A stuck loop cannot report on itself."""
    global _last_dump_at
    while True:
        time.sleep(0.5)
        stalled = time.monotonic() - _heartbeat
        if stalled < 2 or time.monotonic() - _last_dump_at < 15:
            continue
        _last_dump_at = time.monotonic()
        text = _dump_stacks()
        _lag["stack"] = text
        print(f"LOOP BLOCK {stalled:.1f}s\n{text}", flush=True)


def start_watchdog() -> None:
    global _watchdog_started
    if _watchdog_started or not in_web_server():
        return
    _watchdog_started = True
    import threading
    threading.Thread(target=_watchdog, name="loop-watchdog", daemon=True).start()


async def monitor() -> None:
    """Record how late the event loop is, in milliseconds. max_ms is the last minute."""
    global _heartbeat
    start_watchdog()
    while True:
        _heartbeat = time.monotonic()
        started = time.perf_counter()
        await asyncio.sleep(_LAG_INTERVAL)
        _heartbeat = time.monotonic()
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
        "stack": _lag.get("stack") or "",
    }
