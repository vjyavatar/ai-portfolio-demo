"""
CELESYS ACTIVE TRADING — BACKTEST HARNESS
==========================================

Ports the v3 scoring engine from active-trading.js to Python and replays
historical 5-minute candles to measure whether high-confidence signals
actually predict profitable forward returns.

INTENTIONALLY LIMITED:
- OI-dependent factors (OI Structure 20%, False Breakout 15-25% penalty,
  Gamma Override) cannot be backtested without historical option chain
  snapshots, which yfinance does not provide. We score those factors as
  null (null-safe renormalization — same as production when NSE blocked).
- Only structural factors (Trend 25%, VWAP 20%, Strike 10%, R:R 10%) are
  fully exercised. That's 65% of production weight.
- Volume factor (15%) works for US tickers since yfinance ships volume.

USAGE:
    python backtest_active_trading.py              # default: US tickers, 30d
    python backtest_active_trading.py --days 10    # shorter test
    python backtest_active_trading.py --tickers AAPL NVDA TSLA

OUTPUT:
    - backtest_results.csv: every signal with forward returns
    - backtest_report.txt: score band statistics (hit rate, avg return)
"""

import argparse
import csv
import math
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

try:
    import yfinance as yf
    import pandas as pd
except ImportError:
    print("ERROR: Install dependencies first: pip install yfinance pandas")
    sys.exit(1)


# ════════════════════════════════════════════════════════════════════════
# PORT OF active-trading.js SCORING ENGINE (v22) — keep in sync
# ════════════════════════════════════════════════════════════════════════

def score_trend_strength(bars, side):
    """Exact port of scoreTrendStrength()."""
    if len(bars) < 3:
        return None
    last3 = bars[-3:]
    for b in last3:
        if b.get('c') is None or b.get('h') is None or b.get('l') is None:
            return None
    hh = hc = ll = lc = 0
    for i in range(1, 3):
        if last3[i]['h'] > last3[i-1]['h']: hh += 1
        if last3[i]['c'] > last3[i-1]['c']: hc += 1
        if last3[i]['l'] < last3[i-1]['l']: ll += 1
        if last3[i]['c'] < last3[i-1]['c']: lc += 1
    bull_seq = hh + hc
    bear_seq = ll + lc
    raw = bull_seq if side == 'CE' else bear_seq
    mapping = [30, 50, 65, 80, 95]
    return mapping[max(0, min(4, raw))]


def score_vwap_alignment(bars, spot, vwap, side):
    """Exact port of scoreVwapAlignment()."""
    if spot is None or spot <= 0 or vwap is None or vwap <= 0:
        return None
    if len(bars) < 5:
        return None
    s = 0
    for b in bars[-5:]:
        if b.get('h') is None or b.get('l') is None:
            return None
        s += (b['h'] - b['l'])
    atr = s / 5
    if atr <= 0:
        return None
    dist = (spot - vwap) / atr
    signed = dist if side == 'CE' else -dist
    if signed >= 1.5: return 95
    if signed >= 0.5: return 80
    if signed >= 0:   return 65
    if signed >= -0.5: return 40
    return 20


def score_volume_confirmation(bars):
    """Exact port of scoreVolumeConfirmation()."""
    if len(bars) < 6:
        return None
    last = bars[-1]
    if last.get('v') is None or last['v'] <= 0:
        return None
    prev5 = bars[-6:-1]
    s = 0
    for b in prev5:
        if b.get('v') is None or b['v'] <= 0:
            return None
        s += b['v']
    avg = s / 5
    if avg <= 0:
        return None
    ratio = last['v'] / avg
    if ratio >= 1.5: return 92
    if ratio >= 1.2: return 78
    if ratio >= 1.0: return 62
    return 45


def score_strike_quality(atm, spot, strike_step):
    if spot is None or spot <= 0 or atm is None or atm <= 0:
        return None
    if strike_step is None or strike_step <= 0:
        return None
    distance = abs(atm - spot) / strike_step
    if distance < 0.5: return 95
    if distance < 1.5: return 80
    if distance < 2.5: return 65
    return 45


