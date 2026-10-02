import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from trading_site import attach_trading_desk,market_symbol,_cache,_failures,_provider_state
from test_trading_research import fixture

class RouteTests(unittest.TestCase):
    def setUp(self):
        self.app=FastAPI();attach_trading_desk(self.app);self.client=TestClient(self.app);_cache.clear();_failures.clear();_provider_state.update(retry_after=0,checked_at=None,code="NOT_CHECKED",failures=0,requests=0)
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

    def test_options_route_missing_feed_and_invalid_symbol(self):
        import os
        with patch.dict(os.environ,{},clear=True), patch('trading_site.urlopen',side_effect=TimeoutError):
            result=self.client.get('/api/trading-desk/options').json()
        self.assertEqual(result['status'],'WAIT')
        self.assertIsNone(result['candidate'])
        self.assertFalse(result['execution_enabled'])
        self.assertEqual(self.client.get('/api/trading-desk/options?symbol=SPX').status_code,422)
