import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from trading_site import attach_trading_desk,market_symbol,_cache,_failures
from test_trading_research import fixture

class RouteTests(unittest.TestCase):
    def setUp(self):
        self.app=FastAPI();attach_trading_desk(self.app);self.client=TestClient(self.app);_cache.clear();_failures.clear()
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
if __name__=='__main__':unittest.main()
