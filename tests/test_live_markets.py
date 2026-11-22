"""Offline tests for the public market board. No network."""
import json
import unittest
from datetime import datetime, timezone

from live_markets import providers, service, sessions, symbols, verdict
from live_markets.options_chain import parse_nse_chain, parse_yahoo_chain


class SessionTests(unittest.TestCase):
    def test_india_open_us_closed(self):
        # Wednesday 18 Nov 2026 05:00 UTC = 10:30 IST, 00:00 ET.
        now = datetime(2026, 11, 18, 5, 0, tzinfo=timezone.utc)
        board = sessions.describe(now)
        self.assertEqual(board["exchanges"]["IN"]["session"], "OPEN")
        self.assertEqual(board["exchanges"]["US"]["session"], "CLOSED")
        self.assertIn("IST", board["clocks"]["ist"])
        self.assertIn("ET", board["clocks"]["et"])

    def test_us_open_india_closed(self):
        # 15:00 UTC = 10:00 ET, 20:30 IST.
        now = datetime(2026, 11, 18, 15, 0, tzinfo=timezone.utc)
        board = sessions.describe(now)
        self.assertEqual(board["exchanges"]["US"]["session"], "OPEN")
        self.assertEqual(board["exchanges"]["IN"]["session"], "CLOSED")

    def test_weekend_closed(self):
        now = datetime(2026, 11, 22, 15, 0, tzinfo=timezone.utc)
        board = sessions.describe(now)
        self.assertEqual(board["exchanges"]["US"]["session"], "CLOSED")
        self.assertEqual(board["exchanges"]["IN"]["session"], "CLOSED")


class SymbolTests(unittest.TestCase):
    def test_us_and_india_forms(self):
        self.assertEqual(symbols.resolve("AAPL")["tv"][0], "NASDAQ:AAPL")
        reliance = symbols.resolve("RELIANCE.NS")
        self.assertEqual(reliance["tv"], ["NSE:RELIANCE"])
        self.assertEqual(reliance["region_hint"], "IN")
        self.assertEqual(symbols.resolve("RELIANCE", "IN")["tv"][0], "NSE:RELIANCE")
        self.assertEqual(symbols.resolve("^NSEI")["tv"], ["NSE:NIFTY"])

    def test_rejects_blank(self):
        with self.assertRaises(ValueError):
            symbols.resolve("  ")


class ProviderParseTests(unittest.TestCase):
    def test_tradingview_delay_flag(self):
        payload = {"data": [{"s": "NASDAQ:AAPL", "d": [
            342.56, -1.9, -6.65, 1000, "Apple Inc.", "USD", "delayed_streaming_900",
            46.4, 341.8, 303.2, 360.8, 243.4, 38.1, -0.15, 900, -4.3, -2.1,
        ]}]}
        rows = providers.parse_tradingview(payload)
        row = rows["NASDAQ:AAPL"]
        self.assertEqual(row["quality"], "DELAYED")
        self.assertEqual(row["delay_seconds"], 900)
        self.assertEqual(row["price"], 342.56)
        self.assertAlmostEqual(row["features"]["pe"], 38.1)

    def test_streaming_is_live(self):
        self.assertEqual(providers.quality_from_mode("streaming"), ("LIVE", 0))

    def test_yahoo_chart_previous_close(self):
        payload = {"chart": {"result": [{
            "meta": {
                "regularMarketPrice": 1377.5,
                "currency": "INR",
                "shortName": "RELIANCE",
                "regularMarketTime": 1795168690,
                "regularMarketVolume": 100,
            },
            "indicators": {"quote": [{"close": [1370.0, 1377.5], "volume": [10, 100]}]},
        }]}}
        row = providers.parse_yahoo_chart(payload)
        self.assertEqual(row["price"], 1377.5)
        self.assertEqual(row["prev_close"], 1370.0)
        self.assertAlmostEqual(row["change"], 7.5)


class VerdictTests(unittest.TestCase):
    def test_score_uses_only_present_pillars(self):
        scored = verdict.score({
            "price": 100, "sma50": 90, "sma200": 80, "rsi": 52, "recommend": 0.2,
            "pe": 18, "perf_w": 2, "perf_1m": 4, "high_52w": 110, "volume": 100, "avg_volume": 90,
            "change_pct": 0.4,
        })
        self.assertIsNotNone(scored["score"])
        self.assertIn(scored["label"], {"Constructive", "Balanced", "Cautious", "Defensive"})
        self.assertGreater(scored["coverage"], 0.45)
        self.assertTrue(any("P/E" in reason for reason in scored["reasons"]))

    def test_missing_inputs_are_insufficient(self):
        scored = verdict.score({"price": 10})
        self.assertEqual(scored["label"], "Insufficient")
        self.assertIsNone(scored["score"])
        self.assertIn("Not financial advice", scored["disclaimer"])


