import json
import os
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
import option_chain as oc
import research_agents as ra
from discovery_site import attach_discovery, home_page, SEO_PATHS

EXP='2099-01-16'
def us_quote(kind='call', **kw):
    q=dict(underlying='SPY',root_symbol='SPY',expiration_date=EXP,strike=500,option_type=kind,contract_size=100,
           symbol='SPY990116'+kind[0].upper()+'00500000',bid=2,ask=2.2,open_interest=100,volume=50,
           bid_date=1000000,ask_date=1000000,greeks={'mid_iv':.2,'delta':.5})
    q.update(kw);return q

class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        app=FastAPI();attach_discovery(app);self.client=TestClient(app)
        oc._cache.clear();oc._retry.update(IN=0,US=0)
        ra._ai_cache.clear();ra._next_ai=0;ra._budget_runs=0
    def test_pages_are_indexable_and_unique(self):
        for path in SEO_PATHS:
            if path in ('/','/research','/trading/'):continue
            r=self.client.get(path);self.assertEqual(r.status_code,200,path)
            self.assertIn('href="https://celesys.ai'+path+'"',r.text)
            self.assertEqual(r.text.count('<h1>'),1,path)
        self.assertIn('Less noise.',home_page())
        self.assertEqual(self.client.get('/learn/not-a-guide').status_code,404)
    def test_public_feed_disabled_without_network(self):
        with patch.dict(os.environ,{},clear=True),patch('option_chain.urlopen') as call:
            r=self.client.get('/api/option-chain');self.assertEqual(r.json()['status'],'UNAVAILABLE')
            self.assertFalse(call.called);self.assertEqual(r.headers['x-robots-tag'],'noindex')
    def test_inputs(self):
        for params in [{'region':'EU'},{'symbol':'http://evil'},{'expiry':'2026-99-99'},{'symbol':'RELIANCE','region':'IN'},{'symbol':'NIFTY','region':'US'}]:
            self.assertEqual(self.client.get('/api/option-chain',params=params).status_code,422)
    def test_us_normalization_identity_missing_zero(self):
        rows,spot=oc.normalize({'options':{'option':[us_quote(open_interest=0),us_quote('put',open_interest=None),us_quote(strike=501,underlying='QQQ')]}},'US','SPY',EXP)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['call']['oi'],0)
        self.assertIsNone(rows[0]['put']['oi']);self.assertEqual(rows[0]['call']['iv_pct'],20)
        self.assertEqual(rows[0]['call']['bid_time'],1000)
    def test_india_missing_time_not_fetch_time(self):
        payload={'data':[{'expiry':EXP,'underlying_key':oc.INDICES['NIFTY'],'strike_price':25000,'underlying_spot_price':24900,
            'call_options':{'market_data':{'oi':10,'prev_oi':15,'bid_price':10,'ask_price':11},'option_greeks':{'iv':20}},'put_options':None}]}
        rows,spot=oc.normalize(payload,'IN','NIFTY',EXP)
        self.assertEqual(rows[0]['call']['oi_change'],-5);self.assertEqual(rows[0]['call']['iv_pct'],20)
        self.assertIsNone(rows[0]['call']['bid_time']);self.assertIsNone(rows[0]['put'])
        self.assertEqual(oc.snapshot({'rows':rows,'fetched_at':1000},1001)['freshness'],'UNVERIFIED_OR_STALE')
    def test_cached_timestamp_revalidated(self):
        rows,_=oc.normalize({'options':{'option':[us_quote(),us_quote('put')]}},'US','SPY',EXP)
        b={'rows':rows,'fetched_at':1000}
        self.assertEqual(oc.snapshot(b,1100)['freshness'],'RECENT_QUOTES')
        self.assertEqual(oc.snapshot(b,1400)['freshness'],'UNVERIFIED_OR_STALE')
    def test_success_expiry_selection_cache(self):
        env={'CELESYS_PUBLIC_OPTIONS_US':'true','CELESYS_OPTIONS_DATA_TOKEN':'test-token'}
        with patch.dict(os.environ,env),patch('option_chain.get_json',side_effect=[{'expirations':{'date':[EXP]}},{'options':{'option':[us_quote()]}}]) as get:
            a=self.client.get('/api/option-chain?region=US&symbol=SPY').json()
            b=self.client.get('/api/option-chain?region=US&symbol=SPY').json()
        self.assertEqual(a['status'],'SNAPSHOT');self.assertEqual(b['expiry'],EXP);self.assertEqual(get.call_count,2)
        self.assertNotIn('test-token',str(a))
    def test_provider_failure_cooldown_redacted(self):
        from urllib.error import HTTPError
        with patch.dict(os.environ,{'CELESYS_PUBLIC_OPTIONS_US':'true','CELESYS_OPTIONS_DATA_TOKEN':'test'}),patch('option_chain.get_json',side_effect=HTTPError('u',429,'SECRET',{'Retry-After':'900'},None)) as get:
            first=self.client.get('/api/option-chain?region=US&symbol=SPY').json()
            second=self.client.get('/api/option-chain?region=US&symbol=QQQ').json()
        self.assertEqual(get.call_count,1);self.assertNotIn('SECRET',str(first));self.assertEqual(second['status'],'UNAVAILABLE')
    def test_agent_rules_fallback_no_network(self):
        b=ra.stock_brief({'success':True,'summary':{'trailing_pe':12,'fcf_ttm':0}},'AAPL','US')
        with patch.dict(os.environ,{},clear=True),patch('research_agents.model_json') as model:
            result=ra.ai_review(b)
        self.assertFalse(model.called);self.assertEqual(result['ai_status'],'NOT_ENABLED')
        self.assertTrue(any(e['value']==0 for e in result['evidence']))
    def test_agent_critic_withholds(self):
        b=ra.stock_brief({'success':True,'summary':{'trailing_pe':12}},'AAPL','US')
        draft=dict(assessment='Review valuation.',counterargument='Growth is unknown.',next_check='Read filings.',evidence_ids=['E1'])
        with patch.dict(os.environ,{'CELESYS_AGENTS_AI_ENABLED':'true','ANTHROPIC_API_KEY':'test'}),patch('research_agents.model_json',side_effect=[draft,{'approved':False,'reason':'Unsupported'}]) as model:
            result=ra.ai_review(b)
        self.assertEqual(model.call_count,2);self.assertIsNone(result['ai']);self.assertEqual(result['ai_status'],'CRITIC_WITHHELD')
    def test_invalid_citations_never_published(self):
        b=ra.stock_brief({'success':True,'summary':{'trailing_pe':12}},'AAPL','US')
        with patch.dict(os.environ,{'CELESYS_AGENTS_AI_ENABLED':'true','ANTHROPIC_API_KEY':'test'}),patch('research_agents.model_json',return_value=dict(assessment='Review',counterargument='Unknown',next_check='Check',evidence_ids=['E900'])):
            result=ra.ai_review(b)
        self.assertIsNone(result['ai']);self.assertEqual(result['ai_status'],'AI_UNAVAILABLE')
    def test_stale_and_absent_evidence_never_sent_to_ai(self):
        with patch.dict(os.environ,{'CELESYS_AGENTS_AI_ENABLED':'true','ANTHROPIC_API_KEY':'test'}),patch('research_agents.model_json') as model:
            b=ra.trading_brief({'quote_time':1,'price':100},'SPY','US');ra.ai_review(b)
            self.assertEqual(b['ai_status'],'BLOCKED_STALE_EVIDENCE');self.assertFalse(model.called)
    def test_approved_ai_keeps_calculated_assessment_and_caches(self):
        b=ra.stock_brief({'success':True,'summary':{'trailing_pe':12}},'AAPL','US')
        baseline=b['assessment']
        draft=dict(assessment='Valuation requires context.',counterargument='Growth is unknown.',next_check='Read filings.',evidence_ids=['E1'])
        with patch.dict(os.environ,{'CELESYS_AGENTS_AI_ENABLED':'true','ANTHROPIC_API_KEY':'test'}),patch('research_agents.model_json',side_effect=[draft,{'approved':True,'reason':'Acknowledges gaps.'}]) as model:
            first=ra.ai_review(b)
            second=ra.ai_review(ra.stock_brief({'success':True,'summary':{'trailing_pe':12}},'AAPL','US'))
        self.assertEqual(first['assessment'],baseline);self.assertEqual(second['ai_status'],'AI_REVIEWED');self.assertEqual(model.call_count,2)
    def test_stock_brief_endpoint_does_not_leak_provider_errors(self):
        async def broken(**kwargs):raise RuntimeError('private error secret')
        ra.configure_dashboard(broken)
        with patch.dict(os.environ,{},clear=True):
            result=self.client.get('/api/research-brief?mode=stock&symbol=AAPL&region=US')
        ra.configure_dashboard(None)
        self.assertEqual(result.status_code,200);self.assertNotIn('private error secret',result.text)
        self.assertEqual(result.json()['evidence'],[])
    def test_options_brief_handles_missing_side(self):
        b=ra.options_brief({'rows':[{'call':None,'put':{'oi':10}}],'source':'Test','freshness':'UNVERIFIED'},'SPY','US')
        self.assertFalse(any(e['label']=='call OI' for e in b['evidence']))

if __name__=='__main__':unittest.main()
