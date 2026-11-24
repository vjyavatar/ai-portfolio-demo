"""Regression tests for bounded public live-market snapshots."""
import unittest
from unittest.mock import patch

from live_markets.cache import TTLCache


class BoundedLiveCacheTests(unittest.TestCase):
    def test_evicts_oldest_when_capacity_reached(self):
        cache = TTLCache(max_entries=3)
        for symbol in ("AAPL", "MSFT", "NVDA", "SPY"):
            cache.set(symbol, {"symbol": symbol})
        self.assertEqual(len(cache._items), 3)
        self.assertIsNone(cache.get_stale("AAPL", 1800))
        self.assertEqual(cache.get("SPY", 60)["symbol"], "SPY")

    def test_frequently_accessed_entry_survives_eviction(self):
        cache = TTLCache(max_entries=2)
        cache.set("NIFTY", {"price": 1})
        cache.set("SPY", {"price": 2})
        self.assertEqual(cache.get("NIFTY", 60)["price"], 1)
        cache.set("SENSEX", {"price": 3})
        self.assertIsNone(cache.get("SPY", 60))
        self.assertEqual(cache.get("NIFTY", 60)["price"], 1)

    def test_fresh_and_stale_windows_remain_distinct(self):
        cache = TTLCache(max_entries=2)
        with patch("live_markets.cache.time.monotonic", return_value=100.0):
            cache.set("SPY", {"source": "Finnhub"})
        with patch("live_markets.cache.time.monotonic", return_value=170.0):
            self.assertIsNone(cache.get("SPY", 60))
            self.assertEqual(cache.get_stale("SPY", 1800)["source"], "Finnhub")
        with patch("live_markets.cache.time.monotonic", return_value=1901.0):
            self.assertIsNone(cache.get_stale("SPY", 1800))
            self.assertNotIn("SPY", cache._items)

    def test_expired_entries_reclaimed_during_writes(self):
        cache = TTLCache(max_entries=3)
        with patch("live_markets.cache.time.monotonic", return_value=20.0):
            cache.set("old", object())
        with patch("live_markets.cache.time.monotonic", return_value=1900.0):
            cache.set("new", {"quality": "DELAYED"})
        self.assertEqual(list(cache._items), ["new"])

    def test_capacity_and_retention_must_be_positive(self):
        for arguments in ({"max_entries": 0}, {"retention_seconds": 0}):
            with self.assertRaises(ValueError):
                TTLCache(**arguments)


if __name__ == "__main__":
    unittest.main()
