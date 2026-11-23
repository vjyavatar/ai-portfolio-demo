"""Decide, Trading and Home must read the market-data layer, not Yahoo, Finviz or CNBC."""
import ast
from pathlib import Path
from unittest import mock
import unittest

from market_data import layer

ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / "api.py").read_text()

PHASE1 = {
    "decision_engine",
    "investor_decide",
    "_algo_signal_impl",
    "stock_intel",
    "_run_stock_intel",
    "global_ticker",
    "market_pulse",
    "_market_pulse_page",
    "_market_pulse_fetch",
    "movers",
    "_movers_compute_one_ticker",
    "_run_movers_scan",
}

FORBIDDEN = ("import yfinance", "yf.ticker", "finviz", "cnbc", "yahoo", "yfinance")


class PageSourceTests(unittest.TestCase):
    def test_decide_trading_and_home_do_not_call_yfinance_finviz_or_cnbc(self):
        tree = ast.parse(API)
        seen = set()
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in PHASE1:
                seen.add(node.name)
                text = ast.get_source_segment(API, node) or ""
                folded = text.lower()
                for token in FORBIDDEN:
                    self.assertNotIn(token, folded, f"{node.name} still contains {token}")
        self.assertEqual(seen, PHASE1)

    def test_one_source_list_per_region(self):
        self.assertEqual(layer.SOURCES["US"]["candle"][0], "tradingview")
        self.assertIn("sec", layer.SOURCES["US"]["fundamental"])
        self.assertEqual(layer.SOURCES["IN"]["fundamental"][0], "screener")
        self.assertIn("angel", layer.SOURCES["IN"]["price"])

    def test_screener_growth_comes_from_the_profit_and_loss_table(self):
        html = """
        <section id="profit-loss"><table>
        <tr><td>Sales +</td><td>100</td><td>110</td></tr>
        <tr><td>YoY Sales growth</td><td>+8%</td><td>+10%</td></tr>
        <tr><td>Net Profit +</td><td>20</td><td>25</td></tr>
        <tr><td>OPM %</td><td>18%</td><td>19%</td></tr>
        </table></section>
        <section id="balance-sheet"></section>
        """
        metrics = layer._screener_statement_metrics(html)
        self.assertEqual(metrics["revenueGrowth"], 10.0)
        self.assertEqual(metrics["earningsGrowth"], 25.0)
        self.assertEqual(metrics["operatingMargin"], 19.0)

    def test_a_bank_uses_nim_instead_of_gross_margin(self):
        html = """
        <section id="profit-loss"><table>
        <tr><td>Revenue +</td><td>90</td><td>100</td></tr>
        <tr><td>YoY Revenue growth</td><td>+9%</td><td>+12%</td></tr>
        <tr><td>Financing Margin %</td><td>3.4%</td><td>3.6%</td></tr>
        <tr><td>Net Profit +</td><td>10</td><td>11</td></tr>
        </table></section>
        <section id="balance-sheet"></section>
        """
        metrics = layer._screener_statement_metrics(html)
        self.assertTrue(metrics["financial"])
        self.assertEqual(metrics["nim"], 3.6)
        self.assertEqual(metrics["revenueGrowth"], 12.0)
        fake = {
            "ok": True,
            "source": "screener",
            "as_of": "2026-11-22",
            "data": {
                "longName": "HDFC Bank",
                "nim": 3.6,
                "financial": True,
                "returnOnEquity": 0.16,
                "returnOnAssets": 0.018,
                "revenueGrowth": 0.12,
                "earningsGrowth": 0.10,
                "trailingPE": 18.4,
                "debtToEquity": 0,
            },
        }
        with mock.patch.object(layer, "fundamentals", return_value=fake):
            row = layer.investor_fundamentals("HDFCBANK", "IN")
        self.assertTrue(row["ok"])
        self.assertTrue(row["financial"])
        self.assertEqual(row["quality"], 3.6)
        self.assertIsNone(row["grossMargin"])
        self.assertEqual(row["revenueGrowth"], 12.0)
        self.assertEqual(row["earningsGrowth"], 10.0)
        self.assertEqual(row["roe"], 16.0)
        self.assertEqual(row["pe"], 18.4)

    def test_these_pages_do_not_tell_the_user_to_retry_yahoo(self):
        for name in ("static/app.js", "static/app.min.js"):
            text = (ROOT / name).read_text()
            self.assertNotIn("Yahoo Finance sometimes fails to return metrics", text)

    def test_investor_decide_does_not_cache_an_insufficient_verdict(self):
        tree = ast.parse(API)
        node = next(item for item in tree.body if isinstance(item, ast.AsyncFunctionDef) and item.name == "investor_decide")
        text = ast.get_source_segment(API, node)
        self.assertIn("INSUFFICIENT", text)
        self.assertIn("investor_fundamentals", text)
        self.assertLess(text.index("INSUFFICIENT"), text.index("_smart_cache_set(_id_ck"))


if __name__ == "__main__":
    unittest.main()
