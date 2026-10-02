import unittest
from trading_research import analyze_chart

def fixture():
    start=1790947800
    prices=[100+i*.02 for i in range(24)]+[100.75]
    stamps=[start+i*300 for i in range(25)]
    q={'open':[v-.02 for v in prices],'high':[v+.14 for v in prices],'low':[v-.17 for v in prices],'close':prices,'volume':[1000]*24+[1800]}
    now=stamps[-1]+301
    return {'chart':{'result':[{'meta':{'regularMarketPrice':prices[-1],'regularMarketTime':now-1,'instrumentType':'ETF','currentTradingPeriod':{'regular':{'start':start,'end':start+23400}}},'timestamp':stamps,'indicators':{'quote':[q]}}]}},now
class ResearchTests(unittest.TestCase):
    def test_fresh_signal_not_probability(self):
        p,n=fixture();r=analyze_chart(p,'SPY','US',n)
        self.assertEqual(r['verdict'],'LONG_RESEARCH');self.assertTrue(r['paper_eligible'])
        self.assertNotIn('confidence',r)
        self.assertEqual(r['metrics']['relative_volume'],1.8)
    def test_raw_index_is_never_paper_stock(self):
        p,n=fixture();p['chart']['result'][0]['meta']['instrumentType']='INDEX'
        r=analyze_chart(p,'SPX','US',n);self.assertEqual(r['verdict'],'LONG_RESEARCH');self.assertFalse(r['paper_eligible'])
    def test_stale_quote_blocks(self):
        p,n=fixture();p['chart']['result'][0]['meta']['regularMarketTime']=n-301
        r=analyze_chart(p,'SPY','US',n);self.assertEqual(r['verdict'],'WAIT');self.assertFalse(r['paper_eligible'])
    def test_missing_timestamp_blocks(self):
        p,n=fixture();del p['chart']['result'][0]['meta']['regularMarketTime']
        self.assertFalse(analyze_chart(p,'SPY','US',n)['paper_eligible'])
    def test_closed_market_blocks(self):
        p,n=fixture();p['chart']['result'][0]['meta']['currentTradingPeriod']['regular']['end']=n-1
        self.assertEqual(analyze_chart(p,'SPY','US',n)['market_status'],'CLOSED_OR_UNVERIFIED')
    def test_incomplete_bar_excluded(self):
        p,n=fixture();r=analyze_chart(p,'SPY','US',n-10)
        self.assertEqual(len(r['bars']),24)
    def test_gap_blocks(self):
        p,n=fixture();p['chart']['result'][0]['timestamp'][10]+=60
        self.assertEqual(analyze_chart(p,'SPY','US',n)['bars'],[])
    def test_malformed_ohlc_blocks(self):
        p,n=fixture();p['chart']['result'][0]['indicators']['quote'][0]['low'][3]=999
        self.assertEqual(analyze_chart(p,'SPY','US',n)['bars'],[])
    def test_zero_volume_not_faked(self):
        p,n=fixture();p['chart']['result'][0]['indicators']['quote'][0]['volume']=[0]*25
        r=analyze_chart(p,'NIFTY','IN',n);self.assertIsNone(r['metrics']['vwap']);self.assertFalse(r['paper_eligible'])
    def test_provider_failure(self):
        r=analyze_chart({},'SPY','US',1);self.assertFalse(r['paper_eligible']);self.assertEqual(r['verdict'],'WAIT')
    def test_warmup(self):
        p,n=fixture();r=analyze_chart(p,'SPY','US',n-20*300);self.assertEqual(r['metrics'],{})
    def test_future_quote_blocks(self):
        p,n=fixture();p['chart']['result'][0]['meta']['regularMarketTime']=n+60
        self.assertFalse(analyze_chart(p,'SPY','US',n)['paper_eligible'])
if __name__=='__main__':unittest.main()
