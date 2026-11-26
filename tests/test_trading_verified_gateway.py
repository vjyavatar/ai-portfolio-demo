import unittest
from datetime import datetime
from unittest.mock import patch

import angel_options as ao


class VerifiedGatewayTests(unittest.TestCase):
    def setUp(self):
        self.now = 1800000000
        self.book = {"NIFTY": {"token": "1", "symbol": "Nifty 50"},
                     "SENSEX": {"token": "2", "symbol": "SENSEX", "exchange": "BSE"}}

    def quote(self, exchange, tokens, mode):
        self.assertEqual(mode, "FULL")
        key = "NIFTY" if exchange == "NSE" else "SENSEX"
        inst = self.book[key]
        self.assertEqual(tokens, [inst["token"]])
        return [{"exchange": exchange, "symbolToken": inst["token"],
                 "tradingSymbol": inst["symbol"], "ltp": 100,
                 "exchFeedTime": datetime.fromtimestamp(self.now, ao.IST).strftime("%d-%b-%Y %H:%M:%S")}]

    def test_verified_exchange_routing(self):
        with patch.object(ao, "configured", return_value=True), patch.object(ao, "_load_nse_book", return_value=self.book), patch.object(ao, "_ltp_cache", {}), patch.object(ao.time, "time", return_value=self.now), patch.object(ao, "_quotes", side_effect=self.quote):
            rows = ao.nse_quotes(["NIFTY", "SENSEX"], verified=True)
            self.assertEqual(set(rows), {"NIFTY", "SENSEX"})
            self.assertEqual(rows["SENSEX"]["as_of_epoch"], self.now)
            self.assertEqual(rows["NIFTY"]["provider_mode"], "FULL")

    def test_missing_stale_and_wrong_identity_are_rejected(self):
        for change in ({"exchFeedTime": None}, {"exchFeedTime": "01-Jan-2020 09:30:00"}, {"tradingSymbol": "wrong"}):
            row = self.quote("NSE", ["1"], "FULL")[0]
            row.update(change)
            with self.subTest(change=change), patch.object(ao, "configured", return_value=True), patch.object(ao, "_load_nse_book", return_value=self.book), patch.object(ao, "_ltp_cache", {}), patch.object(ao.time, "time", return_value=self.now), patch.object(ao, "_quotes", return_value=[row]):
                self.assertEqual(ao.nse_quotes(["NIFTY"], verified=True), {})

    def test_legacy_cache_is_not_verified(self):
        with patch.object(ao, "configured", return_value=True), patch.object(ao, "_load_nse_book", return_value=self.book), patch.object(ao, "_ltp_cache", {"NIFTY": {"fetched_at": self.now, "price": 999}}), patch.object(ao.time, "time", return_value=self.now), patch.object(ao, "_quotes", side_effect=self.quote):
            self.assertEqual(ao.nse_quotes(["NIFTY"], verified=True)["NIFTY"]["price"], 100)


if __name__ == "__main__":
    unittest.main()
