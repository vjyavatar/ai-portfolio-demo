"""Offline reliability checks; no network, orders, credentials, or synthetic live claims."""
from pathlib import Path
import threading
import time
import unittest

from market_batch import run_bounded_batch


class PriceBatchTests(unittest.TestCase):
    def test_successful_data_is_returned_without_fake_timestamp(self):
        names = ["SPY", "NIFTY", "QQQ"]
        result = run_bounded_batch(names, lambda name: (name, {"price": 50, "provider": "QA_FIXTURE"}))
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["fetched"], 3)
        self.assertEqual(set(result["prices"]), set(names))
        self.assertFalse(result["quote_time_verified"])
        self.assertNotIn("as_of", result)

    def test_provider_errors_do_not_invent_prices(self):
        def lookup(name):
            if name == "BAD":
                raise TimeoutError("fixture timeout")
            return name, None
        result = run_bounded_batch(["BAD", "EMPTY"], lookup)
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["fetched"], 0)
        self.assertEqual(set(result["failed"]), {"BAD", "EMPTY"})

    def test_concurrent_batches_do_not_spawn_more_pools(self):
        entered = threading.Event()
        unblock = threading.Event()
        done = []
        def slow(name):
            entered.set()
            unblock.wait(2)
            return name, {"price": 100}
        first = threading.Thread(target=lambda: done.append(run_bounded_batch(["A"], slow)), daemon=True)
        first.start()
        self.assertTrue(entered.wait(2))
        busy = run_bounded_batch(["B"], lambda name: (name, {"price": 99}))
        self.assertEqual(busy["status"], "BUSY")
        self.assertFalse(busy["success"])
        unblock.set()
        first.join(3)
        self.assertEqual(done[0]["status"], "OK")
        self.assertEqual(run_bounded_batch(["C"], lambda n: (n, {"price": 2}))["status"], "OK")

    def test_timeout_returns_partial_and_holds_gate_until_drain(self):
        block = threading.Event()
        def lookup(name):
            if name == "SLOW":
                block.wait(2)
            return name, {"price": 50}
        result = run_bounded_batch(["FAST", "SLOW"], lookup, timeout_seconds=0.05, max_workers=2)
        self.assertEqual(result["status"], "PARTIAL")
        self.assertIn("SLOW", result["failed"])
        self.assertEqual(run_bounded_batch(["SPY"], lookup)["status"], "BUSY")
        block.set()
        for _ in range(100):
            probe = run_bounded_batch(["SPY"], lambda n: (n, {"price": 100}))
            if probe["status"] == "OK":
                break
            time.sleep(0.01)
        self.assertEqual(probe["status"], "OK")

    def test_max_four_workers_even_when_thirty_symbols_supplied(self):
        guard = threading.Lock()
        live = peak = 0
        def lookup(name):
            nonlocal live, peak
            with guard:
                live += 1
                peak = max(peak, live)
            time.sleep(0.005)
            with guard:
                live -= 1
            return name, {"price": 5}
        names = [f"T{i}" for i in range(30)]
        result = run_bounded_batch(names, lookup, timeout_seconds=2, max_workers=99)
        self.assertEqual(result["fetched"], 30)
        self.assertLessEqual(peak, 4)


class ProductionSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = Path("api.py").read_text(encoding="utf-8")
        cls.start = Path("start.py").read_text(encoding="utf-8")

    def test_decision_processes_are_single_and_warming_is_opt_in(self):
        self.assertIn('ProcessPoolExecutor(max_workers=1, mp_context=ctx, initializer=_decision_child_init)', self.api)
        self.assertIn('os.getenv("CELESYS_WARM_DECISION", "0")', self.start)

    def test_noncore_preseed_and_india_warm_are_opt_in(self):
        for flag in ("CELESYS_DD_PRESEED", "CELESYS_DD_HYDRATE", "CELESYS_WARM_INDIA"):
            self.assertIn(f'os.getenv("{flag}", "0")', self.api)

    def test_price_batch_is_offloaded_not_blocking_asgi_loop(self):
        self.assertIn('await asyncio.to_thread(run_bounded_batch, tickers, _fetch_one)', self.api)

    def test_legacy_alphavantage_key_and_http_call_absent(self):
        self.assertNotIn("alphavantage.co/query?function=OVERVIEW", self.api)
        self.assertIn('from market_data.layer import', self.api)


if __name__ == "__main__":
    unittest.main()
