import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from trading_site import attach_trading_desk,market_symbol,_cache,_failures,_provider_state
from test_trading_research import fixture

class RouteTests(unittest.TestCase):
    def setUp(self):
        self.app=FastAPI();attach_trading_desk(self.app);self.client=TestClient(self.app);_cache.clear();_failures.clear();_provider_state.update(retry_after=0,checked_at=None,code="NOT_CHECKED",failures=0,requests=0,cache_hits=0,stale_served=0,cache_rechecks=0,cooldown_hits=0,singleflight_hits=0)
    def test_mount_and_security_headers(self):
        r=self.client.get('/trading/');self.assertEqual(r.status_code,200)
        self.assertIn("script-src 'self'",r.headers['content-security-policy'])
        self.assertEqual(self.client.get('/trading/paper.mjs').status_code,200)
    def test_no_execution_capability(self):
        self.assertFalse(self.client.get('/api/trading-desk/status').json()['execution_enabled'])
        self.assertEqual(self.client.post('/api/trading-desk/orders',json={}).status_code,404)
    def test_reject_url_input(self):
        self.assertEqual(self.client.get('/api/trading-desk/research',params={'symbol':'https://example.com','region':'US'}).status_code,422)
    def test_mapping_and_region(self):
        self.assertEqual(market_symbol('RELIANCE','IN'),('RELIANCE','RELIANCE.NS'))
        self.assertEqual(market_symbol('SPX','US'),('SPX','^GSPC'))
        with self.assertRaises(ValueError):market_symbol('NIFTY','US')
    def test_failure_is_wait_not_fake_price(self):
        with patch('trading_site.urlopen',side_effect=TimeoutError):
            d=self.client.get('/api/trading-desk/research').json()
        self.assertEqual(d['verdict'],'WAIT');self.assertFalse(d['paper_eligible']);self.assertNotIn('price',d)
    def test_cached_data_rechecks_quote_freshness(self):
        p,n=fixture();_cache[('SPY','US')]=(n,p)
        with patch('trading_site.time.time',return_value=n+30):
            d=self.client.get('/api/trading-desk/research').json()
        self.assertEqual(d['quote_time'],n-1);self.assertEqual(d['fetched_at'],n)
    def test_attach_idempotent(self):
        count=len(self.app.routes);attach_trading_desk(self.app);self.assertEqual(len(self.app.routes),count)

    def test_rate_limit_is_classified_without_leaking_error_body(self):
        from urllib.error import HTTPError
        with patch('trading_site.urlopen',side_effect=HTTPError('url',429,'private provider details',{},None)) as call:
            d=self.client.get('/api/trading-desk/research').json()
            second=self.client.get('/api/trading-desk/research').json()
        self.assertEqual(d['provider_status']['code'],'RATE_LIMITED')
        self.assertEqual(call.call_count,1)
        self.assertEqual(second['verdict'],'WAIT')
        self.assertNotIn('private provider details',str(d))
    def test_access_denial_is_not_mislabeled_closed_market(self):
        from urllib.error import HTTPError
        with patch('trading_site.urlopen',side_effect=HTTPError('url',403,'Forbidden',{},None)):
            d=self.client.get('/api/trading-desk/research').json()
        self.assertEqual(d['provider_status']['code'],'ACCESS_DENIED')
        self.assertFalse(d['paper_eligible'])

    def test_cooldown_spans_symbols_and_honors_retry_after(self):
        from urllib.error import HTTPError
        with patch('trading_site.time.time',return_value=1000), patch('trading_site.urlopen',side_effect=HTTPError('url',429,'rate limit',{'Retry-After':'1200'},None)) as call:
            first=self.client.get('/api/trading-desk/research',params={'symbol':'SPY'}).json()
            second=self.client.get('/api/trading-desk/research',params={'symbol':'QQQ'}).json()
            self.assertEqual(call.call_count,1)
            self.assertEqual(first['provider_status']['retry_after'],2200)
            self.assertEqual(second['provider_status']['retry_after'],2200)
            self.assertEqual(second['verdict'],'WAIT')
    def test_retry_after_http_date_and_exponential_backoff(self):
        from urllib.error import HTTPError
        from trading_site import retry_delay
        from email.utils import formatdate
        e=HTTPError('url',429,'limited',{'Retry-After':formatdate(2800,usegmt=True)},None)
        self.assertEqual(retry_delay(e,1000,300),1800)
        with patch('trading_site.urlopen',side_effect=HTTPError('url',429,'limited',{},None)) as call:
            with patch('trading_site.time.time',return_value=1000):
                self.client.get('/api/trading-desk/research')
            with patch('trading_site.time.time',return_value=1301):
                d=self.client.get('/api/trading-desk/research').json()
            self.assertEqual(call.call_count,2)
            self.assertEqual(d['provider_status']['retry_after'],1901)
    def test_single_flight_blocks_concurrent_provider_requests(self):
        from trading_site import _slots
        _slots.acquire()
        try:
            with patch('trading_site.urlopen') as call:
                d=self.client.get('/api/trading-desk/research').json()
                call.assert_not_called()
                self.assertEqual(d['provider_status']['code'],'REQUEST_IN_PROGRESS')
        finally: _slots.release()
    def test_recovery_caches_valid_evidence_and_resets_backoff(self):
        import json
        from unittest.mock import MagicMock
        p,n=fixture();response=MagicMock()
        response.__enter__.return_value.read.return_value=json.dumps(p).encode()
        _provider_state['failures']=3
        with patch('trading_site.time.time',return_value=n),patch('trading_site.urlopen',return_value=response) as call:
            first=self.client.get('/api/trading-desk/research').json()
            second=self.client.get('/api/trading-desk/research').json()
            self.assertEqual(first['verdict'],'LONG_RESEARCH')
            self.assertTrue(second['provider_status']['cached'])
            self.assertEqual(call.call_count,1)
            self.assertEqual(_provider_state['failures'],0)
    def test_cached_evidence_never_refreshes_source_timestamp(self):
        p,n=fixture();_cache[('SPY','US')]=(n+300,p)
        with patch('trading_site.time.time',return_value=n+301),patch('trading_site.urlopen') as call:
            d=self.client.get('/api/trading-desk/research').json()
            self.assertEqual(d['verdict'],'WAIT')
            self.assertEqual(d['quote_time'],n-1)
            call.assert_not_called()

    def test_last_good_outage_snapshot_is_never_an_entry_even_with_recent_quote(self):
        p,n=fixture();_cache[('SPY','US')]=(n,p)
        with patch('trading_site.time.time',return_value=n+61),patch('trading_site.urlopen',side_effect=TimeoutError):
            response=self.client.get('/api/trading-desk/research');d=response.json()
        self.assertTrue(d['stale_cache']);self.assertEqual(d['verdict'],'WAIT');self.assertFalse(d['paper_eligible'])
        self.assertNotIn('scenario',d)
        self.assertTrue(d['bars']);self.assertEqual(d['quote_time'],n-1);self.assertEqual(d['fetched_at'],n)
        self.assertTrue(any(s['name']=='Provider availability' and s['status']=='blocked' for s in d['stages']))
        self.assertEqual(response.headers['retry-after'],'60');self.assertEqual(d['next_refresh_at'],n+121)
        self.assertEqual(_provider_state['stale_served'],1)

    def test_cooldown_and_singleflight_reuse_last_good_snapshot_without_fetch(self):
        from trading_site import _slots
        p,n=fixture();_cache[('SPY','US')]=(n,p)
        with patch('trading_site.time.time',return_value=n+61),patch('trading_site.urlopen') as call:
            _provider_state['retry_after']=n+100
            d=self.client.get('/api/trading-desk/research').json()
            self.assertTrue(d['stale_cache']);self.assertEqual(d['verdict'],'WAIT')
            _slots.acquire()
            try: concurrent=self.client.get('/api/trading-desk/research').json()
            finally: _slots.release()
            self.assertTrue(concurrent['stale_cache']);self.assertFalse(concurrent['paper_eligible'])
            self.assertEqual(concurrent['provider_status']['code'],'REQUEST_IN_PROGRESS')
            call.assert_not_called()
        self.assertEqual(_provider_state['cooldown_hits'],1);self.assertEqual(_provider_state['singleflight_hits'],1)

    def test_last_good_snapshot_expires_at_fifteen_minutes(self):
        from trading_site import STALE_TTL
        p,n=fixture();_cache[('SPY','US')]=(n,p)
        with patch('trading_site.time.time',return_value=n+STALE_TTL),patch('trading_site.urlopen',side_effect=TimeoutError):
            d=self.client.get('/api/trading-desk/research').json()
        self.assertFalse(d.get('stale_cache',False));self.assertEqual(d['bars'],[])
        self.assertNotIn('price',d);self.assertFalse(d['paper_eligible'])
        self.assertEqual(_provider_state['stale_served'],0)

    def test_gate_rechecks_cache_populated_by_a_just_completed_concurrent_call(self):
        from unittest.mock import Mock
        p,n=fixture();gate=Mock()
        def acquire(**kwargs):
            # Deterministic interleaving: first cache miss, other call completes, gate acquired.
            _cache[('SPY','US')]=(n,p)
            return True
        gate.acquire.side_effect=acquire
        with patch('trading_site._slots',gate),patch('trading_site.time.time',return_value=n),patch('trading_site.urlopen') as call:
            d=self.client.get('/api/trading-desk/research').json()
            call.assert_not_called()
        gate.release.assert_called_once();self.assertTrue(d['provider_status']['cached'])
        self.assertEqual(_provider_state['cache_rechecks'],1);self.assertEqual(_provider_state['cache_hits'],1)

    def test_cached_response_advertises_remaining_refresh_delay(self):
        p,n=fixture();_cache[('SPY','US')]=(n,p)
        with patch('trading_site.time.time',return_value=n+30),patch('trading_site.urlopen') as call:
            response=self.client.get('/api/trading-desk/research');d=response.json();call.assert_not_called()
        self.assertEqual(response.headers['retry-after'],'30');self.assertEqual(d['next_refresh_at'],n+60)
        self.assertEqual(d['provider_status']['retry_after'],d['next_refresh_at'])
        self.assertFalse(d['stale_cache']);self.assertEqual(d['fetched_at'],n)

    def test_empty_new_provider_history_does_not_erase_last_good_cache(self):
        from unittest.mock import MagicMock
        p,n=fixture();_cache[('SPY','US')]=(n,p);response=MagicMock()
        response.__enter__.return_value.read.return_value=b'{"chart":{"result":[]}}'
        with patch('trading_site.time.time',return_value=n+61),patch('trading_site.urlopen',return_value=response):
            d=self.client.get('/api/trading-desk/research').json()
        self.assertTrue(d['stale_cache']);self.assertEqual(d['provider_status']['code'],'INVALID_RESPONSE')
        self.assertIs(_cache[('SPY','US')][1],p)

    def test_options_route_missing_feed_and_invalid_symbol(self):
        import os
        with patch('secure_access.identity') as identity:
            identity.get.return_value={'email':'qa@example.invalid','full':True}
            with patch.dict(os.environ,{},clear=True),patch('trading_site.urlopen',side_effect=TimeoutError):
                response=self.client.get('/api/trading-desk/options');result=response.json()
            self.assertEqual(result['status'],'WAIT')
            self.assertIsNone(result['candidate']);self.assertFalse(result['execution_enabled'])
            self.assertIn('next_refresh_at',result);self.assertIn('retry-after',response.headers)
            self.assertEqual(self.client.get('/api/trading-desk/options?symbol=SPX').status_code,422)

    def test_options_route_rejects_anonymous_and_spoofed_email_before_any_provider_call(self):
        with patch('secure_access.identity') as identity,patch('trading_site.research') as underlying,patch('trading_options.option_research') as options:
            identity.get.return_value=None
            with patch.dict('os.environ',{'CELESYS_AUTH_ENFORCE':'false'}):
                for headers in ({},{'X-Celesys-Email':'allowed@example.invalid','Cookie':'__Host-celesys_session=forged'}):
                    response=self.client.get('/api/trading-desk/options?email=allowed@example.invalid',headers=headers)
                    self.assertEqual(response.status_code,401)
                    self.assertIn('Verified authorized sign-in',response.json()['detail'])
            underlying.assert_not_called();options.assert_not_called()

    def test_options_route_rejects_verified_non_full_account_before_any_provider_call(self):
        with patch('secure_access.identity') as identity,patch('trading_site.research') as underlying,patch('trading_options.option_research') as options:
            identity.get.return_value={'email':'qa@example.invalid','full':False,'trades':True}
            self.assertEqual(self.client.get('/api/trading-desk/options').status_code,401)
            underlying.assert_not_called();options.assert_not_called()

class FeedStatusTests(unittest.TestCase):
    def test_readiness_exposes_only_configuration_and_never_claims_live_connection(self):
        from trading_site import status
        with patch('private_options.ready',return_value=True),patch('secure_access.configured',return_value=False):
            d=status()
        self.assertTrue(d['options_accounts']['IN']['configured'])
        self.assertFalse(d['options_accounts']['IN']['connection_verified'])
        self.assertFalse(d['authentication']['configured'])
        self.assertFalse(d['live_latency_guaranteed'])
        self.assertNotIn('token',str(d).lower())
