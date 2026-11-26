import unittest
from unittest.mock import patch
from openalgo_site import inspect_market, config, call

class OpenAlgoPilotTests(unittest.TestCase):
    def test_broker_mapping_and_no_fabricated_live_status(self):
        now=1800000100
        with patch("openalgo_site.call", side_effect=[{"ltp": 100}, [{"timestamp":1799999700,"close":99},{"timestamp":1800000000,"close":101}]]) as request:
            data=inspect_market("SENSEX", ("https://example.test","test"),now)
        self.assertEqual(request.call_args_list[0].args[2]["exchange"],"BSE_INDEX")
        self.assertEqual(data["last_closed_bar"]["close"],99)
        self.assertFalse(data["live_verified"])
        self.assertEqual(data["decision"],"WAIT")
    def test_unconfigured_does_not_use_fallback(self):
        with patch.dict("os.environ",{"CELESYS_OPENALGO_URL":"","CELESYS_OPENALGO_API_KEY":""}):
            self.assertIsNone(config())
    def test_order_api_is_not_permitted(self):
        with self.assertRaises(ValueError):
            call(("https://example.test","test"),"placeorder",{})
    def test_invalid_data_fails_closed(self):
        with patch("openalgo_site.call",side_effect=[{"ltp":float("nan")}, [{"timestamp":1800000000,"close":-1}]]):
            data=inspect_market("NIFTY",("https://example.test","test"),1800000100)
        self.assertIsNone(data["quote"])
        self.assertIsNone(data["last_closed_bar"])
        self.assertFalse(data["execution_enabled"])

    def test_all_index_routes_use_expected_exchange(self):
        from openalgo_site import EXCHANGES
        for symbol, exchange in (("NIFTY","NSE_INDEX"),("BANKNIFTY","NSE_INDEX"),("SENSEX","BSE_INDEX")):
            with self.subTest(symbol=symbol), patch("openalgo_site.call",return_value=None) as request:
                result=inspect_market(symbol,("https://example.test","test"),1800000100)
                self.assertEqual(EXCHANGES[symbol],exchange)
                self.assertTrue(all(c.args[2]["exchange"]==exchange for c in request.call_args_list))
                self.assertEqual(result["decision"],"WAIT")
                self.assertFalse(result["live_verified"])

    def test_http_route_requires_authorized_access(self):
        from fastapi import FastAPI, HTTPException
        from fastapi.testclient import TestClient
        from openalgo_site import router
        app=FastAPI()
        app.include_router(router)
        with TestClient(app) as client, patch("secure_access.require_user",side_effect=HTTPException(401,"Sign in required")), patch("openalgo_site.call") as upstream:
            for path in ("/api/trading-next/status","/api/trading-next/research?symbol=NIFTY"):
                self.assertEqual(client.get(path).status_code,401)
            upstream.assert_not_called()

    def test_http_route_unconfigured_and_unsupported_symbol(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from openalgo_site import router
        app=FastAPI()
        app.include_router(router)
        with TestClient(app) as client, patch("secure_access.require_user",return_value={"full":True}), patch("openalgo_site.config",return_value=None), patch("openalgo_site.call") as upstream:
            self.assertFalse(client.get("/api/trading-next/status").json()["configured"])
            r=client.get("/api/trading-next/research?symbol=NIFTY")
            self.assertEqual(r.status_code,200)
            self.assertEqual(r.json()["status"],"OPENALGO_NOT_CONFIGURED")
            self.assertFalse(r.json()["live_verified"])
            self.assertEqual(client.get("/api/trading-next/research?symbol=SPY").status_code,422)
            self.assertIn("Trading Next",client.get("/trading-next/").text)
            upstream.assert_not_called()

    def test_quote_timeout_never_becomes_trade(self):
        import requests
        with patch("openalgo_site.call",side_effect=requests.Timeout()):
            data=inspect_market("NIFTY",("https://example.test","test"),1800000100)
        self.assertEqual(data["decision"],"WAIT")
        self.assertFalse(data["live_verified"])
        self.assertIsNone(data["quote"])
        self.assertIsNone(data["last_closed_bar"])
