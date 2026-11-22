import json
import os
import unittest
from copy import deepcopy
from datetime import datetime
from unittest.mock import patch
from urllib.error import HTTPError
import angel_options as a

ENV=dict(zip(a.ENV,['test-api','test-jwt','127.0.0.1','192.0.2.1','00:11:22:33:44:55']))

class AngelOptionsTests(unittest.TestCase):
 def setUp(self):
  a._master=None;a._master_at=0;a._retry_at=0;a._quote_next=0;a._cache.clear()
  a._nse_book=None;a._nse_book_at=0;a._ltp_cache.clear()
  self.now=datetime(2026,10,12,11,0,tzinfo=a.IST).timestamp()
  self.master=[dict(name='NIFTY',symbol='Nifty 50',token='99926000',instrumenttype='AMXIDX',exch_seg='NSE')]
  for token,side in [('101','CE'),('102','PE')]:
   self.master.append(dict(name='NIFTY',symbol='NIFTY13OCT2625000'+side,token=token,instrumenttype='OPTIDX',exch_seg='NFO',expiry='13OCT2026',strike='2500000.000000',lotsize='65'))
  self.index=dict(exchange='NSE',tradingSymbol='Nifty 50',symbolToken='99926000',ltp=25000,exchFeedTime='12-Oct-2026 10:59:59')
  self.quotes=[dict(exchange='NFO',tradingSymbol=x['symbol'],symbolToken=x['token'],ltp=100,
      exchFeedTime='12-Oct-2026 10:59:59',opnInterest=0,tradeVolume=500,
      depth={'buy':[{'price':99,'quantity':65}],'sell':[{'price':100,'quantity':130}]}) for x in self.master[1:]]
 def response(self,quotes):return {'status':True,'data':{'fetched':quotes,'unfetched':[]}}
 def call(self,master=None,quotes=None):
  with patch.dict(os.environ,ENV,clear=True),patch('angel_options.time.time',return_value=self.now),patch('angel_options.time.sleep'),patch('angel_options._request',side_effect=[self.master if master is None else master,self.response([self.index]),self.response(self.quotes if quotes is None else quotes)]) as request:
   result=a.chain('NIFTY');return result,request
 def test_instrument_book_is_parsed_outside_this_process(self):
  raw=json.dumps([
   dict(symbol='Nifty 50',token='1',instrumenttype='AMXIDX',exch_seg='NSE',name='NIFTY'),
   dict(symbol='Nifty Bank',token='2',instrumenttype='AMXIDX',exch_seg='NSE',name='BANKNIFTY'),
   dict(symbol='RELIANCE-EQ',token='2885',instrumenttype='EQ',exch_seg='NSE',name='RELIANCE'),
   dict(symbol='SKIP-EQ',token='4',instrumenttype='EQ',exch_seg='NSE',name='OTHER'),
  ]).encode()
  book=a._book_from_master_bytes(raw)
  self.assertEqual(book['NIFTY']['token'],'1')
  self.assertEqual(book['BANKNIFTY']['symbol'],'Nifty Bank')
  self.assertEqual(book['RELIANCE'],{'token':'2885','symbol':'RELIANCE-EQ'})
  self.assertNotIn('SKIP',book)
  with self.assertRaises(ValueError):
   a._book_from_master_bytes(b'{"not":"a list"}')

 def test_no_configuration_means_no_network(self):
  with patch.dict(os.environ,{},clear=True),patch('angel_options._request') as request:
   self.assertFalse(a.configured());self.assertEqual(a.chain('NIFTY')['status'],'UNAVAILABLE');request.assert_not_called()
 def test_configuration_rejects_header_injection_and_invalid_network_identity(self):
  for key,value in [(a.ENV[1],'token\nheader'),(a.ENV[2],'not-ip'),(a.ENV[4],'no-mac')]:
   env=dict(ENV);env[key]=value
   with patch.dict(os.environ,env,clear=True):self.assertFalse(a.configured())
 def test_only_supported_indices(self):
  with patch.dict(os.environ,ENV,clear=True),patch('angel_options._request') as request:
   self.assertEqual(a.chain('SENSEX')['status'],'UNAVAILABLE');request.assert_not_called()
 def test_master_scales_nfo_paise_and_uses_actual_lot(self):
  index,contracts=a.instruments(self.master,'NIFTY',datetime.fromtimestamp(self.now,a.IST).date())
  self.assertEqual(index['token'],'99926000');self.assertEqual(len(contracts),2)
  self.assertEqual(contracts[0]['strike'],25000);self.assertEqual(contracts[0]['lot_size'],65)
 def test_master_rejects_wrong_scale_symbol_and_instrument_type(self):
  master=deepcopy(self.master);master[1]['strike']='25000';master[2]['instrumenttype']='OPTSTK'
  self.assertEqual(a.instruments(master,'NIFTY',datetime.fromtimestamp(self.now,a.IST).date())[1],[])
 def test_duplicate_master_identity_blocks(self):
  with self.assertRaises(RuntimeError):a.instruments(self.master+[self.master[1]],'NIFTY',datetime.fromtimestamp(self.now,a.IST).date())
 def test_snapshot_has_real_depth_and_explicit_missing_greeks(self):
  result,request=self.call();self.assertEqual(result['status'],'SNAPSHOT')
  self.assertEqual(request.call_count,3);self.assertEqual(result['freshness'],'RECENT_FEED_SNAPSHOT')
  leg=result['rows'][0]['call'];self.assertEqual(leg['bid'],99);self.assertEqual(leg['ask'],100)
  self.assertEqual(leg['oi'],0);self.assertEqual(leg['lot_size'],65)
  for field in ('delta','iv_pct','bid_time','ask_time','greeks_time','oi_change'):self.assertIsNone(leg[field])
  self.assertEqual(leg['feed_time'],self.now-1);self.assertFalse(result['execution_enabled'])
 def test_ist_parsing_rejects_future_or_malformed_time(self):
  for value in ('12-Oct-2026 11:00:01','garbage',None):self.assertIsNone(a.feed_time(value,self.now))
  self.assertEqual(a.feed_time('12-Oct-2026 10:59:59',self.now),self.now-1)
 def test_wrong_quote_identity_blocks_entire_batch(self):
  for field,value in [('symbolToken','999'),('tradingSymbol','BANKNIFTY13OCT2625000CE'),('exchange','BFO')]:
   self.setUp();quotes=deepcopy(self.quotes);quotes[0][field]=value
   result,_=self.call(quotes=quotes);self.assertEqual(result['status'],'UNAVAILABLE')
 def test_duplicate_quote_blocks_batch(self):
  result,_=self.call(quotes=[self.quotes[0],self.quotes[0]]);self.assertEqual(result['status'],'UNAVAILABLE')
 def test_missing_leg_is_explicit_partial_coverage(self):
  result,_=self.call(quotes=[self.quotes[0]])
  self.assertEqual(result['status'],'SNAPSHOT');self.assertIsNone(result['rows'][0]['put'])
  self.assertEqual(result['coverage']['returned_contracts'],1)
 def test_stale_feed_is_not_marked_recent(self):
  quotes=deepcopy(self.quotes);quotes[0]['exchFeedTime']='12-Oct-2026 10:50:00'
  result,_=self.call(quotes=quotes);self.assertEqual(result['freshness'],'UNVERIFIED_OR_STALE')
 def test_crossed_depth_does_not_create_quote(self):
  quotes=deepcopy(self.quotes);quotes[0]['depth']['buy'][0]['price']=110
  result,_=self.call(quotes=quotes);self.assertIsNone(result['rows'][0]['call']['bid'])
 def test_cache_preserves_source_timestamp_and_no_second_provider_call(self):
  with patch.dict(os.environ,ENV,clear=True),patch('angel_options.time.time',return_value=self.now),patch('angel_options.time.sleep'),patch('angel_options._request',side_effect=[self.master,self.response([self.index]),self.response(self.quotes)]) as request:
   first=a.chain('NIFTY');second=a.chain('NIFTY');self.assertEqual(request.call_count,3)
   self.assertEqual(first['fetched_at'],second['fetched_at']);self.assertEqual(first['rows'],second['rows'])
   old=a._snapshot(first,self.now+301);self.assertEqual(old['freshness'],'UNVERIFIED_OR_STALE')
 def test_failure_redacted_and_cooldown_honors_retry_after(self):
  error=HTTPError(a.QUOTE_URL,429,'SECRET',{'Retry-After':'900'},None)
  with patch.dict(os.environ,ENV,clear=True),patch('angel_options.time.time',return_value=self.now),patch('angel_options._request',side_effect=error) as request:
   result=a.chain('NIFTY');self.assertNotIn('SECRET',str(result));self.assertEqual(result['retry_after'],self.now+900)
   a.chain('NIFTY');self.assertEqual(request.call_count,1)
 def test_concurrent_request_does_not_duplicate_network(self):
  with patch.dict(os.environ,ENV,clear=True),patch('angel_options._request') as request:
   a._lock.acquire()
   try:self.assertEqual(a.chain('NIFTY')['status'],'UNAVAILABLE');request.assert_not_called()
   finally:a._lock.release()
 def test_batch_and_url_bounds(self):
  with self.assertRaises(ValueError):a._quotes('NFO',[str(x) for x in range(51)])
  with self.assertRaises(ValueError):a._request('https://attacker.invalid')
  with self.assertRaises(ValueError):a.NoRedirect().redirect_request(None,None,302,'',{},'https://attacker.invalid')
 def test_credential_headers_never_sent_to_master(self):
  with patch.dict(os.environ,ENV,clear=True),patch('angel_session.request_bytes',return_value=b'[]') as request,patch('angel_options._index_master_from_bytes',return_value=[]):
   a._request(a.MASTER_URL)
   headers=request.call_args.kwargs['headers']
   self.assertNotIn('Authorization',headers);self.assertNotIn('X-PrivateKey',headers)
 def test_chain_stops_when_the_decision_budget_elapsed(self):
  import web_background
  web_background.start_deadline(-1)
  try:
   with patch.dict(os.environ,ENV,clear=True),patch('angel_options._request') as request:
    result=a.chain('NIFTY')
   request.assert_not_called()
   self.assertIn('budget', result['message'])
  finally:
   web_background._deadline=None
 def test_index_master_parse_keeps_only_index_rows(self):
  raw=json.dumps([
   dict(name='NIFTY',symbol='Nifty 50',token='1',instrumenttype='AMXIDX',exch_seg='NSE'),
   dict(name='NIFTY',symbol='NIFTY13OCT2625000CE',token='2',instrumenttype='OPTIDX',exch_seg='NFO'),
   dict(name='RELIANCE',symbol='RELIANCE-EQ',token='3',instrumenttype='',exch_seg='NSE'),
  ]).encode()
  kept=a._index_master_from_bytes(raw)
  self.assertEqual([row['token'] for row in kept],['1','2'])
 def test_master_cache_excludes_unrelated_markets(self):
  master=self.master+[dict(name='RELIANCE',token='1',instrumenttype='OPTSTK',exch_seg='NFO')]
  result,_=self.call(master=master);self.assertEqual(result['status'],'SNAPSHOT')
  self.assertEqual(len(a._master),3)
 def test_numeric_overflow_is_not_a_market_value(self):
  for value in ('1e9999','NaN','Infinity',True,-1):self.assertIsNone(a._num(value))
 def test_window_is_bounded_to_50_tokens_and_selected_near_spot(self):
  master=[self.master[0]]
  for index,strike in enumerate(range(23000,27001,100)):
   for offset,side in enumerate(('CE','PE')):
    row=deepcopy(self.master[1]);row.update(token=str(1000+index*2+offset),symbol=f'NIFTY13OCT26{strike}{side}',strike=str(strike*100))
    master.append(row)
  def respond(url,payload=None):
   if url==a.MASTER_URL:return master
   if 'NSE' in payload['exchangeTokens']:return self.response([self.index])
   tokens=payload['exchangeTokens']['NFO'];self.assertEqual(len(tokens),50)
   instruments={row['token']:row for row in master}
   return self.response([dict(self.quotes[0],symbolToken=t,tradingSymbol=instruments[t]['symbol']) for t in tokens])
  with patch.dict(os.environ,ENV,clear=True),patch('angel_options.time.time',return_value=self.now),patch('angel_options.time.sleep'),patch('angel_options._request',side_effect=respond):
   result=a.chain('NIFTY');self.assertEqual(result['status'],'SNAPSHOT')
   self.assertEqual(len(result['rows']),25);self.assertEqual(result['coverage']['available_paired_strikes'],41)
   self.assertEqual(result['rows'][0]['strike'],23800);self.assertEqual(result['rows'][-1]['strike'],26200)
 def _book(self):
  return [
   dict(token='99926000',symbol='Nifty 50',name='NIFTY',instrumenttype='AMXIDX',exch_seg='NSE'),
   dict(token='99926009',symbol='Nifty Bank',name='BANKNIFTY',instrumenttype='AMXIDX',exch_seg='NSE'),
   dict(token='99926017',symbol='India VIX',name='INDIA VIX',instrumenttype='AMXIDX',exch_seg='NSE'),
   dict(token='99926004',symbol='Nifty 500',name='NIFTY 500',instrumenttype='AMXIDX',exch_seg='NSE'),
   dict(token='2885',symbol='RELIANCE-EQ',name='RELIANCE',instrumenttype='',exch_seg='NSE'),
   dict(token='999',symbol='RELIANCE-BE',name='RELIANCE',instrumenttype='',exch_seg='NSE'),
  ]
 def test_nse_quotes_use_ohlc_and_cache_for_60s(self):
  calls=[]
  def respond(url,payload=None):
   calls.append((url,payload))
   if url==a.MASTER_URL:return self._book()
   self.assertEqual(payload['mode'],'OHLC')
   self.assertEqual(payload['exchangeTokens']['NSE'],['2885','99926000'])
   return self.response([
    dict(exchange='NSE',tradingSymbol='RELIANCE-EQ',symbolToken='2885',ltp=1377.5,open=1370,high=1380,low=1368,close=1370),
    dict(exchange='NSE',tradingSymbol='Nifty 50',symbolToken='99926000',ltp=24000,close=23900),
   ])
  with patch.dict(os.environ,ENV,clear=True),patch('angel_options.time.time',return_value=1_000),patch('angel_options.time.sleep'),patch('angel_options._request',side_effect=respond):
   first=a.nse_quotes(['RELIANCE.NS','NIFTY'])
   second=a.nse_quotes(['reliance'])
  self.assertAlmostEqual(first['RELIANCE']['price'],1377.5)
  self.assertAlmostEqual(first['RELIANCE']['change'],7.5)
  self.assertEqual(first['RELIANCE']['quality'],'LIVE')
  self.assertEqual(first['RELIANCE']['source'],'angel_one')
  self.assertEqual(first['NIFTY']['trading_symbol'],'Nifty 50')
  self.assertEqual(second['RELIANCE']['price'],1377.5)
  self.assertEqual(sum(url==a.QUOTE_URL for url,_ in calls),1)
  self.assertNotIn('Nifty 500',{row['trading_symbol'] for row in first.values()})
 def test_nse_quotes_without_configuration_do_not_call_the_network(self):
  with patch.dict(os.environ,{},clear=True),patch('angel_options._request') as request:
   self.assertEqual(a.nse_quotes(['RELIANCE','NIFTY']),{})
   request.assert_not_called()
 def test_nse_quote_failure_logs_class_without_the_jwt(self):
  def boom(url,payload=None):
   raise ValueError('rejected test-jwt')
  with patch.dict(os.environ,ENV,clear=True),patch('angel_options._request',side_effect=boom),self.assertLogs('angel_options',level='WARNING') as logs:
   self.assertEqual(a.nse_quotes(['NIFTY']),{})
  text='\n'.join(logs.output)
  self.assertIn('ValueError',text)
  self.assertNotIn('test-jwt',text)
 def test_bse_symbol_is_not_an_nse_quote(self):
  with patch.dict(os.environ,ENV,clear=True),patch('angel_options._request') as request:
   self.assertEqual(a.nse_quotes(['SENSEX.BO']),{})
   request.assert_not_called()
 def test_index_snapshot_maps_the_legacy_chain_shape(self):
  snap=dict(status='SNAPSHOT',spot=25000,expiry='2026-11-26',message='bounded',rows=[
    dict(strike=25000,call=dict(bid=10,ask=11,last=10.5,oi=100,volume=5,iv_pct=None,lot_size=65),
         put=dict(bid=9,ask=10,last=9.5,oi=80,volume=4,iv_pct=None,lot_size=65))])
  with patch.dict(os.environ,ENV,clear=True),patch('angel_options.chain',return_value=snap) as chain:
   out=a.index_snapshot('NIFTY')
   self.assertIsNone(a.index_snapshot('RELIANCE'))
   self.assertIsNone(a.index_snapshot('SENSEX'))
  chain.assert_called_once_with('NIFTY')
  self.assertEqual(out['_chain_source'],'angel_one')
  self.assertEqual(out['chain_near_atm'][0]['ce_oi'],100)
  self.assertEqual(out['chain_near_atm'][0]['ce_volume'],5)
  self.assertEqual(out['pcr'],0.8)
  self.assertEqual(out['max_pain'],25000)
  self.assertEqual(out['lot_size'],65)
