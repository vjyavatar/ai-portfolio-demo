import ast
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading
import types
import unittest
from market_request_cache import RequestCache


class CacheTests(unittest.TestCase):
    def test_one_load_for_concurrent_identical_requests(self):
        cache = RequestCache(); entered = threading.Event(); release = threading.Event(); calls = []
        def load():
            calls.append(1); entered.set(); release.wait(2); return {'quote_time': 123, 'price': 10}
        with ThreadPoolExecutor(max_workers=5) as pool:
            first = pool.submit(cache.get, 'SPY', load)
            self.assertTrue(entered.wait(1))
            rest = [pool.submit(cache.get, 'SPY', load) for _ in range(4)]
            release.set()
            values = [f.result() for f in [first]+rest]
        self.assertEqual(len(calls), 1)
        self.assertTrue(all(v['quote_time'] == 123 for v in values))

    def test_expiry_copies_and_capacity(self):
        now = [100]; cache = RequestCache(capacity=2, clock=lambda: now[0]); calls = []
        def load(): calls.append(1); return {'nested': [7], 'source_time': 90}
        data = cache.get('SPY', load, ttl=60); data['nested'].append(8)
        self.assertEqual(cache.get('SPY', load)['nested'], [7])
        now[0] = 161
        self.assertEqual(cache.get('SPY', load)['source_time'], 90)
        self.assertEqual(len(calls), 2)
        cache.get('QQQ', load); cache.get('AAPL', load)
        self.assertEqual(cache.snapshot()['entries'], 2)

    def test_rate_limit_circuit_blocks_other_symbols_then_recovers(self):
        now = [100]; cache = RequestCache(clock=lambda: now[0]); calls = []
        def limited(): calls.append(1); raise RuntimeError('429 private response')
        self.assertEqual(cache.get('SPY', limited, default={}), {})
        self.assertIsNone(cache.get('QQQ', lambda: calls.append(2)))
        self.assertEqual(calls, [1]); self.assertEqual(cache.snapshot()['cooldown_skips'], 1)
        self.assertNotIn('private', str(cache.snapshot()))
        now[0] = 401
        self.assertEqual(cache.get('QQQ', lambda: {'price': 20}), {'price': 20})

    def test_empty_response_negative_cache_is_short(self):
        now = [0]; cache = RequestCache(clock=lambda: now[0]); calls = []
        def load(): calls.append(1); return {}
        cache.get('SPY', load, default={}); cache.get('SPY', load, default={})
        self.assertEqual(len(calls), 1)
        now[0] = 16; cache.get('SPY', load, default={}); self.assertEqual(len(calls), 2)

    def test_wait_timeout_does_not_spawn_second_request(self):
        cache = RequestCache(wait_seconds=0); gate = threading.Event(); started = threading.Event(); calls = []
        def load(): calls.append(1); started.set(); gate.wait(2); return 1
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(cache.get, 'SPY', load); self.assertTrue(started.wait(1))
            self.assertIsNone(cache.get('SPY', load)); gate.set(); self.assertEqual(future.result(), 1)
        self.assertEqual(len(calls), 1)

    def test_actual_safe_ticker_separates_intervals_and_reuses_across_instances(self):
        tree = ast.parse(Path('api.py').read_text())
        node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == '_SafeTicker')
        calls = []
        class Fake:
            def __init__(self, *args, **kwargs): pass
            def history(self, **kwargs): calls.append(kwargs); return {'quote_time': 10, 'interval': kwargs['interval']}
            @property
            def info(self): calls.append('info'); return {'regularMarketTime': 10}
        env = {'_yf_original': types.SimpleNamespace(Ticker=Fake), '_legacy_market_cache': RequestCache()}
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'api.py', 'exec'), env)
        a, b = env['_SafeTicker']('SPY'), env['_SafeTicker']('spy')
        a.history(interval='5m'); b.history(interval='5m'); a.history(interval='1d')
        self.assertEqual(len(calls), 2)
        self.assertEqual(a.info, b.info); self.assertEqual(len(calls), 3)

if __name__ == '__main__': unittest.main()
