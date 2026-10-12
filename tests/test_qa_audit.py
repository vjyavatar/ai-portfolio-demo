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
