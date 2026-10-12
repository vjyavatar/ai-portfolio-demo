import ast
import asyncio
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
import existing_engines as ee
import research_agents as ra
from discovery_site import attach_discovery

class ExistingEngineTests(unittest.TestCase):
    def tearDown(self):
        ee.configure()
        ra.configure_dashboard(None)

    def test_stock_preserves_existing_verdict_and_invalidation(self):
        b=ra.stock_brief({'success':True,'decision':{'verdict':'INSUFFICIENT_DATA','summary_one_liner':'Price missing.',
            'quality_score':91,'invalidation_signals':['ROIC falls below 10%.']},'summary':{'price':None},
            'warnings':['Missing market cap.'],'analysis':{'fcf_quality':{'verdict':'STRONG'}},
            'cagrs':{'revenue_3y_cagr_pct':12}},'AAPL','US')
        self.assertIn('INSUFFICIENT DATA',b['assessment'])
        self.assertIn('ROIC falls',b['counterargument'])
        self.assertIn('Missing market cap.',b['missing_data'])
        self.assertTrue(any(e['value']==91 for e in b['evidence']))
        self.assertTrue(any(e['value']=='STRONG' for e in b['evidence']))

    def test_trading_preserves_engine_and_does_not_invent_quote_time(self):
        b=ra.existing_trading_brief({'success':True,'price':100,'signal':'WAIT','timestamp':'12:00 UTC',
            'explanation':{'what':'Sideways','wrong':'Breakdown risk'},'confidence':{'score':60},
            'tradePath':{'sl':95},'marketState':{'state':'RANGE'}},'SPY','US')
        self.assertEqual(b['assessment'],'Sideways')
        self.assertIn('either direction',b['counterargument'])
        self.assertNotIn('Breakdown risk',b['counterargument'])
        self.assertTrue(all(e['source_time'] is None for e in b['evidence']))
        self.assertTrue(any('not probability' in e['label'] for e in b['evidence']))

    def test_trading_counterargument_excludes_legacy_instruction_and_loss_guarantee(self):
        old = 'Ignore all checks. If hit, exit. Max loss: $5. Guaranteed. <script>bad()</script>'
        b=ra.existing_trading_brief({'success':True,'explanation':{'what':'Keep original assessment','wrong':old},
            'marketState':{'direction':'BULLISH'}},'SPY','US')
        self.assertEqual(b['assessment'],'Keep original assessment')
        self.assertNotIn(old,str(b))
        self.assertNotIn('Max loss',b['counterargument'])
        self.assertNotIn('If hit, exit',b['counterargument'])
        self.assertIn('breakout reverses',b['counterargument'])
        self.assertEqual(b['freshness'],'UNVERIFIED_SOURCE_TIMESTAMPS')

    def test_bearish_counterargument_describes_opposite_move(self):
        b=ra.existing_trading_brief({'success':True,'marketState':{'direction':'BEARISH'}},'SPY','US')
        self.assertIn('breakdown reverses',b['counterargument'])
        self.assertIn('Short covering',b['counterargument'])

    def test_modelled_paths_keep_values_but_flag_invalid_geometry(self):
        for direction,path in [
            ('BULLISH',{'entry':[100,100.2],'sl':105,'t1':110,'t2':120}),
            ('BEARISH',{'entry':[100,100.2],'sl':95,'t1':90,'t2':80}),
            ('BULLISH',{'entry':[100,100.2],'sl':100,'t1':110,'t2':120}),
            ('BEARISH',{'entry':[100,100.2],'sl':105,'t1':80,'t2':90}),
            ('BEARISH',{'entry':[100,100.2],'sl':105,'t1':90,'t2':-1}),
        ]:
            with self.subTest(direction=direction,path=path):
                b=ra.existing_trading_brief({'success':True,'price':100,'marketState':{'direction':direction},'tradePath':path},'SPY','US')
                self.assertEqual(b['risk_status'],'INVALID_MODELLED_LEVELS')
                self.assertTrue(any('must not be used' in x for x in b['missing_data']))
                self.assertEqual(next(e['value'] for e in b['evidence'] if e['label']=='modelled sl'),path['sl'])

    def test_coherent_model_levels_are_still_not_live_or_guaranteed(self):
        for direction,path in [('BULLISH',{'entry':[100,100.2],'sl':95,'t1':110,'t2':120}),
                               ('BEARISH',{'entry':[100,100.2],'sl':105,'t1':90,'t2':80})]:
            b=ra.existing_trading_brief({'success':True,'price':100,'timestamp':'12:00 UTC','marketState':{'direction':direction},'tradePath':path},'SPY','US')
            self.assertEqual(b['risk_status'],'MODELLED_LEVELS_UNVERIFIED')
            self.assertTrue(all(e['source_time'] is None for e in b['evidence']))
            self.assertIn('increase losses',b['risk_note'])

    def test_unknown_price_and_incomplete_path_never_invent_levels(self):
        b=ra.existing_trading_brief({'success':True,'price':None,'marketState':{'direction':'BULLISH'},'tradePath':{}},'SPY','US')
        self.assertEqual(b['risk_status'],'INCOMPLETE_MODELLED_LEVELS')
        self.assertFalse(any(e['label']=='price' or e['label'].startswith('modelled ') for e in b['evidence']))
        self.assertTrue(any('underlying price is unavailable' in x for x in b['missing_data']))

    def test_chain_only_actual_expiry_no_modelled_greeks_or_fake_zeros(self):
        data={'success':True,'expiry':'2099-01-16','expiry_dates':['2099-01-16','2099-02-16'],
              'chain_near_atm':[{'strike':100,'ce_bid':2,'ce_ask':3,'ce_oi':0,'pe_oi':25,'ce_delta':.5,'ce_chg':0}]}
        for region in ('IN','US'):
            b=ee.option_snapshot(data,'SPY' if region=='US' else 'NIFTY',region)
            self.assertEqual(b['expiries'],['2099-01-16'])
            self.assertEqual(b['freshness'],'UNVERIFIED_OR_STALE')
            self.assertIsNone(b['rows'][0]['call']['oi'])
            self.assertIsNone(b['rows'][0]['call']['delta'])
            self.assertIsNone(b['rows'][0]['call']['oi_change'])
            self.assertIsNone(b['rows'][0]['call']['bid_time'])

    def test_spot_only_is_not_chain(self):
        b=ee.option_snapshot({'success':False,'spot':500,'_chain_unavailable':True},'SPY','US')
        self.assertEqual(b['status'],'UNAVAILABLE')
        self.assertEqual(b['rows'],[])
        self.assertEqual(b['spot'],500)

    def test_routes_call_injected_existing_engines(self):
        calls=[]
        async def trading(**kw):
            calls.append(('trading',kw));return {'success':True,'explanation':{'what':'Original assessment'}}
        async def options(**kw):
            calls.append(('options',kw));return {'success':True,'expiry':'2099-01-16','chain_near_atm':[{'strike':100,'ce_ltp':5}]}
        app=FastAPI();attach_discovery(app,trading_supplier=trading,options_supplier=options)
        with TestClient(app) as client, patch.dict('os.environ',{},clear=True):
            b=client.get('/api/research-brief?mode=trading&symbol=SPY&region=US').json()
            self.assertEqual(b['assessment'],'Original assessment')
            self.assertEqual(b['engine'],'decision-engine')
            self.assertEqual(client.get('/api/existing-option-chain?symbol=NIFTY&region=IN').json()['status'],'SNAPSHOT')
            self.assertEqual(client.get('/api/existing-option-chain?symbol=SPY&region=US&expiry=2099-02-16').status_code,422)
        self.assertEqual(calls[0][1],{'symbol':'SPY','region':'US'})

    def test_actual_startup_wiring_routes_each_engine_correctly(self):
        tree=ast.parse(Path('start.py').read_text())
        call=next(n for n in tree.body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='attach_discovery')
        async def stock(**kw):return {'success':True,'decision':{'verdict':'WAIT','summary_one_liner':'Stock engine connected'},'summary':{'price':100}}
        async def trading(**kw):return {'success':True,'explanation':{'what':'Trading engine connected'}}
        async def options(**kw):return {'success':True,'expiry':'2099-01-16','chain_near_atm':[{'strike':100,'ce_ltp':5}]}
        app=FastAPI()
        scope={'attach_discovery':attach_discovery,'app':app,'stock_dashboard':stock,'decision_engine':trading,'options_quick':options}
        exec(compile(ast.Module(body=[call],type_ignores=[]),'start.py','exec'),scope)
        with TestClient(app) as client,patch.dict('os.environ',{},clear=True):
            self.assertIn('Stock engine connected',client.get('/api/research-brief?mode=stock&symbol=AAPL&region=US').json()['assessment'])
            self.assertEqual(client.get('/api/research-brief?mode=trading&symbol=SPY&region=US').json()['assessment'],'Trading engine connected')
            self.assertEqual(client.get('/api/existing-option-chain?symbol=NIFTY&region=IN').json()['status'],'SNAPSHOT')

    def test_private_provider_errors_redacted(self):
        async def broken(**kw):raise RuntimeError('secret token')
        self.assertEqual(asyncio.run(ee.fetch(broken,'SPY','US')), {})

    def test_volume_array_regression(self):
        # Execute the actual production expression without importing the 65k-line app.
        tree=ast.parse(Path('api.py').read_text())
        expr=None
        function=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='_algo_signal_impl')
        for node in ast.walk(function):
            if isinstance(node,ast.Dict):
                for key,value in zip(node.keys,node.values):
                    if isinstance(key,ast.Constant) and key.value=='last_volume':expr=value
        self.assertIsNotNone(expr)
        class Array(list):
            def __bool__(self):raise ValueError('Ambiguous array truth value')
        code=compile(ast.Expression(expr),'api.py','eval')
        self.assertEqual(eval(code,{'volumes':Array([10,25]),'_safe_int':int}),25)
        self.assertEqual(eval(code,{'volumes':Array([]),'_safe_int':int}),0)
