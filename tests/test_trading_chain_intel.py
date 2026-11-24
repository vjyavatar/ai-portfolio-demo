"""Fail-closed India option evidence coverage tests."""
import unittest
from trading_chain_intel import evaluate

class IndiaEvidenceTests(unittest.TestCase):
    def test_no_chain_does_not_invent_candidate(self):
        r=evaluate({'verdict':'LONG_RESEARCH','market_status':'OPEN'}, {'status':'UNAVAILABLE','rows':[]})
        self.assertEqual(r['status'],'WAIT')
        self.assertFalse(r['eligible'])
        self.assertIsNone(r['chain']['pcr_oi'])
        self.assertEqual(next(x for x in r['checks'] if x['label']=='Gamma / gamma flip')['state'],'UNAVAILABLE')
    def test_oi_and_walls_are_context_only(self):
        c={'status':'SNAPSHOT','expiry':'2026-11-26','rows':[
          {'strike':26000,'call':{'oi':200,'oi_change':20,'bid':50,'ask':51,'spread_pct':1.98},'put':{'oi':100,'oi_change':-10}},
          {'strike':26100,'call':{'oi':50,'oi_change':5},'put':{'oi':400,'oi_change':25}},
        ]}
        r=evaluate({'verdict':'LONG_RESEARCH','market_status':'OPEN'},c)
        self.assertFalse(r['eligible'])
        self.assertEqual(r['chain']['pcr_oi'],2.0)
        self.assertEqual(r['chain']['highest_call_oi_strike'],26000)
        self.assertEqual(r['chain']['highest_put_oi_strike'],26100)
        self.assertEqual(r['chain']['total_call_oi_change'],25)
        self.assertEqual(r['chain']['total_put_oi_change'],15)
        self.assertEqual(next(x for x in r['checks'] if x['label']=='Historical calibration')['state'],'UNAVAILABLE')
    def test_missing_or_invalid_expiry_fails_closed(self):
        r=evaluate({'verdict':'BEARISH_RESEARCH','market_status':'OPEN'}, {'status':'SNAPSHOT','expiry':'broken','rows':[{'strike':200,'call':{'oi':2}}]})
        self.assertEqual(next(x for x in r['checks'] if x['label']=='Strike and expiry')['state'],'UNAVAILABLE')
        self.assertEqual(r['status'],'WAIT')

if __name__=='__main__':unittest.main()
