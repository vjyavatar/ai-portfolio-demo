"""Provider layer behavior that must hold without a live network."""
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
