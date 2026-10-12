"""Execute selected production AST only; never import the network-heavy application."""
import ast
import asyncio
import os
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

TREE=ast.parse(Path('api.py').read_text())

def function(name,parent=TREE):
    return next(node for node in parent.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name==name)

def load(node,scope):
    exec(compile(ast.Module(body=[node],type_ignores=[]),'api.py','exec'),scope)
    return scope[node.name]

class PrefetchTests(unittest.TestCase):
    def test_default_startup_returns_without_sleep_or_network(self):
        scope={'os':os}
        start=load(function('_start_prefetch_loop'),scope)
        with patch.dict(os.environ,{},clear=True):
            asyncio.run(start()) # No asyncio/pool/provider in scope: accidental work fails.

    def test_direct_prefetch_is_disabled_without_explicit_opt_in(self):
        prefetch=load(function('_prefetch_popular'),{'os':os})
        for value in ('','false','1'):
            with patch.dict(os.environ,{'CELESYS_YAHOO_PREFETCH':value},clear=True):
                self.assertIsNone(prefetch())

    def ticker_loader(self,cached):
        cache=Mock(return_value=cached);gate=Mock();ticker=Mock(return_value=SimpleNamespace(info={'currentPrice':100,'previousClose':99}))
        scope={'_smart_cache_get':cache,'_yahoo_rate_wait':gate,'yf':SimpleNamespace(Ticker=ticker),'_smart_cache_set':Mock()}
        return load(function('_fetch_one',function('_prefetch_popular')),scope),scope

    def test_cached_prefetch_skips_provider_and_rate_gate(self):
        fetch,scope=self.ticker_loader({'price':100})
        self.assertEqual(fetch('SPY'),('SPY',True))
        scope['yf'].Ticker.assert_not_called();scope['_yahoo_rate_wait'].assert_not_called()
        scope['_smart_cache_get'].assert_called_once_with('price:SPY')

    def test_uncached_prefetch_uses_gate_before_provider(self):
        fetch,scope=self.ticker_loader(None)
        scope['yf'].Ticker.side_effect=lambda symbol: (self.assertEqual(scope['_yahoo_rate_wait'].call_count,1) or SimpleNamespace(info={'currentPrice':100,'previousClose':99}))
        self.assertEqual(fetch('SPY'),('SPY',True))
        scope['_smart_cache_set'].assert_called_once()

    def test_busy_prefetch_does_not_fetch_or_overwrite_cache(self):
        fetch,scope=self.ticker_loader(None)
        scope['_yahoo_rate_wait'].side_effect=RuntimeError('queue busy')
        self.assertEqual(fetch('SPY'),('SPY',False))
        scope['yf'].Ticker.assert_not_called();scope['_smart_cache_set'].assert_not_called()

    def rate_limiter(self):
        sleeps=[];lock=threading.Lock()
        def sleep(delay):
            self.assertTrue(lock.acquire(blocking=False),'Lock held during sleep')
            lock.release();sleeps.append(delay)
        scope={'_time':SimpleNamespace(monotonic=lambda:100.0,sleep=sleep),
               '_yahoo_rate_lock':lock,'_yahoo_next_call':0.0,'_yahoo_min_delay':1.5,'_yahoo_max_wait':5.0}
        return load(function('_yahoo_rate_wait'),scope),scope,sleeps

    def test_concurrent_reservations_are_distinct_without_sleeping_lock(self):
        reserve,scope,sleeps=self.rate_limiter()
        with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda _:reserve(),range(4)))
        self.assertEqual(sorted(sleeps),[1.5,3.0,4.5])
        self.assertEqual(scope['_yahoo_next_call'],106.0)

    def test_congested_queue_fails_without_reserving_or_sleeping(self):
        reserve,scope,sleeps=self.rate_limiter();scope['_yahoo_next_call']=106.0
        with self.assertRaisesRegex(RuntimeError,'queue busy'):reserve()
        self.assertEqual(scope['_yahoo_next_call'],106.0);self.assertEqual(sleeps,[])

    def test_elapsed_queue_starts_immediately(self):
        reserve,scope,sleeps=self.rate_limiter();scope['_yahoo_next_call']=90.0
        reserve();self.assertEqual(sleeps,[]);self.assertEqual(scope['_yahoo_next_call'],101.5)
