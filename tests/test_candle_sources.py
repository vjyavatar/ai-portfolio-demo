"""US candle order and the loop watchdog."""
import ast
from pathlib import Path
import unittest

import web_background
from market_data import layer


class CandleSourceTests(unittest.TestCase):
    def test_us_equity_tries_tradingview_before_the_sources_that_miss(self):
        names = [name for name, _step in layer._candle_steps("AMD", layer.classify("AMD", "US"), "1d")]
        self.assertEqual(names[0], "tradingview")
        self.assertIn("nasdaq", names)
        self.assertIn("stooq", names)
        self.assertLess(names.index("tradingview"), names.index("finnhub"))

    def test_a_failed_candle_load_is_not_cached(self):
        key = "candles:US:TESTMISS:1d"
        layer._cache.pop(key, None)
        env = layer._remember(key, 60, lambda: {"ok": False, "data": None})
        self.assertFalse(env.get("ok"))
        self.assertIsNone(layer._cache_get(key, 60))

    def test_watchdog_is_a_thread_and_the_lag_endpoint_keeps_the_stack(self):
        self.assertTrue(callable(web_background.start_watchdog))
        self.assertIn("stack", web_background.snapshot())
        source = Path("api.py").read_text()
        tree = ast.parse(source)
        route = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "market_pulse")
        text = ast.get_source_segment(source, route)
        self.assertIn("pulse-page", text)
        self.assertNotIn("timeout=12", text)
        ticker = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "global_ticker")
        ticker_text = ast.get_source_segment(source, ticker)
        self.assertIn("asyncio.to_thread(_index_rows)", ticker_text)
        self.assertNotIn("live_results = index_rows()", ticker_text)
        algo = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "algo_signal_safe")
        algo_text = ast.get_source_segment(source, algo)
        self.assertIn('guarded.get("success")', algo_text)
