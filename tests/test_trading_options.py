import unittest, os
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import patch
import trading_options as o

class OptionsTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,2,16,0,tzinfo=timezone.utc).timestamp()
        self.r=dict(symbol='SPY',region='US',verdict='LONG_RESEARCH',market_status='OPEN',
            quote_time=self.now-1,bar_close_time=self.now-60,session_start=self.now-7200,session_end=self.now+3600,
            scenario=dict(entry=700,stop=698,target=704,kind='UNDERLYING_ONLY'),
            stages=[{'name':name,'status':'pass'} for name in (
                'Data steward','Session guard','Trend analyst','Setup analyst','Risk critic','Quote guard')])
        self.q=dict(symbol='SPY261005C00700000',underlying='SPY',root_symbol='SPY',type='option',
            option_type='call',contract_size=100,expiration_date='2026-10-05',strike=700,
            bid=3,ask=3.1,bid_date=(self.now-1)*1000,ask_date=(self.now-1)*1000,
            volume=500,open_interest=1000,bidsize=10,asksize=10,
            greeks=dict(delta=.55,mid_iv=.25,updated_at='2026-10-02T15:59:00+00:00'))
        o._cache.clear();o._retry_at=0
    def test_call_and_put(self):
        for direction,verdict,sign in [('call','LONG_RESEARCH',1),('put','BEARISH_RESEARCH',-1)]:
            q=deepcopy(self.q);r=deepcopy(self.r);r['verdict']=verdict
            q['option_type']=direction;q['symbol']='SPY261005'+direction[0].upper()+'00700000'
            q['greeks']['delta']=.55*sign
            if direction=='put':r['scenario'].update(stop=702,target=696)
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
    def test_future_greek_timestamp_blocks(self):
        q=deepcopy(self.q);q['greeks']['updated_at']='2026-10-02T16:00:01Z'
        self.assertEqual(o.assess(self.r,[q],self.now)['status'],'WAIT')
    def test_malformed_greek_timestamp_blocks(self):
        for value in ('2026-10-02garbage','2026-10-02T99:99:00Z',None,123):
            q=deepcopy(self.q);q['greeks']['updated_at']=value
            self.assertEqual(o.assess(self.r,[q],self.now)['status'],'WAIT')
    def test_old_greek_timestamp_blocks(self):
        q=deepcopy(self.q);q['greeks']['updated_at']='2026-10-02T14:59:59+00:00'
        self.assertEqual(o.assess(self.r,[q],self.now)['status'],'WAIT')
    def test_naive_greek_timestamp_blocks_without_timezone_guess(self):
        for value in ('2026-10-02 15:59:00','2026-10-02'):
            q=deepcopy(self.q);q['greeks']['updated_at']=value
            self.assertEqual(o.assess(self.r,[q],self.now)['status'],'WAIT')
    def test_explicit_offsets_and_hourly_estimate_expiration(self):
        for value in ('2026-10-02T15:00:10Z','2026-10-02T11:00:10-04:00','2026-10-02T20:30:10+05:30'):
            q=deepcopy(self.q);q['greeks']['updated_at']=value
            d=o.assess(self.r,[q],self.now)
            self.assertEqual(d['status'],'BUY_CALL_CANDIDATE')
            self.assertEqual(d['candidate']['expires_at'],self.now+10)
            self.assertEqual(d['candidate']['greeks_kind'],'HOURLY_PROVIDER_ESTIMATE_NOT_LIVE')
            self.assertEqual(o.assess(self.r,[q],self.now+11)['status'],'WAIT')
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
    def test_quote_entry_risk_and_illustrative_exits_are_distinct(self):
        c=o.assess(self.r,[self.q],self.now)['candidate']
        self.assertEqual(c['entry']['low'],3)
        self.assertEqual(c['entry']['high'],3.1)
        self.assertEqual(c['entry']['limit_cap'],3.1)
        self.assertFalse(c['entry']['fill_guaranteed'])
        self.assertEqual(c['contract_multiplier'],100)
        self.assertEqual(c['premium_risk']['maximum_loss_per_contract'],310)
        self.assertTrue(c['premium_risk']['excludes_fees'])
        self.assertEqual(c['exit_policy']['stop_premium'],2.33)
        self.assertEqual(c['exit_policy']['target_premium'],4.65)
        self.assertEqual(c['exit_policy']['kind'],'ILLUSTRATIVE_POLICY_NOT_FORECAST')
        self.assertFalse(c['exit_policy']['stop_loss_guaranteed'])
        self.assertEqual(c['underlying_invalidation'],698)
        self.assertEqual(c['underlying_target'],704)
        self.assertEqual(c['underlying_risk_kind'],'UNDERLYING_PRICE_NOT_OPTION_PREMIUM')
    def test_no_calibrated_probability_is_created(self):
        for quotes in ([self.q],[]):
            d=o.assess(self.r,quotes,self.now)
            self.assertEqual(d['confidence']['status'],'UNCALIBRATED')
            self.assertIsNone(d['confidence']['success_probability'])
            if d['candidate']:self.assertEqual(d['candidate']['confidence'],d['confidence'])
    def test_invalid_session_or_signal_quote_order_blocks(self):
        for updates in ({'session_start':None},{'session_start':self.now+1},{'session_start':self.now-90000},
                        {'quote_time':self.now-61},{'session_start':self.now-30}):
            with self.subTest(updates=updates):
                r=deepcopy(self.r);r.update(updates)
                self.assertEqual(o.assess(r,[self.q],self.now)['status'],'WAIT')
    def test_invalid_underlying_level_order_blocks(self):
        for changes in ({'stop':701},{'target':699},{'kind':'OPTION_PREMIUM'},{'entry':None},{'stop':0}):
            r=deepcopy(self.r);r['scenario'].update(changes)
            self.assertEqual(o.assess(r,[self.q],self.now)['status'],'WAIT')
    def test_option_quotes_must_follow_signal_close(self):
        for field in ('bid_date','ask_date'):
            q=deepcopy(self.q);q[field]=(self.now-61)*1000
            self.assertEqual(o.assess(self.r,[q],self.now)['status'],'WAIT')
    def test_candidate_not_returned_at_exact_expiration_boundary(self):
        q=deepcopy(self.q);q['greeks']['updated_at']='2026-10-02T15:00:00Z'
        self.assertEqual(o.assess(self.r,[q],self.now)['status'],'WAIT')
    def test_strike_cannot_be_rounded_into_different_contract_identity(self):
        q=deepcopy(self.q);q['strike']=700.0001
        self.assertEqual(o.assess(self.r,[q],self.now)['status'],'WAIT')
    def test_requested_expiry_must_match_returned_contract(self):
        self.assertEqual(o.assess(self.r,[self.q],self.now,expected_expiry='2026-10-06')['status'],'WAIT')
    def test_ranking_prioritizes_relative_spread_and_discloses_coverage(self):
        wider=deepcopy(self.q);wider.update(strike=701,symbol='SPY261005C00701000',bid=3,ask=3.2)
        wider['greeks']['delta']=.55
        tight=deepcopy(self.q);tight['greeks']['delta']=.45
        d=o.assess(self.r,[wider,tight],self.now,expected_expiry='2026-10-05')
        self.assertEqual(d['candidate']['contract'],tight['symbol'])
        self.assertEqual(d['coverage']['contracts_received'],2)
        self.assertEqual(d['coverage']['contracts_passed'],2)
        self.assertEqual(d['coverage']['requested_expiry'],'2026-10-05')
        self.assertEqual(d['candidate']['ranking']['eligible_contracts'],2)
        self.assertIn('not expected profit',d['candidate']['ranking']['note'])
    def test_policy_is_omitted_when_cent_rounding_prevents_distinct_stop(self):
        q=deepcopy(self.q);q.update(bid=.01,ask=.01)
        d=o.assess(self.r,[q],self.now)
        self.assertIsNone(d['candidate']['exit_policy'])
    def test_adapter_validates_requested_expiry_on_fresh_and_cached_chain(self):
        q=deepcopy(self.q);q.update(expiration_date='2026-10-06',symbol='SPY261006C00700000')
        with patch.dict(os.environ,{'CELESYS_OPTIONS_DATA_ENABLED':'true','CELESYS_OPTIONS_DATA_TOKEN':'test-only'}),patch('trading_options.time.time',return_value=self.now),patch('trading_options._get',side_effect=[{'expirations':{'date':['2026-10-05']}},{'options':{'option':[q]}}]) as get:
            self.assertEqual(o.option_research(self.r)['status'],'WAIT')
            self.assertEqual(o.option_research(self.r)['status'],'WAIT')
            self.assertEqual(get.call_count,2)
    def test_stale_cache_or_failed_research_guards_never_produce_candidate(self):
        for changes in ({'stale_cache':True},{'stages':None},{'stages':[]},
                        {'stages':self.r['stages']+[{'name':'Provider availability','status':'blocked'}]}):
            r=deepcopy(self.r);r.update(changes)
            self.assertEqual(o.assess(r,[self.q],self.now)['status'],'WAIT')
        r=deepcopy(self.r);r['stages'][0]['status']='watch'
        self.assertEqual(o.assess(r,[self.q],self.now)['status'],'WAIT')
