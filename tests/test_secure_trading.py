import ast,json,os,time,unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
import secure_access as auth
from private_options import dhan_rows,chain
ENV={'CELESYS_AUTH_SECRET':'x'*48,'CELESYS_SMTP_HOST':'smtp.example.invalid','CELESYS_SMTP_USER':'qa','CELESYS_SMTP_PASSWORD':'test','CELESYS_SMTP_FROM':'test@example.invalid','CELESYS_AUTH_ENFORCE':'true','CELESYS_SITE_ORIGIN':'https://testserver'}
class SecurityTests(unittest.TestCase):
 def setUp(self):
  auth._codes.clear();auth._sessions.clear();auth._rates.clear();self.env=patch.dict(os.environ,ENV,clear=True);self.env.start()
  app=FastAPI()
  @app.get('/private')
  def private():return {'ok':True}
  auth.attach_access(app,lambda e:{'full':e=='member@example.org','trades':e=='member@example.org','dream':False},{'/private':'trades'})
  self.client=TestClient(app,base_url='https://testserver');self.headers={'Origin':'https://testserver'}
 def tearDown(self):self.client.close();self.env.stop()
 def login(self):
  with patch('secure_access.send_code') as send:
   r=self.client.post('/api/access/start',json={'email':'member@example.org'},headers=self.headers);self.assertEqual(r.status_code,200);code=send.call_args.args[1]
  return self.client.post('/api/access/confirm',json={'email':'member@example.org','code':code},headers=self.headers),code
 def test_unknown_email_and_supplied_header_do_not_unlock_enforced_scan(self):
  self.assertEqual(self.client.get('/api/watchlist/research',headers={'X-Celesys-Email':'member@example.org'}).status_code,403)
  self.assertEqual(self.client.get('/private?email=member@example.org').status_code,403)
 def test_origin_rejected(self):self.assertEqual(self.client.post('/api/access/start',json={'email':'member@example.org'},headers={'Origin':'https://evil.invalid'}).status_code,403)
 def test_login_cookie_and_logout_revocation(self):
  r,_=self.login();self.assertEqual(r.status_code,200);cookie=r.headers['set-cookie'];self.assertIn('HttpOnly',cookie);self.assertIn('Secure',cookie);self.assertIn('SameSite=strict',cookie)
  self.assertEqual(self.client.get('/private').status_code,200)
  self.client.post('/api/access/logout',headers=self.headers)
  self.assertEqual(self.client.get('/private').status_code,403)
 def test_otp_single_use(self):
  _,code=self.login();r=self.client.post('/api/access/confirm',json={'email':'member@example.org','code':code},headers=self.headers);self.assertEqual(r.status_code,401)
 def test_wrong_codes_lock_challenge(self):
  with patch('secure_access.send_code') as send:
   self.client.post('/api/access/start',json={'email':'member@example.org'},headers=self.headers);code=send.call_args.args[1]
  wrong='0'*8 if code!='0'*8 else '1'*8
  for _ in range(5):self.assertEqual(self.client.post('/api/access/confirm',json={'email':'member@example.org','code':wrong},headers=self.headers).status_code,401)
  self.assertEqual(self.client.post('/api/access/confirm',json={'email':'member@example.org','code':code},headers=self.headers).status_code,401)
 def test_tampered_cookie_rejected(self):
  self.login();self.client.cookies.clear();self.client.cookies.set(auth.COOKIE,'fake.bad');self.assertEqual(self.client.get('/private').status_code,403)
 def test_oversized_body_rejected(self):self.assertEqual(self.client.post('/api/access/start',content='x'*3000,headers=self.headers).status_code,413)
 def test_feed_requires_verified_account(self):
  with self.assertRaises(Exception) as e:chain('NIFTY','IN')
  self.assertEqual(e.exception.status_code,401)
 def test_no_session_inheritance_in_compatibility_mode(self):
  tree=ast.parse(Path('api.py').read_text());n=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='check_premium_gate')
  scope={'has_tier':lambda email,tier:email=='member@example.org','_premium_sessions':{'member@example.org':{'dream':True,'ts':time.time()}}}
  with patch.dict(os.environ,{'CELESYS_AUTH_ENFORCE':'false'}):
   exec(compile(ast.Module(body=[n],type_ignores=[]),'gate','exec'),scope)
   self.assertEqual(scope['check_premium_gate']('stranger@example.org','dream'),(False,'stranger@example.org'))
 def test_dhan_zero_and_missing_preserved_without_invented_time(self):
  rows,spot=dhan_rows({'status':'success','data':{'last_price':100,'oc':{'100':{'ce':{'security_id':1,'top_bid_price':2,'top_ask_price':3,'oi':0,'previous_oi':2,'greeks':{'delta':.5}}}}}})
  self.assertEqual(rows[0]['call']['oi'],0);self.assertEqual(rows[0]['call']['oi_change'],-2);self.assertIsNone(rows[0]['call']['bid_time']);self.assertIsNone(rows[0]['put']);self.assertEqual(spot,100)
 def test_algo_never_manufactures_price_history(self):
  tree=ast.parse(Path('api.py').read_text());n=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='_algo_signal_impl')
  self.assertNotIn('_prices_syn',ast.get_source_segment(Path('api.py').read_text(),n))

 def test_algo_rejects_price_only_nse_points_and_fabricated_volumes(self):
  source=Path('api.py').read_text();tree=ast.parse(source)
  function=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='_algo_signal_impl')
  segment=ast.get_source_segment(source,function)
  # These endpoints supplied price points or date-less index rows, not validated OHLCV.
  for endpoint in ('chart-databyindex','indicesHistory','gpiData'):
   self.assertNotIn(endpoint,segment)
  history_assignments=[]
  for node in ast.walk(function):
   if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='daily' for t in node.targets):
    self.assertFalse(any(isinstance(c,ast.Call) and isinstance(c.func,ast.Attribute) and c.func.attr=='DataFrame' for c in ast.walk(node.value)), 'Daily history must not be reconstructed from substitute OHLCV fields')
    if isinstance(node.value,ast.Await):history_assignments.append(node.value)
  self.assertEqual(len(history_assignments),2, 'Both India and US must retain their genuine-history provider path')
  for assignment in history_assignments:
   calls=[n for n in ast.walk(assignment) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='history']
   self.assertEqual(len(calls),1)
   self.assertEqual({k.arg:ast.literal_eval(k.value) for k in calls[0].keywords},{'period':'1y','interval':'1d'})
  self.assertIn('Genuine historical data is unavailable',segment)

 def test_stock_intelligence_does_not_randomize_historical_bars(self):
  tree=ast.parse(Path('api.py').read_text());n=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='_run_stock_intel')
  self.assertNotIn('random.uniform',ast.get_source_segment(Path('api.py').read_text(),n))

 def legacy_guard_scope(self):
  import asyncio
  tree=ast.parse(Path('api.py').read_text());scope={'asyncio':asyncio,'_algo_cache':{},'_algo_cache_ts':{}}
  for name in ('_legacy_algo_research_guard','algo_signal_safe'):
   node=next(n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name)
   node.decorator_list=[];exec(compile(ast.Module(body=[node],type_ignores=[]),'legacy-guard','exec'),scope)
  return scope

 def test_legacy_guard_preserves_research_and_is_idempotent(self):
  guard=self.legacy_guard_scope()['_legacy_algo_research_guard']
  raw={'success':True,'signal':'STRONG BUY','confidence':'HIGH','timestamp':'10:30 AM IST',
       'live_data_verified':True,'trade':{'tradeable':True,'entry':100},'priceHistory':[98,99,100],
       'engines':{'decision':'BUY','decisionReason':'Weighted factors','finalScore':82},
       'plans':[{'tradable':True,'entry':2.5}]}
  out=guard(raw)
  self.assertEqual(out['research_signal'],'STRONG BUY');self.assertEqual(out['research_confidence'],'HIGH')
  self.assertEqual(out['signal'],'HOLD / WAIT');self.assertEqual(out['confidence'],'UNVERIFIED')
  self.assertFalse(out['trade']['tradeable']);self.assertFalse(out['plans'][0]['tradable']);self.assertFalse(out['live_data_verified'])
  self.assertEqual(out['engines']['research_decision'],'BUY');self.assertEqual(out['engines']['decision'],'WAIT')
  self.assertEqual(out['engines']['finalScore'],82);self.assertEqual(out['trade']['entry'],100)
  self.assertEqual(out['priceHistory'],raw['priceHistory']);self.assertNotIn('quote_time',out)
  self.assertEqual(out['data_mode'],'HISTORICAL_RESEARCH_ONLY')
  self.assertEqual(out['timestamp_kind'],'COMPUTATION_TIME_NOT_QUOTE_TIME')
  self.assertEqual(guard(out),out);self.assertTrue(raw['trade']['tradeable']);self.assertEqual(raw['signal'],'STRONG BUY')

 def test_legacy_wrapper_guards_fresh_and_preexisting_cached_results(self):
  import asyncio
  from datetime import datetime
  from unittest.mock import AsyncMock
  scope=self.legacy_guard_scope();raw={'success':True,'signal':'BUY','confidence':'HIGH','trade':{'tradeable':True}}
  upstream=AsyncMock(return_value=raw);scope['_algo_signal_impl']=upstream
  fresh=asyncio.run(scope['algo_signal_safe']('SPY','US'))
  self.assertFalse(fresh['trade']['tradeable']);self.assertEqual(fresh['research_signal'],'BUY')
  scope['_algo_cache']['SPY_US']=raw;scope['_algo_cache_ts']['SPY_US']=datetime.utcnow()
  cached=asyncio.run(scope['algo_signal_safe']('SPY','US'))
  self.assertEqual(cached,fresh);self.assertEqual(upstream.await_count,1)
  self.assertTrue(raw['trade']['tradeable'])

 def test_legacy_guard_does_not_turn_provider_failures_into_research(self):
  guard=self.legacy_guard_scope()['_legacy_algo_research_guard'];failure={'success':False,'error':'History unavailable'}
  self.assertEqual(guard(failure),failure);self.assertFalse(guard(None)['success'])

 def test_actual_global_handlers_preserve_denials_and_hide_internal_errors(self):
  from fastapi import Request,HTTPException
  from fastapi.responses import JSONResponse
  tree=ast.parse(Path('api.py').read_text());scope={'Request':Request,'HTTPException':HTTPException,'JSONResponse':JSONResponse}
  for name in ['http_exception_handler','global_exception_handler']:
   n=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name==name);n.decorator_list=[]
   exec(compile(ast.Module(body=[n],type_ignores=[]),'handlers','exec'),scope)
  import asyncio
  request=Request({'type':'http','method':'GET','path':'/private','headers':[],'query_string':b''})
  denied=asyncio.run(scope['http_exception_handler'](request,HTTPException(403,'Denied')))
  self.assertEqual(denied.status_code,403)
  failed=asyncio.run(scope['global_exception_handler'](request,Exception('SECRET_TOKEN')))
  self.assertEqual(failed.status_code,500);self.assertNotIn(b'SECRET_TOKEN',failed.body)
