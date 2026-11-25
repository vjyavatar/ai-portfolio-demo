import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from trading_source_clock import normalize
from trading_research import analyze_chart

def local(y,m,d,h,minute,region="US"):
    return datetime(y,m,d,h,minute,tzinfo=ZoneInfo("America/New_York" if region=="US" else "Asia/Kolkata")).timestamp()
def fixture(region="US",count=3):
    symbol="SPY" if region=="US" else "^NSEI"
    start=local(2026,11,25,9,30 if region=="US" else 15,region)
    now=start+count*300+120
    times=[start-86400,start-86100]+[start+i*300 for i in range(count)]
    q={k:[100.0]*len(times) for k in ("open","high","low","close")}
    q["volume"]=[1000]*len(times)
    return {"chart":{"result":[{"meta":{"symbol":symbol,"currency":"USD" if region=="US" else "INR","dataGranularity":"5m","providerQuotePrice":101.0,"exchangeQuoteTime":now-1,"quoteSource":"finnhub" if region=="US" else "angel","candleSource":"tradingview","regularMarketTime":now,"currentTradingPeriod":{"regular":{"start":times[0],"end":times[-1]+300}}},"timestamp":times,"indicators":{"quote":[q]}}]}},now

class SourceClockTests(unittest.TestCase):
    def test_opening_session_not_last_bar(self):
        p,n=fixture();r=analyze_chart(normalize(p,"US",n),"SPY","US",n)
        self.assertEqual(r["market_status"],"OPEN")
        self.assertEqual(r["session_start"],local(2026,11,25,9,30))
        self.assertEqual(r["session_end"],local(2026,11,25,16,0))
        self.assertEqual(len(r["bars"]),3)
        self.assertEqual(r["quote_time"],n-1)
        self.assertEqual(r["price"],101.0)
        self.assertTrue(r["warming_up"])
        self.assertEqual(r["verdict"],"WAIT")
    def test_missing_exchange_time_does_not_use_retrieval(self):
        p,n=fixture();p["chart"]["result"][0]["meta"]["exchangeQuoteTime"]=None
        r=analyze_chart(normalize(p,"US",n),"SPY","US",n)
        self.assertIsNone(r["quote_time"]);self.assertEqual(r["price"],101.0)
        self.assertEqual(r["price_kind"],"UNVERIFIED_QUOTE_SNAPSHOT")
        self.assertFalse(r["paper_eligible"])
    def test_closed_bar_fallback_not_a_quote(self):
        p,n=fixture();m=p["chart"]["result"][0]["meta"];m["providerQuotePrice"]=None
        r=analyze_chart(normalize(p,"US",n),"SPY","US",n)
        self.assertEqual(r["price_kind"],"LAST_CLOSED_BAR")
        self.assertEqual(r["price"],100.0);self.assertIsNone(r["quote_time"])
        self.assertEqual(r["price_as_of"],local(2026,11,25,9,45))
        self.assertEqual(r["verdict"],"WAIT")
    def test_stale_candle_cannot_trade(self):
        p,n=fixture(count=25);p["chart"]["result"][0]["meta"]["candleStale"]=True
        r=analyze_chart(normalize(p,"US",n),"SPY","US",n)
        self.assertEqual(r["quote_time"],n-1);self.assertTrue(r["candle_stale"])
        self.assertEqual(r["verdict"],"WAIT")
    def test_india_regular_clock(self):
        p,n=fixture("IN");r=analyze_chart(normalize(p,"IN",n),"NIFTY","IN",n)
        self.assertEqual(r["session_start"],local(2026,11,25,9,15,"IN"))
        self.assertEqual(r["session_end"],local(2026,11,25,15,30,"IN"))
        self.assertEqual(r["market_status"],"OPEN")
        self.assertTrue(r["warming_up"])
    def test_future_quote_blocked(self):
        p,n=fixture();p["chart"]["result"][0]["meta"]["exchangeQuoteTime"]=n+5
        r=analyze_chart(normalize(p,"US",n),"SPY","US",n)
        self.assertIsNone(r["quote_time"]);self.assertFalse(r["paper_eligible"])
    def test_weekend_and_stale_quote_blocked(self):
        p,n=fixture();n=local(2026,11,28,10,0)
        r=analyze_chart(normalize(p,"US",n),"SPY","US",n)
        self.assertNotEqual(r["market_status"],"OPEN")
        self.assertEqual(r["verdict"],"WAIT")
