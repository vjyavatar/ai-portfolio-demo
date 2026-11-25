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

class ContractReviewTests(unittest.TestCase):
    def fixture(self):
        from datetime import datetime, timezone
        now=datetime(2026,11,25,7,0,tzinfo=timezone.utc).timestamp()
        report={'symbol':'NIFTY','region':'IN','market_status':'OPEN','verdict':'LONG_RESEARCH','quote_time':now-5,'bar_close_time':now-30}
        leg={'contract':'NIFTY26NOV2626000CE','bid':100,'ask':101,'bid_size':100,'ask_size':100,'lot_size':65,'oi':5000,'volume':2000,'feed_time':now-5,'feed_time_kind':'EXCHANGE_FEED_SNAPSHOT_IST_NOT_SIDE_SPECIFIC'}
        chain={'symbol':'NIFTY','region':'IN','source':'Angel One SmartAPI','status':'SNAPSHOT','expiry':'2026-11-26','spot':26005,'spot_feed_time':now-6,'fetched_at':now-2,'rows':[{'strike':26000,'call':leg}]}
        return now,report,chain,leg
    def test_recent_snapshot_review_is_not_buy(self):
        now,r,c,leg=self.fixture()
        result=evaluate(r,c,now)
        self.assertEqual(result['contract_review']['strike'],26000)
        self.assertEqual(result['contract_review']['premium_per_lot'],6565)
        self.assertEqual(result['status'],'WAIT')
        self.assertFalse(result['eligible'])
    def test_reject_stale_future_wide_missing_and_wrong_side(self):
        for change in ('stale','future','wide','missing','side','closed','cache','identity'):
            with self.subTest(change=change):
                now,r,c,leg=self.fixture()
                if change=='stale':leg['feed_time']=now-61
                if change=='future':leg['feed_time']=now+1
                if change=='wide':leg['ask']=120
                if change=='missing':leg['ask_size']=None
                if change=='side':r['verdict']='BEARISH_RESEARCH'
                if change=='closed':r['market_status']='CLOSED_OR_UNVERIFIED'
                if change=='cache':r['stale_cache']=True
                if change=='identity':c['symbol']='BANKNIFTY'
                self.assertIsNone(evaluate(r,c,now)['contract_review'])
if __name__=='__main__':unittest.main()