def score_risk_reward(target, sl, premium):
    if None in (target, sl, premium):
        return None
    if premium <= 0 or target <= 0 or sl <= 0:
        return None
    reward = abs(target - premium)
    risk = abs(premium - sl)
    if risk <= 0:
        return None
    rr = reward / risk
    if rr >= 2.0: return 92
    if rr >= 1.5: return 78
    if rr >= 1.2: return 65
    return 45


def detect_side(bars, spot, vwap, day_open, day_high, day_low):
    """Port of detectSide() — uses only factors available from yfinance."""
    bull = bear = 0
    if vwap:
        if spot > vwap: bull += 2
        elif spot < vwap: bear += 2
    if day_open:
        if spot > day_open: bull += 1
        elif spot < day_open: bear += 1
    if day_high and day_low and day_high > day_low:
        rp = (spot - day_low) / (day_high - day_low)
        if rp > 0.6: bull += 1
        if rp < 0.4: bear += 1
    if bull == bear: return None
    return 'CE' if bull > bear else 'PE'


def score_trade(bars, symbol, strike_step):
    """
    Produce a confidence score for the LAST candle in `bars`, using v3 composite.
    OI + Gamma + False-Breakout factors are None (backtest limitation).
    Returns (score, side, confidence_state, missing_factors) or None.
    """
    if len(bars) < 6:
        return None
    last = bars[-1]
    spot = last['c']
    if spot is None or spot <= 0:
        return None

    # Compute session VWAP from bars (session-to-date)
    sum_pv = sum_v = 0
    for b in bars:
        typ = (b['h'] + b['l'] + b['c']) / 3 if all(b.get(k) is not None for k in 'hlc') else None
        v = b.get('v') or 0
        if typ is not None and v > 0:
            sum_pv += typ * v
            sum_v += v
    vwap = sum_pv / sum_v if sum_v > 0 else None

    day_open = bars[0]['o']
    day_high = max(b['h'] for b in bars if b.get('h') is not None)
    day_low = min(b['l'] for b in bars if b.get('l') is not None)

    side = detect_side(bars, spot, vwap, day_open, day_high, day_low)
    if side is None:
        return None

    # ATM = spot rounded to nearest strike_step
    atm = round(spot / strike_step) * strike_step

    # Assume an ATM option priced at ~1% of spot (typical equity ATM IV),
    # with risk/reward derived from 15%/30% policy. This is POLICY not fake
    # data — same as production.
    premium = spot * 0.01
    sl = premium * 0.85
    target = premium * 1.30

    factors = {
        'trend': score_trend_strength(bars, side),
        'vwap': score_vwap_alignment(bars, spot, vwap, side),
        'oi': None,   # no OI data in backtest — skipped
        'vol': score_volume_confirmation(bars),
        'strike': score_strike_quality(atm, spot, strike_step),
        'rr': score_risk_reward(target, sl, premium),
    }

    # Hard require structural factors (trend, vwap, strike, rr)
    for k in ('trend', 'vwap', 'strike', 'rr'):
        if factors[k] is None:
            return None

    # Weighted composite, renormalized over available factors
    weights = {'trend': 0.25, 'vwap': 0.20, 'oi': 0.20, 'vol': 0.15,
               'strike': 0.10, 'rr': 0.10}
    num = den = 0
    missing = []
    for k, w in weights.items():
        if factors[k] is None:
            missing.append(k)
        else:
            num += w * factors[k]
            den += w
    score = int(round(num / den)) if den > 0 else 0
    score = max(0, min(100, score))

    if score < 55:
        return None

    state = 'ideal' if score >= 80 else 'early' if score >= 68 else 'late' if score >= 60 else 'avoid'
    return {
        'score': score, 'side': side, 'state': state,
        'missing': missing, 'spot': spot, 'atm': atm,
        'premium': premium, 'factors': factors
    }


