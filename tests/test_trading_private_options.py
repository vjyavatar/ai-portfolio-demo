"""Private option routes: deterministic provider fixtures, never live credentials."""
import os
import sys
import types
import unittest
from unittest.mock import Mock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
import private_options as subject

NOW = 1791817200  # 2026-10-12, before fixture expiries.
US_ENV = {'CELESYS_LICENSED_OPTIONS_US':'true','CELESYS_OPTIONS_DATA_TOKEN':'fixture-only'}
DHAN_ENV = {'CELESYS_LICENSED_OPTIONS_IN':'true','CELESYS_DHAN_ACCESS_TOKEN':'fixture-only',
            'CELESYS_DHAN_CLIENT_ID':'fixture-client','CELESYS_DHAN_INSTRUMENTS_JSON':'{"NIFTY":{"id":13,"segment":"IDX_I"}}'}

def us_quote(side='call', expiry='2026-10-15'):
    return dict(symbol='SPY'+expiry.replace('-','')[2:]+side[0].upper()+'00600000',
                root_symbol='SPY',underlying='SPY',expiration_date=expiry,strike=600,
                option_type=side,contract_size=100,bid=2,ask=2.1,last=2.05,
                bid_date=(NOW-2)*1000,ask_date=(NOW-1)*1000,open_interest=1200,volume=200,
                greeks={'mid_iv':.25,'delta':.55 if side=='call' else -.45,'updated_at':'2026-10-12T14:00:00Z'})

