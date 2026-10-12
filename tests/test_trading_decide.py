"""Original Decide strategy selection and final safety gate, without network imports."""
import ast
from copy import deepcopy
from pathlib import Path
import unittest

TREE=ast.parse(Path('api.py').read_text())
DECIDE=next(n for n in TREE.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='decision_engine')

def scope():
    nodes=[n for n in TREE.body if isinstance(n,ast.FunctionDef) and n.name in ('_legacy_algo_research_guard','_decision_research_guard')]
    env={};exec(compile(ast.Module(body=nodes,type_ignores=[]),'api.py','exec'),env);return env

def assignment(name):
    return next(n for n in ast.walk(DECIDE) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets))

class DecideTests(unittest.TestCase):
    def strategy(self,direction,signal,iv):
        env=scope();algo=env['_legacy_algo_research_guard']({'success':True,'signal':signal,'direction':direction})
        env.update(algo=algo,direction=direction,iv_rank=iv,state='TRENDING',adx=30,strats=[])
        branch=next(n for n in ast.walk(DECIDE) if isinstance(n,ast.If) and isinstance(n.test,ast.BoolOp) and isinstance(n.test.values[0],ast.Name) and n.test.values[0].id=='_is_bullish')
        nodes=[assignment('sig'),assignment('_is_bullish'),assignment('_is_bearish'),branch]
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'api.py','exec'),env)
        self.assertEqual(algo['signal'],'HOLD / WAIT')
        return env['strategy']

    def test_original_bullish_strategy_branches_survive_guard(self):
        for iv,expected in [(20,'BUY CALL'),(50,'BULL CALL SPREAD'),(80,'SELL PUT / BULL PUT SPREAD')]:
            self.assertEqual(self.strategy('BULLISH','BUY',iv)['name'],expected)

    def test_original_bearish_strategy_branches_survive_guard(self):
        for iv,expected in [(20,'BUY PUT'),(50,'BEAR PUT SPREAD'),(80,'SELL CALL / BEAR CALL SPREAD')]:
            self.assertEqual(self.strategy('BEARISH','AVOID',iv)['name'],expected)

    def test_original_elite_research_decision_is_retained_for_analytics(self):
        env={'_elite':{'decision':'WAIT','research_decision':'BUY_CALL'}}
        exec(compile(ast.Module(body=[assignment('_elite_decision')],type_ignores=[]),'api.py','exec'),env)
        self.assertEqual(env['_elite_decision'],'BUY_CALL')

    def example(self):
        return {'success':True,'signal':'BUY','confidence':{'score':82,'grade':'A'},
            'priceHistory':[99,100,102],'strategy':{'name':'BUY CALL','reason':'Calculated research'},
            'tradePath':{'entry':[100,101],'sl':95,'t1':110,'t2':120},
            'tradeSpec':{'premium':5},'recommendedTrade':{'tradeable':True},
            'liveTag':{'tag':'TRADE NOW'},'tradeVerdict':{'verdict':'CALL BUY','tradeType':'CALL BUY','action':'FULL POSITION','probability':80,'warnings':[]},
            'explanation':{'what':'Original assessment','doNow':'Buy now','wrong':'Max loss $5'},
            'engines':{'decision':'CALL BUY','finalScore':80}}

    def test_final_gate_preserves_calculations_but_disables_actions(self):
        raw=self.example();original=deepcopy(raw);out=scope()['_decision_research_guard'](raw)
        self.assertEqual(raw,original)
        self.assertEqual(out['signal'],'HOLD / WAIT');self.assertEqual(out['research_signal'],'BUY')
        self.assertFalse(out['execution_enabled']);self.assertFalse(out['live_data_verified'])
        self.assertEqual(out['strategy']['name'],'BUY CALL');self.assertEqual(out['tradePath']['sl'],95)
        self.assertEqual(out['priceHistory'],raw['priceHistory']);self.assertEqual(out['confidence']['score'],82)
        self.assertEqual(out['explanation']['what'],'Original assessment')
        self.assertEqual(out['tradeVerdict']['tradeType'],'WAIT');self.assertIsNone(out['tradeVerdict']['probability'])
        self.assertNotIn('FULL POSITION',out['tradeVerdict']['action'])
        self.assertFalse(out['recommendedTrade']['tradeable'])
        self.assertEqual(out['engines']['decision'],'WAIT')
        self.assertIn('UNVERIFIED',out['liveTag']['tag']);self.assertNotIn('Max loss',out['explanation']['wrong'])

    def test_repeated_guard_preserves_research_values_and_no_duplicate_warning(self):
        guard=scope()['_decision_research_guard'];first=guard(self.example());again=guard(first)
        self.assertEqual(first,again)
        self.assertEqual(len(again['tradeVerdict']['warnings']),1)

    def test_self_asserted_verification_does_not_enable_actions(self):
        raw=self.example();raw.update(live_data_verified=True,execution_enabled=True,tradeable=True)
        out=scope()['_decision_research_guard'](raw)
        self.assertFalse(out['live_data_verified']);self.assertFalse(out['execution_enabled']);self.assertFalse(out['tradeable'])

    def test_production_success_return_passes_through_final_guard(self):
        guarded=[n for n in ast.walk(DECIDE) if isinstance(n,ast.Return) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='_decision_research_guard']
        self.assertEqual(len(guarded),1)
        self.assertIsInstance(guarded[0].value.args[0],ast.Call)

    def test_failed_response_stays_failure(self):
        raw={'success':False,'error':'No source data'}
        self.assertEqual(scope()['_decision_research_guard'](raw),raw)
