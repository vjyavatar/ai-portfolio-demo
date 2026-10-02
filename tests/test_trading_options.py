import unittest, os
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import patch
import trading_options as o

class OptionsTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,2,16,0,tzinfo=timezone.utc).timestamp()
        self.r=dict(symbol='SPY',region='US',verdict='LONG_RESEARCH',market_status='OPEN',
            quote_time=self.now-1,bar_close_time=self.now-60,session_end=self.now+3600,
            scenario=dict(entry=700,stop=698,target=704))
        self.q=dict(symbol='SPY261005C00700000',underlying='SPY',root_symbol='SPY',type='option',
            option_type='call',contract_size=100,expiration_date='2026-10-05',strike=700,
            bid=3,ask=3.1,bid_date=(self.now-1)*1000,ask_date=(self.now-1)*1000,
            volume=500,open_interest=1000,bidsize=10,asksize=10,
            greeks=dict(delta=.55,mid_iv=.25,updated_at='2026-10-02 15:59:00'))
        o._cache.clear();o._retry_at=0
    def test_call_and_put(self):
        for direction,verdict,sign in [('call','LONG_RESEARCH',1),('put','BEARISH_RESEARCH',-1)]:
            q=deepcopy(self.q);r=deepcopy(self.r);r['verdict']=verdict
            q['option_type']=direction;q['symbol']='SPY261005'+direction[0].upper()+'00700000'
            q['greeks']['delta']=.55*sign
            d=o.assess(r,[q],self.now)
            self.assertEqual(d['status'],'BUY_'+direction.upper()+'_CANDIDATE')
            self.assertEqual(d['candidate']['premium_at_risk'],310)
            self.assertFalse(d['execution_enabled'])
    def test_contract_rejections(self):
        cases=dict(symbol='QQQ261005C00700000',root_symbol='SPY1',underlying='QQQ',type='stock',
            option_type='put',contract_size=10,expiration_date='2026-10-02',strike=-1,
            bid=0,ask=10,bid_date=(self.now-301)*1000,ask_date=(self.now+1)*1000,
            volume=0,open_interest=0,bidsize=0,asksize=0,greeks=None)
        for k,v in cases.items():
            with self.subTest(k=k):
                q=deepcopy(self.q);q[k]=v
                self.assertEqual(o.assess(self.r,[q],self.now)['status'],'WAIT')
    def test_underlying_rejections(self):
        for k,v in dict(verdict='WAIT',region='IN',symbol='NVDA',market_status='CLOSED',
                        quote_time=self.now-301,bar_close_time=self.now+1,session_end=self.now-1).items():
            with self.subTest(k=k):
                r=deepcopy(self.r);r[k]=v
                self.assertEqual(o.assess(r,[self.q],self.now)['status'],'WAIT')
    def test_cache_never_renews_quote(self):
        self.assertEqual(o.assess(self.r,[self.q],self.now+301)['status'],'WAIT')
    def test_disabled_never_networks(self):
        with patch.dict(os.environ,{},clear=True),patch('trading_options._get') as get:
            self.assertEqual(o.option_research(self.r)['status'],'WAIT');get.assert_not_called()
    def test_adapter_cache_and_failure(self):
        with patch.dict(os.environ,{'CELESYS_OPTIONS_DATA_ENABLED':'true','CELESYS_OPTIONS_DATA_TOKEN':'test-only'}),patch('trading_options.time.time',return_value=self.now):
            with patch('trading_options._get',side_effect=[{'expirations':{'date':['2026-10-02','2026-10-05']}},{'options':{'option':[self.q]}}]) as get:
                self.assertEqual(o.option_research(self.r)['status'],'BUY_CALL_CANDIDATE')
                self.assertEqual(o.option_research(self.r)['status'],'BUY_CALL_CANDIDATE')
                self.assertEqual(get.call_count,2)
            o._cache.clear();o._retry_at=0
            with patch('trading_options._get',side_effect=TimeoutError('SECRET')) as get:
                d=o.option_research(self.r);self.assertNotIn('SECRET',str(d))
                self.assertEqual(d['status'],'WAIT');o.option_research(self.r)
                self.assertEqual(get.call_count,1)
