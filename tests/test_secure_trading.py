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

 def test_stock_intelligence_does_not_randomize_historical_bars(self):
  tree=ast.parse(Path('api.py').read_text());n=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='_run_stock_intel')
  self.assertNotIn('random.uniform',ast.get_source_segment(Path('api.py').read_text(),n))

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
