import unittest
from copy import deepcopy
from trading_opportunities import rank_reports

NOW=1000000
def fixture(symbol="SPY",region="US",volume=2):
    return dict(symbol=symbol,region=region,source="Finnhub" if region=="US" else "Angel One",mode="RESEARCH_ONLY",
        market_status="OPEN",quote_time=NOW-5,bar_close_time=NOW-20,session_start=NOW-3600,session_end=NOW+3600,
        price=100,verdict="LONG_RESEARCH",stages=[dict(name=n,status="pass") for n in
            ("Data steward","Session guard","Trend analyst","Setup analyst","Risk critic","Quote guard","Research coordinator")],
        scenario=dict(kind="UNDERLYING_ONLY",entry=100,stop=98,target=104),metrics=dict(relative_volume=volume))
class OpportunityTests(unittest.TestCase):
    def test_rank_cap_and_order(self):
        symbols=["SPY","QQQ","AAPL","NVDA","MSFT","AMD"]
        result=rank_reports([fixture(s,volume=i+1) for i,s in enumerate(symbols)],"US",NOW,symbols)
        self.assertEqual([x["symbol"] for x in result["opportunities"]],symbols[::-1][:5])
        self.assertEqual(result["coverage"]["observed"],6)
        self.assertTrue(all(not x["option_entry_verified"] for x in result["opportunities"]))
    def test_reject_stale_closed_wrong_region_and_invalid_data(self):
        for change in [dict(stale_cache=True),dict(market_status="CLOSED"),dict(quote_time=NOW+1),
                       dict(bar_close_time=NOW-301),dict(region="IN"),dict(stages=[]),dict(source="market-data"),
                       dict(scenario=dict(kind="UNDERLYING_ONLY",entry=100,stop=104,target=98)),dict(verdict="WAIT")]:
            with self.subTest(change=change):
                self.assertEqual(rank_reports([dict(fixture(),**change)],"US",NOW,["SPY"])["opportunities"],[])
    def test_no_padding_and_region_isolation(self):
        result=rank_reports([fixture(),fixture("NIFTY","IN")],"IN",NOW,["NIFTY","SENSEX"])
        self.assertEqual([x["symbol"] for x in result["opportunities"]],["NIFTY"])
        self.assertEqual(result["coverage"],dict(universe_size=2,observed=1))
    def test_expiry_and_duplicates(self):
        first=fixture()
        second=deepcopy(first);second["quote_time"]=NOW-1
        result=rank_reports([first,second],"US",NOW,["SPY"])
        self.assertEqual(len(result["opportunities"]),1)
        self.assertEqual(result["opportunities"][0]["quote_time"],NOW-1)
        self.assertEqual(result["opportunities"][0]["expires_at"],NOW+280)