class PrivateOptionTests(unittest.TestCase):
    def setUp(self):
        subject._cache.clear();subject._next.update(IN=0,US=0)
        self.env=patch.dict(os.environ,{},clear=True);self.env.start();self.addCleanup(self.env.stop)
        self.identity=patch('secure_access.identity');self.user=self.identity.start();self.addCleanup(self.identity.stop)
        self.user.get.return_value={'email':'qa@example.invalid','full':True}
        self.network=patch('private_options.request_json',side_effect=AssertionError('Unexpected provider request'))
        self.request=self.network.start();self.addCleanup(self.network.stop)
        self.clock=patch('private_options.time.time',return_value=NOW);self.clock.start();self.addCleanup(self.clock.stop)
        app=FastAPI();app.include_router(subject.router);self.client=TestClient(app)

    def test_anonymous_spoofed_header_and_non_full_never_reach_provider_or_config(self):
        with patch('private_options.ready') as ready:
            for identity in (None,{'full':False,'email':'qa@example.invalid'}):
                self.user.get.return_value=identity
                for path in ('status','chain?region=IN&symbol=NIFTY'):
                    r=self.client.get('/api/private-options/'+path,headers={'X-Celesys-Email':'admin@example.invalid'})
                    self.assertEqual(r.status_code,401)
            ready.assert_not_called();self.request.assert_not_called()

    def test_missing_configuration_returns_no_quotes_without_network(self):
        # Avoid depending on an installed Angel SDK for a read-only missing-config path.
        angel=types.SimpleNamespace(configured=Mock(return_value=False),chain=Mock())
        with patch.dict(sys.modules,angel_options=angel):
            status=self.client.get('/api/private-options/status').json()
            self.assertEqual(status['providers']['IN'],'Angel One SmartAPI')
            self.assertFalse(status['IN']);self.assertFalse(status['US']);self.assertFalse(status['connection_verified'])
            for region,symbol in [('IN','NIFTY'),('US','SPY')]:
                result=self.client.get('/api/private-options/chain',params={'region':region,'symbol':symbol}).json()
                self.assertEqual(result['status'],'UNAVAILABLE');self.assertEqual(result['rows'],[])
                self.assertFalse(result['execution_enabled'])
            angel.chain.assert_not_called();self.request.assert_not_called()

    def test_configured_angel_delegation_preserves_symbol_expiry_and_payload(self):
        result={'symbol':'NIFTY','region':'IN','source':'Angel One SmartAPI','currency':'INR','rows':[],'status':'UNAVAILABLE'}
        angel=types.SimpleNamespace(configured=Mock(return_value=True),chain=Mock(return_value=result))
        with patch.dict(sys.modules,angel_options=angel),patch.dict(os.environ,{'CELESYS_LICENSED_OPTIONS_IN':'true'}):
            r=self.client.get('/api/private-options/chain',params={'region':'IN','symbol':'NIFTY','expiry':'2026-10-15'})
        self.assertEqual(r.status_code,200);self.assertEqual(r.json(),result)
        angel.chain.assert_called_once_with('NIFTY','2026-10-15');self.request.assert_not_called()

    def test_existing_dhan_config_stays_dhan_and_preserves_unknown_quote_timestamps(self):
        self.request.side_effect=[{'data':['2026-10-15']},{'status':'success','data':{'last_price':25000,'oc':{'25000':{'ce':{'security_id':123,'top_bid_price':100,'top_ask_price':102,'last_price':101,'oi':1000,'previous_oi':900,'volume':200,'implied_volatility':20,'greeks':{'delta':.5}}}}}}]
        with patch.dict(os.environ,DHAN_ENV),patch('private_options.time.sleep') as sleep:
            self.assertEqual(subject.india_provider(),'dhan')
            d=self.client.get('/api/private-options/chain',params={'region':'IN','symbol':'NIFTY'}).json()
        self.assertEqual(d['source'],'Dhan');self.assertEqual(d['currency'],'INR');self.assertEqual(d['status'],'SNAPSHOT')
        self.assertEqual(d['freshness'],'UNVERIFIED_OR_STALE');self.assertIsNone(d['rows'][0]['call']['bid_time'])
        self.assertEqual(d['rows'][0]['call']['oi_change'],100);self.assertIsNone(d['rows'][0]['put'])
        self.assertEqual(self.request.call_count,2);sleep.assert_called_once_with(3.1)
        self.assertEqual(self.request.call_args.args[2],{'UnderlyingScrip':13,'UnderlyingSeg':'IDX_I','Expiry':'2026-10-15'})

    def test_tradier_normalizes_both_sides_and_cache_preserves_source_times(self):
        self.request.side_effect=[{'expirations':{'date':['2026-10-16','2026-10-15']}},{'options':{'option':[us_quote(),us_quote('put'),dict(us_quote(),underlying='QQQ')]}}]
        with patch.dict(os.environ,US_ENV):
            d=self.client.get('/api/private-options/chain').json()
            with patch('private_options.time.time',return_value=NOW+30):cached=self.client.get('/api/private-options/chain').json()
        self.assertEqual(d['expiry'],'2026-10-15');self.assertEqual(d['expiries'],['2026-10-15','2026-10-16'])
        self.assertEqual(d['currency'],'USD');self.assertEqual(d['freshness'],'RECENT_QUOTES');self.assertEqual(len(d['rows']),1)
        self.assertEqual(d['rows'][0]['call']['iv_pct'],25);self.assertEqual(d['rows'][0]['put']['delta'],-.45)
        self.assertEqual(cached['rows'],d['rows']);self.assertEqual(cached['fetched_at'],NOW);self.assertEqual(cached['age_seconds'],30)
        self.assertEqual(self.request.call_count,2)

    def test_provider_failure_has_bounded_cooldown_and_never_substitutes_quotes(self):
        self.request.side_effect=TimeoutError('Do not expose fixture token')
        with patch.dict(os.environ,US_ENV):
            first=self.client.get('/api/private-options/chain').json();second=self.client.get('/api/private-options/chain').json()
        self.assertEqual(first['retry_after'],NOW+300);self.assertEqual(second['retry_after'],NOW+300)
        self.assertEqual(second['rows'],[]);self.assertEqual(second['status'],'UNAVAILABLE')
        self.assertNotIn('fixture token',str(first));self.assertEqual(self.request.call_count,1)

    def test_invalid_expiry_rejected_before_provider_and_unlisted_expiry_before_chain(self):
        with patch.dict(os.environ,US_ENV):
            for expiry in ('2026-02-30','20261015','2026-1-1','https://example.invalid'):
                self.assertEqual(self.client.get('/api/private-options/chain',params={'expiry':expiry}).status_code,422)
            self.request.assert_not_called()
            self.request.side_effect=[{'expirations':{'date':'2026-10-15'}}]
            self.assertEqual(self.client.get('/api/private-options/chain',params={'expiry':'2026-10-16'}).status_code,422)
            self.assertEqual(self.request.call_count,1)

if __name__=='__main__':unittest.main()
