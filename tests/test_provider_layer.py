"""Provider layer behavior that must hold without a live network."""
import time
import unittest
from datetime import datetime, timezone

from market_data import layer
from market_data.yfcompat import Ticker, _empty


class SafetyTests(unittest.TestCase):
    def test_history_is_never_none(self):
        layer._cache.clear()
        original = layer.candles
        layer.candles = lambda *args, **kwargs: {"ok": False, "data": None}
        try:
            frame = Ticker("MU").history(period="1y")
        finally:
            layer.candles = original
        self.assertIsNotNone(frame)
        self.assertEqual(len(frame), 0)
        self.assertTrue(frame.empty)

    def test_info_is_never_none(self):
        layer._cache.clear()
        original = layer.fundamentals
        layer.fundamentals = lambda *args, **kwargs: {"ok": False, "data": None}
        try:
            info = Ticker("KAYNES.NS").info
        finally:
            layer.fundamentals = original
        self.assertEqual(info, {})
        self.assertIsInstance(Ticker("AAPL").insider_transactions, type(_empty()))

    def test_stale_cache_is_labelled(self):
        layer._cache.clear()
        fresh = {"ok": True, "data": {"price": 10}, "source": "finnhub", "as_of": "2026-11-20T21:00:00+00:00", "stale": False, "metric_sources": {}}
        layer._cache_put("quote:US:MU", fresh)
        with layer._lock:
            layer._cache["quote:US:MU"]["stored_at"] = 0
        stale = layer._remember("quote:US:MU", 20, lambda: None)
        self.assertTrue(stale["stale"])
        self.assertEqual(stale["source"], "finnhub")
        self.assertEqual(stale["data"]["price"], 10)
        self.assertNotIn("Traceback", str(stale))

    def test_yahoo_hosts_are_blocked(self):
        with self.assertRaises(RuntimeError):
            layer._request("https://query1.finance.yahoo.com/v8/finance/chart/MU")

    def test_screener_ratio_parser(self):
        html = '''
        <li><span class="name"> Stock P/E </span><span class="number">73.6</span></li>
        <li><span class="name"> ROE </span><span class="number">9.07</span></li>
        '''
        ratios = layer._screener_ratios(html)
        self.assertEqual(ratios["Stock P/E"], 73.6)
        self.assertEqual(ratios["ROE"], 9.07)

    def test_nasdaq_rows_become_bars(self):
        bars = layer._bars_from_pairs([
            ("2026-11-19", "$352.91", "$355.28", "$346.47", "$349.21", "40,906,860"),
            ("2026-11-20", "$352.865", "$354.34", "$340.56", "$342.56", "80,692,550"),
        ], "nasdaq")
        self.assertEqual(len(bars["data"]), 2)
        self.assertEqual(bars["data"][-1]["close"], 342.56)
        self.assertEqual(bars["source"], "nasdaq")

    def test_slow_preferred_provider_does_not_hold_a_ready_fallback(self):
        layer._cache.clear()
        def slow():
            time.sleep(5)
            return {"ok": True, "data": [{"time": "2026-11-01", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}], "source": "finnhub", "as_of": "x", "stale": False}
        def fast():
            return {"ok": True, "data": [{"time": f"2026-11-{day:02d}", "open": 1, "high": 1, "low": 1, "close": 2, "volume": 1} for day in range(1, 8)], "source": "nasdaq", "as_of": "x", "stale": False}
        started = time.perf_counter()
        got = layer._race_bars([slow, fast], budget=6)
        elapsed = time.perf_counter() - started
        self.assertEqual(got["source"], "nasdaq")
        self.assertLess(elapsed, 3.0)
        self.assertGreaterEqual(len(got["data"]), 5)

    def test_finnhub_timeout_still_uses_the_next_candle_source(self):
        layer._cache.clear()
        original_finnhub = layer._finnhub_bars
        original_nasdaq = layer._nasdaq_bars
        def boom(symbol, interval="1d"):
            raise TimeoutError("finnhub timed out")
        def nasdaq(symbol):
            rows = []
            for day in range(1, 8):
                rows.append({"time": f"2026-11-{day:02d}", "open": 10, "high": 11, "low": 9, "close": 10 + day, "volume": 100})
            return {"ok": True, "data": rows, "source": "nasdaq", "as_of": "2026-11-22T00:00:00+00:00", "stale": False, "metric_sources": {}}
        layer._finnhub_bars = boom
        layer._nasdaq_bars = nasdaq
        try:
            env = layer.candles("MU", period="1y", interval="1d", region="US")
        finally:
            layer._finnhub_bars = original_finnhub
            layer._nasdaq_bars = original_nasdaq
            layer._cache.clear()
        self.assertTrue(env["ok"])
        self.assertEqual(env["source"], "nasdaq")
        self.assertGreaterEqual(len(env["data"]), 5)

    def test_region_routing(self):
        self.assertEqual(layer.classify("MU")["region"], "US")
        self.assertEqual(layer.classify("KAYNES.NS")["region"], "IN")
        self.assertEqual(layer.classify("NIFTY", "IN")["kind"], "index")
        self.assertEqual(layer.classify("RELIANCE", "IN")["tv"], ["NSE:RELIANCE"])

    def test_tradingview_margins_are_decimals(self):
        info, sources = {}, {}
        layer._apply_tv_fundamentals(info, sources, {
            "price": 594.51,
            "fields": {
                "change_abs": 1.2,
                "price_earnings_ttm": 8.01,
                "gross_margin": 80.71,
                "net_margin": 63.79,
                "return_on_equity": 88.25,
                "description": "Micron",
                "currency": "USD",
            },
        }, "2026-11-22T12:00:00+00:00")
        self.assertAlmostEqual(info["grossMargins"], 0.8071, places=4)
        self.assertAlmostEqual(info["profitMargins"], 0.6379, places=4)
        self.assertAlmostEqual(info["trailingPE"], 8.01, places=2)
        self.assertEqual(sources["grossMargins"]["source"], "tradingview")
        self.assertIn("as_of", sources["trailingPE"])


if __name__ == "__main__":
    unittest.main()
