"""Bounded multi-symbol lookup for the legacy stock-price API.

The ASGI handler calls this in a background thread. Only one batch may run at
once, so a reconnect storm cannot create unbounded provider thread pools.
No prices are synthesized: only actual successful lookup results are returned.
"""
from concurrent.futures import ThreadPoolExecutor, wait
from threading import BoundedSemaphore, Thread

_BATCH_ADMISSION = BoundedSemaphore(1)


def run_bounded_batch(tickers, lookup, timeout_seconds=12.0, max_workers=4):
    """Return partial/empty data promptly; drain slow work before another batch."""
    names = list(tickers)[:30]
    if not names:
        return {"success": False, "status": "UNAVAILABLE", "error": "No symbols supplied",
                "prices": {}, "fetched": 0, "cached": 0, "failed": []}
    if not _BATCH_ADMISSION.acquire(blocking=False):
        return {"success": False, "status": "BUSY",
                "error": "Price scan is busy. Retry shortly; do not use a stale quote for a trade.",
                "prices": {}, "fetched": 0, "cached": 0, "failed": names[:10],
                "retry_after_seconds": 5}

    executor = None
    deferred_release = False
    try:
        worker_count = max(1, min(int(max_workers), 4, len(names)))
        executor = ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="price-batch")
        futures = {executor.submit(lookup, name): name for name in names}
        done, pending = wait(futures, timeout=max(0.01, float(timeout_seconds)))
        prices, failed = {}, []
        for future, expected in futures.items():
            if future not in done:
                failed.append(expected)
                continue
            try:
                symbol, snapshot = future.result()
                if symbol == expected and isinstance(snapshot, dict) and snapshot.get("price"):
                    prices[expected] = snapshot
                else:
                    failed.append(expected)
            except Exception:
                failed.append(expected)

        if pending:
            # Cancelling queue entries is not enough: active socket calls still
            # hold memory. Keep the admission gate until those threads exit.
            def _drain_and_release():
                try:
                    executor.shutdown(wait=True, cancel_futures=True)
                finally:
                    _BATCH_ADMISSION.release()

            Thread(target=_drain_and_release, name="price-batch-drain", daemon=True).start()
            deferred_release = True
        else:
            executor.shutdown(wait=True, cancel_futures=True)
            executor = None

        return {"success": True, "status": "PARTIAL" if pending else "OK",
                "prices": prices, "fetched": len(prices), "cached": 0,
                "failed": failed[:10], "quote_time_verified": False}
    finally:
        if not deferred_release:
            if executor is not None:
                executor.shutdown(wait=False, cancel_futures=True)
            _BATCH_ADMISSION.release()