# ════════════════════════════════════════════════════════════════════════
# FORWARD RETURN COMPUTATION
# ════════════════════════════════════════════════════════════════════════

def compute_forward_return(bars, entry_idx, side, horizons):
    """
    For a signal at bars[entry_idx], compute the % move in spot at +N candles.
    Returns dict {horizon_minutes: pct_return}.
    For a CALL signal, return is positive if spot went up.
    For a PUT signal, return is positive if spot went down.
    """
    entry = bars[entry_idx]
    entry_spot = entry['c']
    out = {}
    for h in horizons:
        target_idx = entry_idx + (h // 5)  # h minutes / 5min per candle
        if target_idx >= len(bars):
            out[h] = None
            continue
        future_spot = bars[target_idx]['c']
        raw_pct = (future_spot - entry_spot) / entry_spot * 100
        out[h] = raw_pct if side == 'CE' else -raw_pct
    return out


# ════════════════════════════════════════════════════════════════════════
# BACKTEST RUNNER
# ════════════════════════════════════════════════════════════════════════

def bars_from_df(df):
    """Convert yfinance DataFrame to our bar format."""
    bars = []
    for ts, row in df.iterrows():
        bars.append({
            'ts': ts,
            'o': float(row['Open']) if pd.notna(row['Open']) else None,
            'h': float(row['High']) if pd.notna(row['High']) else None,
            'l': float(row['Low']) if pd.notna(row['Low']) else None,
            'c': float(row['Close']) if pd.notna(row['Close']) else None,
            'v': int(row['Volume']) if pd.notna(row['Volume']) else 0,
        })
    return bars


def infer_strike_step(symbol, spot):
    """Rough strike step for US tickers."""
    if spot is None or spot <= 0:
        return 1
    if spot < 25:   return 0.5
    if spot < 100:  return 1
    if spot < 200:  return 2.5
    if spot < 500:  return 5
    return 10


def run_backtest(tickers, days, horizons):
    """Main loop — fetch historical 5m bars for each ticker and replay."""
    all_signals = []
    print(f"[BACKTEST] Fetching {days}d of 5m bars for {len(tickers)} tickers…")

    end = datetime.now()
    start = end - timedelta(days=days)

    for sym in tickers:
        try:
            df = yf.download(sym, start=start, end=end, interval='5m',
                             progress=False, auto_adjust=False)
            if df.empty:
                print(f"  [SKIP] {sym}: no data")
                continue
            # Flatten multi-index columns if present
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            # Group by date — treat each trading day as a separate session for VWAP
            df['date'] = df.index.date
            session_count = 0
            signals_this_sym = 0
            for date, day_df in df.groupby('date'):
                session_bars = bars_from_df(day_df)
                if len(session_bars) < 10:  # need enough candles for both scoring + forward return
                    continue
                session_count += 1
                # Walk through this session's candles (after 6 bars warmup)
                for entry_idx in range(6, len(session_bars) - max(horizons) // 5):
                    bars_so_far = session_bars[:entry_idx + 1]
                    step = infer_strike_step(sym, bars_so_far[-1]['c'])
                    result = score_trade(bars_so_far, sym, step)
                    if result is None:
                        continue
                    fwd = compute_forward_return(session_bars, entry_idx,
                                                 result['side'], horizons)
                    signals_this_sym += 1
                    all_signals.append({
                        'sym': sym, 'date': str(date),
                        'ts': str(session_bars[entry_idx]['ts']),
                        'score': result['score'], 'side': result['side'],
                        'state': result['state'],
                        'spot': result['spot'],
                        'atm': result['atm'],
                        'fwd_15m': fwd.get(15), 'fwd_30m': fwd.get(30),
                        'fwd_60m': fwd.get(60),
                        'missing': ','.join(result['missing']),
                    })
            print(f"  [DONE] {sym}: {session_count} sessions, {signals_this_sym} signals")
        except Exception as e:
            print(f"  [ERROR] {sym}: {type(e).__name__}: {e}")

    return all_signals


def write_results(signals, csv_path):
    if not signals:
        print("[BACKTEST] No signals generated — nothing to write")
        return
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(signals[0].keys()))
        writer.writeheader()
        writer.writerows(signals)
    print(f"[BACKTEST] {len(signals)} signals → {csv_path}")


def write_report(signals, report_path):
    """Score band statistics — the real backtest output."""
    bands = [
        ('55-65 (late)',  55, 65),
        ('66-75 (early)', 66, 75),
        ('76-85 (ideal)', 76, 85),
        ('86-95 (strong)', 86, 95),
        ('96+ (elite)',   96, 101),
    ]
    horizons = [15, 30, 60]
    lines = []
    lines.append('=' * 72)
    lines.append('CELESYS ACTIVE TRADING — BACKTEST REPORT')
    lines.append(f'Generated: {datetime.now().isoformat()}')
    lines.append(f'Total signals: {len(signals)}')
    lines.append('=' * 72)
    lines.append('')
    lines.append('HYPOTHESIS: Higher confidence scores should produce better')
    lines.append('forward returns. If the engine works, 86+ band should beat 55-65.')
    lines.append('')
    lines.append(f'{"Score Band":<18} {"N":>6}   {"Win%@15m":>10} {"Avg@15m":>10} '
                 f'{"Win%@30m":>10} {"Avg@30m":>10} {"Win%@60m":>10} {"Avg@60m":>10}')
    lines.append('-' * 72)

    for label, lo, hi in bands:
        band_signals = [s for s in signals if lo <= s['score'] < hi]
        n = len(band_signals)
        if n == 0:
            lines.append(f'{label:<18} {n:>6}   {"—":>10} {"—":>10} '
                         f'{"—":>10} {"—":>10} {"—":>10} {"—":>10}')
            continue
        stats = []
        for h in horizons:
            returns = [s[f'fwd_{h}m'] for s in band_signals if s[f'fwd_{h}m'] is not None]
            if not returns:
                stats.extend(['—', '—'])
                continue
            wins = sum(1 for r in returns if r > 0)
            win_pct = wins / len(returns) * 100
            avg = sum(returns) / len(returns)
            stats.append(f'{win_pct:>9.1f}%')
            stats.append(f'{avg:>+9.3f}%')
        lines.append(f'{label:<18} {n:>6}   ' + ' '.join(f'{x:>10}' for x in stats))

    lines.append('')
    lines.append('=' * 72)
    lines.append('INTERPRETATION:')
    lines.append('  - If Win% rises with score band → engine has edge ✓')
    lines.append('  - If Win% flat or lower for high scores → engine lacks edge ✗')
    lines.append('  - Note: 65% of weight (structural factors only) — OI/Gamma untested')
    lines.append('=' * 72)

    txt = '\n'.join(lines)
    print('\n' + txt)
    with open(report_path, 'w') as f:
        f.write(txt)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tickers', nargs='+',
                        default=['SPY', 'QQQ', 'IWM', 'AAPL', 'NVDA', 'TSLA', 'META', 'AMZN'])
    parser.add_argument('--days', type=int, default=7,
                        help='Days of 5m history (yfinance limits intraday to ~60 days)')
    parser.add_argument('--horizons', nargs='+', type=int, default=[15, 30, 60])
    parser.add_argument('--csv', default='/tmp/backtest_results.csv')
    parser.add_argument('--report', default='/tmp/backtest_report.txt')
    args = parser.parse_args()

    signals = run_backtest(args.tickers, args.days, args.horizons)
    if signals:
        write_results(signals, args.csv)
        write_report(signals, args.report)
    else:
        print('[BACKTEST] No signals — check that yfinance is reachable')


if __name__ == '__main__':
    main()
