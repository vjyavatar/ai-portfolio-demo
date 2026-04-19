"""Synthetic test: feed the scoring engine known bars and verify output is sensible."""
import sys
sys.path.insert(0, '/home/claude/patch/tools')

# Import just the scoring functions without the yfinance-dependent runner
import importlib.util
spec = importlib.util.spec_from_file_location(
    "bt", "/home/claude/patch/tools/backtest_active_trading.py"
)

# Monkey-patch yfinance so import doesn't fail
class _FakeYf:
    def download(self, *a, **k): raise RuntimeError("not used in unit test")
sys.modules['yfinance'] = _FakeYf()

bt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bt)

# Bullish scenario — prices rising, volume strong, VWAP rising
bars_bull = [
    {'o': 100, 'h': 101, 'l': 99.5, 'c': 100.5, 'v': 100000},
    {'o': 100.5, 'h': 101.5, 'l': 100, 'c': 101.2, 'v': 110000},
    {'o': 101.2, 'h': 102, 'l': 101, 'c': 101.8, 'v': 115000},
    {'o': 101.8, 'h': 102.5, 'l': 101.5, 'c': 102.3, 'v': 120000},
    {'o': 102.3, 'h': 103.2, 'l': 102, 'c': 103, 'v': 125000},
    {'o': 103, 'h': 103.8, 'l': 102.8, 'c': 103.5, 'v': 180000},  # HH+HC, volume surge
]

# Bearish scenario
bars_bear = [
    {'o': 100, 'h': 100.5, 'l': 99, 'c': 99.5, 'v': 100000},
    {'o': 99.5, 'h': 99.8, 'l': 98.5, 'c': 98.8, 'v': 110000},
    {'o': 98.8, 'h': 99, 'l': 98, 'c': 98.2, 'v': 115000},
    {'o': 98.2, 'h': 98.5, 'l': 97.5, 'c': 97.8, 'v': 120000},
    {'o': 97.8, 'h': 98, 'l': 97, 'c': 97.2, 'v': 125000},
    {'o': 97.2, 'h': 97.4, 'l': 96, 'c': 96.3, 'v': 180000},
]

# Chop scenario (should be rejected or score low)
bars_chop = [
    {'o': 100, 'h': 100.5, 'l': 99.5, 'c': 100, 'v': 100000},
    {'o': 100, 'h': 100.3, 'l': 99.8, 'c': 100.1, 'v': 100000},
    {'o': 100.1, 'h': 100.4, 'l': 99.9, 'c': 100, 'v': 100000},
    {'o': 100, 'h': 100.3, 'l': 99.8, 'c': 100.1, 'v': 100000},
    {'o': 100.1, 'h': 100.5, 'l': 99.9, 'c': 100, 'v': 100000},
    {'o': 100, 'h': 100.2, 'l': 99.8, 'c': 100, 'v': 100000},
]

print('=== Backtest scoring engine — synthetic tests ===\n')

r_bull = bt.score_trade(bars_bull, 'TEST', 1)
print(f'Bullish setup     → {r_bull}')
assert r_bull is not None, 'Bullish setup should produce a signal'
assert r_bull['side'] == 'CE', 'Bullish should be CE'
assert r_bull['score'] >= 70, f'Bullish should score ≥70, got {r_bull["score"]}'

r_bear = bt.score_trade(bars_bear, 'TEST', 1)
print(f'Bearish setup     → {r_bear}')
assert r_bear is not None, 'Bearish setup should produce a signal'
assert r_bear['side'] == 'PE', 'Bearish should be PE'
assert r_bear['score'] >= 70, f'Bearish should score ≥70, got {r_bear["score"]}'

r_chop = bt.score_trade(bars_chop, 'TEST', 1)
print(f'Choppy setup      → {r_chop}')
# Chop may or may not generate a signal depending on marginal VWAP — but if it does, score should be low
if r_chop is not None:
    assert r_chop['score'] < 80, f'Chop should score <80 if signal generated, got {r_chop["score"]}'
    print(f'  (chop scored {r_chop["score"]} — below "ideal" band ≥80, as expected)')

# Forward-return test
fwd = bt.compute_forward_return(bars_bull + [{'c': 105, 'o':103.5,'h':105.2,'l':103.5,'v':100000}] * 20,
                                 5, 'CE', [15, 30, 60])
print(f'\nForward return (bull entry at idx 5, simulated +1.5% move): {fwd}')
assert fwd[15] > 0, 'CE with upward move should show positive forward return'

print('\n✅ BACKTEST ENGINE LOGIC VERIFIED')
print('   Ready to run with real yfinance data on your Render box or local.')
