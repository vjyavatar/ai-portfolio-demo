"""Offline route smoke tests for the non-mutating Celesys web surfaces."""
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from discovery_site import attach_discovery
from live_markets.router import attach_live_markets
from trading_site import attach_trading_desk
import trading_site


class WebsiteRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        attach_trading_desk(app)
        attach_live_markets(app)
        attach_discovery(app)
        cls.client = TestClient(app)

    def test_every_public_document_page_returns_html(self):
        pages = [
            "/trading/", "/markets", "/learn", "/methodology",
            "/options/india", "/options/us", "/agents",
        ]
        for path in pages:
            with self.subTest(path=path):
                response = self.client.get(path, follow_redirects=True)
                self.assertEqual(response.status_code, 200)
                self.assertIn("text/html", response.headers.get("content-type", ""))
                self.assertGreater(len(response.content), 100)

    def test_trading_desk_has_read_only_status(self):
        response = self.client.get("/api/trading-desk/status")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), dict)

    def test_trading_invalid_symbol_is_rejected(self):
        response = self.client.get("/api/trading-desk/research", params={"symbol": "!", "region": "US"})
        self.assertEqual(response.status_code, 422)

    def test_provider_outage_stays_an_unavailable_research_response(self):
        trading_site._cache.clear()
        trading_site._failures.clear()
        trading_site._provider_state.update(code="READY", retry_after=0, failures=0)
        with patch("trading_site.open_chart", side_effect=TimeoutError("QA forced provider timeout")):
            response = self.client.get("/api/trading-desk/research", params={"symbol": "QQQ", "region": "US"})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIsInstance(body, dict)
        self.assertNotEqual(body.get("verdict"), "TRADE ALLOWED")
        self.assertFalse(body.get("paper_eligible", False))
        trading_site._failures.clear()
        trading_site._provider_state.update(code="READY", retry_after=0, failures=0)

    def test_legacy_api_contains_decide_and_market_pulse_routes(self):
        from pathlib import Path
        source = Path("api.py").read_text(encoding="utf-8")
        for route in ('/api/decision-engine', '/api/investor-decide', '/api/market-pulse', '/api/batch-prices'):
            with self.subTest(route=route):
                self.assertIn(route, source)


if __name__ == "__main__":
    unittest.main()
