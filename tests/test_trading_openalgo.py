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
