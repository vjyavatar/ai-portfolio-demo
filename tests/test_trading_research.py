import unittest
from trading_research import analyze_chart

def fixture():
    start=1790947800
    prices=[100+i*.02 for i in range(24)]+[100.75]
    stamps=[start+i*300 for i in range(25)]
    q={'open':[v-.02 for v in prices],'high':[v+.14 for v in prices],'low':[v-.17 for v in prices],'close':prices,'volume':[1000]*24+[1800]}
    now=stamps[-1]+301
    return {'chart':{'result':[{'meta':{'symbol':'SPY','currency':'USD','dataGranularity':'5m','regularMarketPrice':prices[-1],'regularMarketTime':now-1,'instrumentType':'ETF','currentTradingPeriod':{'regular':{'start':start,'end':start+23400}}},'timestamp':stamps,'indicators':{'quote':[q]}}]}},now
class ResearchTests(unittest.TestCase):
    def test_fresh_signal_not_probability(self):
        p,n=fixture();r=analyze_chart(p,'SPY','US',n)
        self.assertEqual(r['verdict'],'LONG_RESEARCH');self.assertTrue(r['paper_eligible'])
        self.assertNotIn('confidence',r)
        self.assertEqual(r['metrics']['relative_volume'],1.8)
    def test_raw_index_is_never_paper_stock(self):
        p,n=fixture();p['chart']['result'][0]['meta']['instrumentType']='INDEX';p['chart']['result'][0]['meta']['symbol']='^GSPC'
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
        p,n=fixture();p['chart']['result'][0]['meta']['currency']='INR';p['chart']['result'][0]['meta']['symbol']='^NSEI';p['chart']['result'][0]['indicators']['quote'][0]['volume']=[0]*25
        r=analyze_chart(p,'NIFTY','IN',n);self.assertIsNone(r['metrics']['vwap']);self.assertFalse(r['paper_eligible'])
    def test_provider_failure(self):
        r=analyze_chart({},'SPY','US',1);self.assertFalse(r['paper_eligible']);self.assertEqual(r['verdict'],'WAIT')
    def test_warmup(self):
        p,n=fixture();r=analyze_chart(p,'SPY','US',n-20*300);self.assertEqual(r['metrics'],{})
    def test_future_quote_blocks(self):
        p,n=fixture();p['chart']['result'][0]['meta']['regularMarketTime']=n+60
        self.assertFalse(analyze_chart(p,'SPY','US',n)['paper_eligible'])

    def test_quote_reversal_invalidates_closed_bar_candidate(self):
        p,n=fixture();p['chart']['result'][0]['meta']['regularMarketPrice']=100.10
        r=analyze_chart(p,'SPY','US',n)
        self.assertEqual(r['verdict'],'WAIT')
        self.assertEqual(next(s for s in r['stages'] if s['name']=='Quote guard')['status'],'blocked')
    def test_quote_chasing_blocks(self):
        p,n=fixture();p['chart']['result'][0]['meta']['regularMarketPrice']=102
        self.assertEqual(analyze_chart(p,'SPY','US',n)['verdict'],'WAIT')
    def test_wrong_currency_and_interval_block(self):
        for key,value in [('currency','CAD'),('dataGranularity','1d')]:
            p,n=fixture();p['chart']['result'][0]['meta'][key]=value
            self.assertEqual(analyze_chart(p,'SPY','US',n)['verdict'],'WAIT')
    def test_missing_or_wrong_source_symbol_blocks(self):
        for identity in (None, 'QQQ', 'SPY.NS'):
            p,n=fixture();p['chart']['result'][0]['meta']['symbol']=identity
            r=analyze_chart(p,'SPY','US',n)
            self.assertEqual(r['verdict'],'WAIT');self.assertFalse(r['paper_eligible'])
            self.assertIn('symbol',r['reason'])
    def test_indian_equity_identity_suffix_is_verified(self):
        for requested,provided in [('RELIANCE','RELIANCE.NS'),('RELIANCE.NS','RELIANCE.NS'),('RELIANCE.BO','RELIANCE.BO')]:
            p,n=fixture();meta=p['chart']['result'][0]['meta']
            meta.update(symbol=provided,currency='INR')
            self.assertEqual(analyze_chart(p,requested,'IN',n)['verdict'],'LONG_RESEARCH')
    def test_quote_before_closed_signal_bar_blocks(self):
        p,n=fixture();p['chart']['result'][0]['meta']['regularMarketTime']=n-299
        r=analyze_chart(p,'SPY','US',n)
        self.assertEqual(r['verdict'],'WAIT');self.assertFalse(r['paper_eligible'])
        self.assertEqual(r['stages'][0]['status'],'blocked')
    def test_missing_latest_closed_bar_blocks_even_with_new_quote(self):
        p,n=fixture();p['chart']['result'][0]['meta']['regularMarketTime']=n+500
        r=analyze_chart(p,'SPY','US',n+500)
        self.assertEqual(r['verdict'],'WAIT');self.assertFalse(r['paper_eligible'])
    def test_closed_bar_age_boundary(self):
        for elapsed,verdict in [(299,'LONG_RESEARCH'),(300,'WAIT')]:
            p,n=fixture();p['chart']['result'][0]['meta']['regularMarketTime']=n+elapsed
            self.assertEqual(analyze_chart(p,'SPY','US',n+elapsed)['verdict'],verdict)
if __name__=='__main__':unittest.main()
