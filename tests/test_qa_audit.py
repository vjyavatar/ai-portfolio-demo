import unittest
from qa.audit import validate_brief,validate_chain,validate_document,Document
class AuditTests(unittest.TestCase):
 def test_empty_success_is_failure(self):
  self.assertEqual(validate_brief(dict(assessment='x',evidence=[],counterargument='x',missing_data=[],next_check='x'))[0],'FAIL')
 def test_unavailable_chain_never_passes(self):
  self.assertEqual(validate_chain({'status':'UNAVAILABLE','rows':[]})[0],'UNVERIFIED')
 def test_fake_snapshot_fails(self):
  self.assertEqual(validate_chain({'status':'SNAPSHOT','rows':[]})[0],'FAIL')
 def test_duplicate_strikes_fail(self):
  self.assertEqual(validate_chain({'status':'SNAPSHOT','expiry':'2099-01-01','rows':[{'strike':100},{'strike':100}]})[0],'FAIL')
 def test_sourced_evidence_is_structurally_valid(self):
  self.assertEqual(validate_brief(dict(assessment='x',evidence=[{'source':'fixture','value':1}],counterargument='x',missing_data=[],next_check='x'))[0],'PASS')

 def test_protected_document_denial_is_not_a_page_failure_or_functional_pass(self):
  for code in (401,403):
   self.assertEqual(validate_document('/today',code,'text/html',b'',Document())[0],'UNVERIFIED')
 def test_public_document_denial_still_fails(self):
  self.assertEqual(validate_document('/',403,'text/html',b'',Document())[0],'FAIL')
 def test_protected_document_server_error_still_fails(self):
  self.assertEqual(validate_document('/today',500,'text/html',b'',Document())[0],'FAIL')

 def test_outage_snapshot_never_passes_as_live(self):
  from qa.audit import validate_trading
  data=dict(symbol='SPY',region='US',currency='USD',source='Yahoo Finance chart',verdict='WAIT',stale_cache=True)
  self.assertEqual(validate_trading(data,'SPY','US')[0],'UNVERIFIED')
  for extra in ({'verdict':'LONG_RESEARCH'},{'paper_eligible':True},{'scenario':{'entry':10}}):
   self.assertEqual(validate_trading(dict(data,**extra),'SPY','US')[0],'FAIL')

 def test_live_probes_include_all_indian_indices(self):
  from qa.audit import trading_probes
  paths=[p for p,_ in trading_probes(['IN'])]
  for symbol in ('NIFTY','BANKNIFTY','SENSEX','RELIANCE'):
   self.assertIn('/api/trading-desk/research?symbol='+symbol+'&region=IN',paths)
 def test_live_audit_requires_provenance_and_does_not_confuse_closed_with_unverified(self):
  from qa.audit import validate_trading
  d=dict(symbol='NIFTY',region='IN',currency='INR',source='angel',verdict='WAIT',market_status='OPEN',session_start=1000,session_end=9000,quote_time=2000,bar_close_time=1990,price=100,quote_source='angel',candle_source='angel',price_kind='SOURCE_QUOTE',provider_status={'code':'RESPONSE_RECEIVED'})
  self.assertEqual(validate_trading(d,'NIFTY','IN',now=2010)[0],'PASS')
  self.assertEqual(validate_trading(dict(d,quote_source='tradingview'),'NIFTY','IN',now=2010)[0],'UNVERIFIED')
  self.assertEqual(validate_trading(dict(d,market_status='CLOSED_OR_UNVERIFIED'),'NIFTY','IN',now=2010)[0],'UNVERIFIED')
  self.assertEqual(validate_trading(dict(d,market_status='CLOSED_OR_UNVERIFIED'),'NIFTY','IN',now=9010)[0],'PASS')
