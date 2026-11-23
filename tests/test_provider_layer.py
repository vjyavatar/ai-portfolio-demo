"""Provider layer behavior that must hold without a live network."""
import time
import unittest
from datetime import datetime, timezone

from market_data import layer
from market_data.layer import Ticker, _empty


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

    def _bars(self, source):
        rows = []
        for day in range(1, 8):
            rows.append({"time": f"2026-11-{day:02d}", "open": 10, "high": 11, "low": 9, "close": 10 + day, "volume": 100})
        return {"ok": True, "data": rows, "source": source, "as_of": "2026-11-22T00:00:00+00:00", "stale": False, "metric_sources": {}}

    def test_us_chain_stops_when_finnhub_has_bars(self):
        layer._cache.clear()
        calls = []
        original = (layer._finnhub_bars, layer._nasdaq_bars, layer._tradingview_bars)
        def finnhub(symbol, interval="1d"):
            calls.append("finnhub")
            return self._bars("finnhub")
        def later(name):
            def inner(*args, **kwargs):
                calls.append(name)
                return self._bars(name)
            return inner
        layer._finnhub_bars = finnhub
        layer._nasdaq_bars = later("nasdaq")
        layer._tradingview_bars = later("tradingview")
        try:
            env = layer.candles("MU", region="US")
        finally:
            layer._finnhub_bars, layer._nasdaq_bars, layer._tradingview_bars = original
            layer._cache.clear()
        self.assertEqual(calls, ["finnhub"])
        self.assertEqual(env["source"], "finnhub")

    def test_us_chain_reaches_tradingview_after_finnhub_and_nasdaq_fail(self):
        layer._cache.clear()
        calls = []
        original = (layer._finnhub_bars, layer._nasdaq_bars, layer._tradingview_bars)
        def miss(name):
            def inner(*args, **kwargs):
                calls.append(name)
                return None
            return inner
        layer._finnhub_bars = miss("finnhub")
        layer._nasdaq_bars = miss("nasdaq")
        layer._tradingview_bars = lambda *args, **kwargs: calls.append("tradingview") or self._bars("tradingview")
        try:
            env = layer.candles("AAPL", region="US")
        finally:
            layer._finnhub_bars, layer._nasdaq_bars, layer._tradingview_bars = original
            layer._cache.clear()
        self.assertEqual(calls, ["finnhub", "nasdaq", "tradingview"])
        self.assertEqual(env["source"], "tradingview")

    def test_slow_finnhub_falls_through_near_five_seconds(self):
        layer._cache.clear()
        original = (layer._finnhub_bars, layer._nasdaq_bars, layer._tradingview_bars)
        def slow(symbol, interval="1d"):
            time.sleep(30)
            return None
        layer._finnhub_bars = slow
        layer._nasdaq_bars = lambda symbol: self._bars("nasdaq")
        layer._tradingview_bars = lambda *args, **kwargs: self._bars("tradingview")
        started = time.perf_counter()
        try:
            env = layer.candles("NVDA", region="US")
        finally:
            layer._finnhub_bars, layer._nasdaq_bars, layer._tradingview_bars = original
            layer._cache.clear()
        elapsed = time.perf_counter() - started
        self.assertEqual(env["source"], "nasdaq")
        self.assertGreater(elapsed, 4)
        self.assertLess(elapsed, 7)

    def test_india_chain_order_and_angel_proxy_session(self):
        layer._cache.clear()
        calls = []
        angel_calls = []
        original = (layer._angel_bars, layer._screener_bars, layer._tradingview_bars, layer._moneycontrol_index_bars)
        def miss(name):
            def inner(*args, **kwargs):
                calls.append(name)
                return None
            return inner
        layer._angel_bars = miss("angel")
        layer._screener_bars = miss("screener")
        layer._tradingview_bars = miss("tradingview")
        layer._moneycontrol_index_bars = lambda symbol: calls.append("nifty") or self._bars("moneycontrol")
        try:
            env = layer.candles("NIFTY", region="IN")
        finally:
            layer._angel_bars, layer._screener_bars, layer._tradingview_bars, layer._moneycontrol_index_bars = original
            layer._cache.clear()
        self.assertEqual(calls, ["angel", "screener", "tradingview", "nifty"])
        self.assertEqual(env["source"], "moneycontrol")

        import angel_options
        import angel_session
        def request_json(url, payload=None, headers=None, timeout=15):
            angel_calls.append((url, timeout))
            return {"data": [["2026-11-20T09:15:00+05:30", 100, 110, 90, 105, 1000]]}
        saved = (
            angel_options.configured, angel_options._nse_key, angel_options._load_nse_book,
            angel_options._headers, angel_session.request_json, getattr(angel_options, "_nse_book", None),
        )
        angel_options.configured = lambda: True
        angel_options._nse_key = lambda symbol: "RELIANCE"
        angel_options._nse_book = {"RELIANCE": {"token": "2885", "symbol": "RELIANCE-EQ"}}
        angel_options._load_nse_book = lambda now: angel_options._nse_book
        angel_options._headers = lambda: {"Authorization": "Bearer test"}
        angel_session.request_json = request_json
        try:
            bars = layer._angel_bars("RELIANCE.NS", "1d")
        finally:
            (
                angel_options.configured, angel_options._nse_key, angel_options._load_nse_book,
                angel_options._headers, angel_session.request_json, angel_options._nse_book,
            ) = saved
        self.assertEqual(bars["source"], "angel")
        self.assertEqual(angel_calls[0][0], layer._ANGEL_CANDLE)
        self.assertEqual(angel_calls[0][1], layer.ANGEL_CANDLE_TIMEOUT)

    def test_chain_retries_once_and_does_not_cache_a_miss(self):
        layer._cache.clear()
        calls = []
        original = (layer._finnhub_bars, layer._nasdaq_bars, layer._tradingview_bars)
        def miss(name):
            def inner(*args, **kwargs):
                calls.append(name)
                return None
            return inner
        def nasdaq(symbol):
            calls.append("nasdaq")
            if calls.count("nasdaq") >= 2:
                return self._bars("nasdaq")
            return None
        layer._finnhub_bars = miss("finnhub")
        layer._nasdaq_bars = nasdaq
        layer._tradingview_bars = miss("tradingview")
        try:
            env = layer.candles("MU", region="US")
            self.assertTrue(env["ok"])
            self.assertEqual(env["source"], "nasdaq")
            self.assertEqual(calls, ["finnhub", "nasdaq", "tradingview", "finnhub", "nasdaq"])
            calls.clear()
            cached = layer.candles("MU", region="US")
            self.assertEqual(calls, [])
            self.assertEqual(cached["source"], "nasdaq")
            layer._cache.clear()
            calls.clear()
            layer._nasdaq_bars = miss("nasdaq")
            missed = layer.candles("AAPL", region="US")
            self.assertFalse(missed["ok"])
            first = len(calls)
            self.assertEqual(first, 6)
            layer.candles("AAPL", region="US")
            self.assertEqual(len(calls), 12)
        finally:
            layer._finnhub_bars, layer._nasdaq_bars, layer._tradingview_bars = original
            layer._cache.clear()

    def test_cold_angel_book_does_not_block_screener(self):
        import angel_options
        saved_book = getattr(angel_options, "_nse_book", None)
        saved_load = angel_options._load_nse_book
        saved_configured = angel_options.configured
        angel_options._nse_book = None
        angel_options.configured = lambda: True
        angel_options._load_nse_book = lambda now: None
        started = time.perf_counter()
        try:
            bars = layer._angel_bars("RELIANCE.NS", "1d")
        finally:
            angel_options._nse_book = saved_book
            angel_options._load_nse_book = saved_load
            angel_options.configured = saved_configured
        self.assertIsNone(bars)
        self.assertLess(time.perf_counter() - started, 0.5)

    def test_quote_clock_rejects_a_june_snapshot(self):
        old = layer.quote_batch_clock({"NVDA": {"price": 100, "as_of": "2026-06-10T20:00:00+00:00"}})
        self.assertFalse(old["ok"])
        self.assertIn("2026-06-10", old["error"])
        self.assertEqual(old["as_of"], "2026-06-10")
        empty = layer.quote_batch_clock({})
        self.assertFalse(empty["ok"])
        self.assertIsNone(empty["as_of"])
        missing_clock = layer.quote_batch_clock({"NVDA": {"price": 100}})
        self.assertFalse(missing_clock["ok"])

    def test_quote_clock_accepts_a_recent_bar(self):
        moment = datetime.now(timezone.utc).isoformat()
        fresh = layer.quote_batch_clock({"NVDA": {"price": 125, "as_of": moment}})
        self.assertTrue(fresh["ok"])
        self.assertEqual(fresh["as_of"], moment[:10])
        self.assertTrue(layer.quote_date_ok(moment[:10]))
        self.assertFalse(layer.quote_date_ok("2026-06-08"))
        row = layer._quote_from_tv_fields("NVDA", {"change_abs": -1, "last_bar_update_time": 1795223700}, 125.53)
        self.assertEqual(row["as_of"][:10], "2026-11-21")

    def test_tradingview_packets_keep_bar_rows(self):
        body = '{"m":"series_loading","p":[]}'
        blob = f"~m~{len(body)}~m~{body}"
        self.assertEqual(layer._tv_packets(blob)[0]["m"], "series_loading")


if __name__ == "__main__":
    unittest.main()
