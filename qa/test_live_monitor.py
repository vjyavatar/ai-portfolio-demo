"""Deterministic acceptance tests; no market/provider calls."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from qa.audit import validate_trading, trading_probes, main

NOW=10000

def report(verdict='WAIT'):
    return dict(symbol='SPY',region='US',source='Yahoo Finance chart',currency='USD',
        verdict=verdict,session_start=NOW-7000,session_end=NOW+7000,market_status='OPEN',
        price=500,quote_time=NOW-10,bar_close_time=NOW-20,
        provider_status={'code':'RESPONSE_RECEIVED'},bars=[{}]*21,
        stages=[{'name':name,'status':'pass'} for name in (
            'Data steward','Session guard','Trend analyst','Setup analyst','Risk critic','Quote guard')])

class LiveMonitorTests(unittest.TestCase):
    def check(self,data):return validate_trading(data,'SPY','US',NOW)[0]
    def test_fresh_candidate_passes(self):
        self.assertEqual(self.check(report('LONG_RESEARCH')),'PASS')
    def test_stale_or_future_candidate_fails(self):
        for field,value in [('quote_time',NOW-301),('quote_time',NOW+1),('bar_close_time',NOW-301),('bar_close_time',NOW+1)]:
            with self.subTest(field=field,value=value):
                d=report('LONG_RESEARCH');d[field]=value
                self.assertEqual(self.check(d),'FAIL')
    def test_quote_before_signal_close_fails(self):
        d=report('BEARISH_RESEARCH');d['quote_time']=NOW-30
        self.assertEqual(self.check(d),'FAIL')
    def test_candidate_outside_session_or_without_provider_fails(self):
        for updates in [{'session_end':NOW-1},{'provider_status':{'code':'RATE_LIMITED'}},{'session_start':None},{'price':float('nan')}]:
            d=report('LONG_RESEARCH');d.update(updates)
            self.assertEqual(self.check(d),'FAIL')
    def test_failed_gate_cannot_pass_candidate(self):
        d=report('LONG_RESEARCH');d['stages'][0]['status']='blocked'
        self.assertEqual(self.check(d),'FAIL')
    def test_missing_bars_cannot_pass_candidate(self):
        d=report('LONG_RESEARCH');d['bars']=[]
        self.assertEqual(self.check(d),'FAIL')
    def test_closed_wait_is_expected_not_feed_failure(self):
        d=report();d.update(session_end=NOW-1,market_status='CLOSED_OR_UNVERIFIED',quote_time=NOW-5000,bar_close_time=None)
        status,detail=validate_trading(d,'SPY','US',NOW)
        self.assertEqual(status,'PASS');self.assertIn('Closed-session WAIT',detail)
    def test_unavailable_is_not_closed_market_pass(self):
        d=report();d.update(provider_status={'code':'ACCESS_DENIED'},session_start=None,session_end=None)
        self.assertEqual(self.check(d),'UNVERIFIED')
    def test_unknown_session_not_pass(self):
        d=report();d['session_start']=None
        self.assertEqual(self.check(d),'UNVERIFIED')
    def test_stale_open_wait_is_unverified(self):
        d=report();d['quote_time']=NOW-301
        self.assertEqual(self.check(d),'UNVERIFIED')
    def test_fresh_open_wait_does_not_require_signal(self):
        self.assertEqual(self.check(report()),'PASS')
    def test_wrong_source_symbol_currency_fail(self):
        for field,value in [('source','unknown'),('symbol','AAPL'),('currency','INR'),('region','IN')]:
            d=report();d[field]=value
            self.assertEqual(self.check(d),'FAIL')
    def test_contradictory_session_state_fails(self):
        d=report();d['market_status']='CLOSED_OR_UNVERIFIED'
        self.assertEqual(self.check(d),'FAIL')
    def test_region_probe_selection(self):
        self.assertEqual([p for p,_ in trading_probes(['IN'])],['/api/trading-desk/research?symbol=RELIANCE&region=IN'])
        self.assertEqual(len(trading_probes(['IN','US'])),2)
    def test_lightweight_run_is_bounded_paced_and_records_unavailability(self):
        requested=[]
        def fake_fetch(base,path):
            requested.append(path)
            if path=='/health':data={'status':'healthy'}
            else:
                data=report();data['provider_status']={'code':'RATE_LIMITED'}
                if 'region=IN' in path:data.update(symbol='RELIANCE',region='IN',currency='INR')
            return 200,'application/json',json.dumps(data).encode(),0.1
        def fake_output(cmd,**kwargs):return '[]' if cmd[0]=='node' else 'fixture-commit'
        with tempfile.TemporaryDirectory() as folder, patch('sys.argv',['audit','--live','https://celesys.ai','--live-data-only','--output',folder]), patch('qa.audit.source_inventory',return_value=(['/'],[],[])), patch('qa.audit.fetch',side_effect=fake_fetch), patch('qa.audit.subprocess.check_output',side_effect=fake_output), patch('qa.audit.time.sleep') as sleeper:
            self.assertEqual(main(),0)
            saved=json.loads((Path(folder)/'report.json').read_text())
            self.assertEqual(len(requested),3)
            self.assertEqual(sleeper.call_count,2)
            self.assertTrue(all(call.args==(20,) for call in sleeper.call_args_list))
            checks=[c for c in saved['checks'] if '/api/trading-desk/research' in c['name']]
            self.assertEqual([c['status'] for c in checks],['UNVERIFIED','UNVERIFIED'])
            self.assertEqual(saved['target'],'https://celesys.ai')
