import unittest
from datetime import datetime,timezone
from unittest.mock import patch
from trading_opportunity_scan import RegionalScanner,regular_window,UNIVERSE
from trading_opportunities import rank_reports

def ts(value):return datetime.fromisoformat(value).timestamp()
NOW=ts("2026-11-25T15:30:00+00:00")
def fixture(symbol):
    return dict(symbol=symbol,region="US",source="Finnhub",mode="RESEARCH_ONLY",market_status="OPEN",
        quote_time=NOW-1,bar_close_time=NOW-30,session_start=NOW-3600,session_end=NOW+3600,
        price=100,verdict="LONG_RESEARCH",stages=[dict(name=n,status="pass") for n in
            ("Data steward","Session guard","Trend analyst","Setup analyst","Risk critic","Quote guard","Research coordinator")],
        scenario=dict(kind="UNDERLYING_ONLY",entry=100,stop=98,target=104),metrics=dict(relative_volume=2))
class RegionalScannerTests(unittest.TestCase):
    def test_clock_windows(self):
        self.assertTrue(regular_window("US",NOW))
        self.assertFalse(regular_window("IN",NOW))
        self.assertTrue(regular_window("IN",ts("2026-11-25T04:00:00+00:00")))
        self.assertFalse(regular_window("US",ts("2026-11-28T15:30:00+00:00")))
    def test_cycle_and_expired_shortlist(self):
        clock=[NOW]
        scanner=RegionalScanner(lambda s,r:fixture(s),lambda:{},clock=lambda:clock[0])
        scanner.enabled=True
        with patch.object(scanner.stop,"wait",return_value=False):
            scanner.cycle("US")
        result=scanner.snapshot("US")
        self.assertEqual(len(result["opportunities"]),5)
        self.assertEqual(result["coverage"]["attempted"],len(UNIVERSE["US"]))
        clock[0]+=301
        result=scanner.snapshot("US")
        self.assertEqual(result["opportunities"],[])
        self.assertEqual(len(result["last_shortlist"]),5)
        self.assertNotIn("price",result["last_shortlist"][0])
    def test_provider_cooldown_respected(self):
        scanner=RegionalScanner(lambda *a:self.fail("Network must not be called"),lambda:{"retry_after":NOW+900},clock=lambda:NOW)
        scanner.enabled=True
        scanner.cycle("US")
        result=scanner.snapshot("US")
        self.assertEqual(result["coverage"]["attempted"],0)
        self.assertTrue(result["partial_coverage"])
    def test_disabled_scanner(self):
        scanner=RegionalScanner(lambda *a:self.fail("Network must not be called"),lambda:{},clock=lambda:NOW)
        with patch.dict("os.environ",{"CELESYS_REGIONAL_SCAN":"0"}):scanner.start()
        self.assertEqual(scanner.snapshot("US")["status"],"SCANNER_DISABLED")
        self.assertIsNone(scanner.thread)
