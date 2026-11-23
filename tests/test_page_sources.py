"""Decide, Trading and Home must read the market-data layer, not Yahoo, Finviz or CNBC."""
import ast
from pathlib import Path
from unittest import mock
import unittest

from market_data import layer

ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / "api.py").read_text()

PHASE2 = {
    "market_context_v3",
    "investor_due_diligence",
    "batch_prices",
    "stock_quick",
    "top_picks",
    "screener",
    "heatmap",
    "smart_exit_v2",
    "momentum_leaders",
    "etf_scanner",
    "early_momentum_radar",
    "earnings_this_week",
    "cross_market_match",
    "decide_top_investments",
    "sector_intel",
    "l0_scan",
    "cds_batch",
    "etf_analyze",
    "dd_returns_snapshot",
    "catalyst_scan",
    "live_scan",
    "runway_screener",
    "runway_top",
    "imdf_decision",
    "imdf_themes",
    "multibagger_discovery",
    "red_flag_scan",
    "red_flag_screen",
    "high_prob_setups",
    "asset_intelligence",
    "institutional_terminal",
    "options_setup_detector",
    "market_daily",
    "regional_reports",
    "ema_signal",
    "gift_nifty",
    "us_premarket",
    "price_tick",
    "execution_score_v2",
    "trade_ticket",
    "fund_live",
    "structural_change_signal",
    "performance_leaderboard",
    "health_check",
    "options_flow",
    "validate_trades",
    "opportunity_runway",
    "market_why",
    "master_decision",
    "stock_news",
    "_capital_rotation_impl",
    "_macro_impact_impl",
    "_inst_conviction_impl",
    "_mgmt_change_impl",
    "_earnings_pred_impl",
    "_multibagger_prob_impl",
    "earnings_setup",
    "earnings_calendar",
    "microcap_hunter",
    "journal_list",
}

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
    "home_market_strip",
    "_movers_preview",
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

    def test_high_traffic_routes_read_the_layer(self):
        tree = ast.parse(API)
        seen = set()
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in PHASE2:
                seen.add(node.name)
                text = ast.get_source_segment(API, node) or ""
                folded = text.lower()
                for token in FORBIDDEN:
                    self.assertNotIn(token, folded, f"{node.name} still contains {token}")
        self.assertEqual(seen, PHASE2)

    def test_scan_screens_do_not_stamp_the_june_snapshot(self):
        tree = ast.parse(API)
        wanted = {"runway_top", "red_flag_screen", "multibagger_discovery"}
        for node in tree.body:
            if not isinstance(node, ast.AsyncFunctionDef) or node.name not in wanted:
                continue
            text = ast.get_source_segment(API, node) or ""
            self.assertNotIn("2026-06-08", text, node.name)
            self.assertNotIn("2026-06-10", text, node.name)
            self.assertIn("quote_batch_clock", text, node.name)
            wanted.remove(node.name)
        self.assertEqual(wanted, set())
        cards = {"imdf_decision", "imdf_themes", "red_flag_scan"}
        for node in tree.body:
            if not isinstance(node, ast.AsyncFunctionDef) or node.name not in cards:
                continue
            text = ast.get_source_segment(API, node) or ""
            self.assertNotIn("2026-06-10", text, node.name)
            self.assertNotIn("2026-06-08", text, node.name)
            self.assertIn("quote_batch_clock", text, node.name)
            cards.remove(node.name)
        self.assertEqual(cards, set())

    def test_aapl_is_us_and_hdfcbank_is_india_when_region_is_omitted(self):
        self.assertEqual(layer.classify("AAPL")["region"], "US")
        self.assertEqual(layer.classify("HDFCBANK")["region"], "IN")
        self.assertEqual(layer.classify("RELIANCE")["region"], "IN")
        self.assertEqual(layer.classify("AAPL", "IN")["region"], "IN")
        self.assertEqual(layer.classify("RELIANCE")["region"], "IN")
        conviction = next(item for item in ast.parse(API).body if isinstance(item, ast.AsyncFunctionDef) and item.name == "_inst_conviction_impl")
        body = ast.get_source_segment(API, conviction) or ""
        self.assertIn("classify(symbol)", body)
        self.assertIn("investor_fundamentals", body)
        route = next(item for item in ast.parse(API).body if isinstance(item, ast.AsyncFunctionDef) and item.name == "institutional_conviction")
        self.assertIn('region: str = ""', ast.get_source_segment(API, route) or "")

    def test_investor_decide_keeps_a_twelve_second_budget(self):
        tree = ast.parse(API)
        node = next(item for item in tree.body if isinstance(item, ast.AsyncFunctionDef) and item.name == "investor_decide")
        text = ast.get_source_segment(API, node)
        self.assertIn("timeout=7", text)
        self.assertIn("_investor_wall = 8.0", text)
        self.assertIn("_investor_wall = 4.8", text)
        self.assertIn("_warm_india_decisions", API)
        self.assertIn("_india_investor_snapshot", text)
        self.assertIn("_investor_on_budget", text)
        self.assertIn("Value: neutral 8/20", text)
        self.assertIn("profitCagr", text)
        self.assertIn("_intel_from_layer", (ROOT / "api.py").read_text())

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

    def test_screener_decide_pack_keeps_book_value_and_profit_history(self):
        html = """
        <div id="top-ratios">
          <span class="name">Book Value</span><span class="number">698</span>
          <span class="name">Dividend Yield</span><span class="number">0.40%</span>
        </div>
        <a title="Broad Sector">Energy</a>
        <section id="profit-loss"><table>
        <tr><td>Sales</td><td>100</td><td>110</td><td>140</td><td>180</td></tr>
        <tr><td>Net Profit</td><td>10</td><td>12</td><td>16</td><td>20</td></tr>
        <tr><td>OPM %</td><td>10%</td><td>11%</td><td>12%</td><td>13%</td></tr>
        </table></section>
        """
        pack = layer.screener_decide_from_html(html)
        self.assertEqual(pack["bookValue"], 698)
        self.assertEqual(pack["sector"], "Energy")
        self.assertEqual(len(pack["annualHistory"]), 4)
        self.assertGreater(pack["profitCagr"], 20)
        self.assertEqual(pack["annualHistory"][-1]["margin"], 13)

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

    def test_home_strip_asks_the_layer_for_six_tiles(self):
        def scan():
            return {
                label: {"price": 100.0, "change_pct": 40.0, "source": "tradingview"}
                for label, _symbol, _region in layer._HOME_STRIP
            }
        def bars(_symbol, _resolution, _count, _timeout):
            return [("t", 1, 1, 1, 90, 0), ("t", 1, 1, 1, 100, 0)]
        layer._cache.pop("home-strip", None)
        with mock.patch.object(layer, "_strip_scan", side_effect=scan), \
             mock.patch.object(layer, "_tv_symbol_bars", side_effect=bars), \
             mock.patch.object(layer, "quote", return_value={"ok": False}):
            payload = layer.home_strip()
        self.assertEqual(
            [row["name"] for row in payload["indices"]],
            ["NIFTY", "SENSEX", "S&P 500", "NASDAQ", "USD/INR", "GOLD"],
        )
        self.assertEqual(payload["nifty"], 100.0)
        self.assertEqual(payload["indices"][0]["change_pct"], round((100 - 90) / 90 * 100, 2))
        self.assertTrue(payload["indices"][0]["spark"])
        self.assertIsNone(layer._session_move(100, [], 21))

    def test_home_page_drops_the_repeated_blocks(self):
        html = (ROOT / "index.html").read_text()
        report = next(item for item in ast.parse(API).body if isinstance(item, ast.AsyncFunctionDef) and item.name == "generate_report")
        report_text = ast.get_source_segment(API, report)
        self.assertIn("_live_from_layer", report_text)
        self.assertIn("timeout=4.5", report_text)
        self.assertIn("9.0 -", report_text)
        self.assertNotIn("get_live_stock_data", report_text)
        self.assertNotIn('35, "sonnet"', report_text)
        self.assertIn("Unlock Decide", html)
        self.assertNotIn("Email, optional", html)
        self.assertIn('id="home-brief"', html)
        self.assertIn('id="home-movers"', html)
        self.assertIn('data-try="TCS"', html)
        self.assertNotIn("OUR RESEARCH STANDARD", html)
        self.assertIn('id="ws-start-cards" class="ws-start-grid" hidden', html)

    def test_investor_decide_does_not_cache_an_insufficient_verdict(self):
        tree = ast.parse(API)
        node = next(item for item in tree.body if isinstance(item, ast.AsyncFunctionDef) and item.name == "investor_decide")
        text = ast.get_source_segment(API, node)
        self.assertIn("INSUFFICIENT", text)
        self.assertIn("investor_fundamentals", text)
        self.assertLess(text.index("INSUFFICIENT"), text.index("_smart_cache_set(_id_ck"))


if __name__ == "__main__":
    unittest.main()