class ChainParseTests(unittest.TestCase):
    def test_yahoo_chain_keeps_near_spot(self):
        calls = [{"contractSymbol": "C", "strike": strike, "bid": 1, "ask": 1.2, "lastPrice": 1.1,
                  "volume": 5, "openInterest": 9, "impliedVolatility": 0.2, "lastTradeDate": 1795208395}
                 for strike in (300, 340, 342.5, 400)]
        puts = [{"contractSymbol": "P", "strike": 342.5, "bid": 2, "ask": 2.2, "lastPrice": 2.1,
                 "volume": 3, "openInterest": 4, "impliedVolatility": 0.3}]
        payload = {"optionChain": {"result": [{
            "quote": {"regularMarketPrice": 342.56},
            "options": [{"expirationDate": 1795392000, "calls": calls, "puts": puts}],
        }]}}
        chain = parse_yahoo_chain(payload, strike_window=1)
        self.assertTrue(chain["available"])
        self.assertEqual(chain["quality"], "DELAYED")
        strikes = [row["strike"] for row in chain["rows"]]
        self.assertIn(342.5, strikes)
        self.assertNotIn(400, strikes)
        self.assertLessEqual(len(strikes), 3)

    def test_nse_chain_parser(self):
        payload = {"records": {
            "expiryDates": ["26-Nov-2026"],
            "underlyingValue": 25800,
            "timestamp": "20-Nov-2026 15:30:00",
            "data": [
                {"strikePrice": 25800, "expiryDate": "26-Nov-2026",
                 "CE": {"lastPrice": 120, "bidprice": 118, "askPrice": 122, "openInterest": 1000, "impliedVolatility": 12, "totalTradedVolume": 50},
                 "PE": {"lastPrice": 110, "bidprice": 108, "askPrice": 112, "openInterest": 900, "impliedVolatility": 13, "totalTradedVolume": 40}},
                {"strikePrice": 30000, "expiryDate": "26-Nov-2026",
                 "CE": {"lastPrice": 1, "bidprice": 1, "askPrice": 1.2, "openInterest": 1, "impliedVolatility": 20, "totalTradedVolume": 1},
                 "PE": {"lastPrice": 1, "bidprice": 1, "askPrice": 1.2, "openInterest": 1, "impliedVolatility": 20, "totalTradedVolume": 1}},
            ],
        }}
        chain = parse_nse_chain(payload, strike_window=0)
        self.assertTrue(chain["available"])
        self.assertEqual(chain["rows"][0]["strike"], 25800)
        self.assertEqual(chain["rows"][0]["call"]["bid"], 118)


class PresentationTests(unittest.TestCase):
    def test_closed_session_is_last_close(self):
        now = datetime(2026, 11, 22, 15, 0, tzinfo=timezone.utc)
        raw = {"tv_symbol": "NASDAQ:AAPL", "price": 100, "change": -1, "change_pct": -1,
               "volume": 10, "quality": "DELAYED", "delay_seconds": 900, "provider": "tradingview",
               "features": {}}
        shown = service._present(raw, {"token": "AAPL", "tv": ["NASDAQ:AAPL"]}, now)
        self.assertEqual(shown["quality"], "LAST_CLOSE")
        self.assertEqual(shown["session"], "CLOSED")
        self.assertEqual(shown["delay_seconds"], 900)
        self.assertEqual(shown["currency"], "USD")

    def test_india_currency(self):
        now = datetime(2026, 11, 18, 5, 0, tzinfo=timezone.utc)
        raw = {"tv_symbol": "NSE:RELIANCE", "price": 1377.5, "change": 1.9, "change_pct": 0.14,
               "volume": 100, "quality": "DELAYED", "delay_seconds": 900, "provider": "tradingview",
               "currency": "INR", "features": {}}
        shown = service._present(raw, {"token": "RELIANCE.NS", "tv": ["NSE:RELIANCE"]}, now)
        self.assertEqual(shown["region"], "IN")
        self.assertEqual(shown["session"], "OPEN")
        self.assertEqual(shown["quality"], "DELAYED")

    def test_fx_keeps_streaming_flag_when_equity_sessions_are_closed(self):
        now = datetime(2026, 11, 22, 15, 0, tzinfo=timezone.utc)
        raw = {"tv_symbol": "FX_IDC:USDINR", "price": 92.66, "change": -0.6, "change_pct": -0.66,
               "volume": 0, "quality": "LIVE", "delay_seconds": 0, "provider": "tradingview",
               "calendar": "continuous", "currency": "INR", "features": {}}
        shown = service._present(raw, {"token": "USD/INR", "tv": ["FX_IDC:USDINR"]}, now)
        self.assertEqual(shown["session"], "CONTINUOUS")
        self.assertEqual(shown["quality"], "LIVE")
        self.assertIsNone(shown["volume"])


class RouterTests(unittest.TestCase):
    def test_markets_page_and_quote_validation(self):
        from live_markets.router import live_health, live_quote, markets_page
        page = markets_page()
        body = page.body.decode()
        self.assertEqual(page.status_code, 200)
        self.assertIn("v4.63.104", body)
        self.assertIn("Not financial advice", body)
        bad = live_quote("<script>")
        self.assertFalse(bad["success"])
        health = live_health()
        self.assertTrue(health["ok"])
        self.assertIn("tradingview", json.dumps(health))


if __name__ == "__main__":
    unittest.main()
