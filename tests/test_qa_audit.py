import unittest
from qa.audit import validate_brief,validate_chain
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
