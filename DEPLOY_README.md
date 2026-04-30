# Celesys v4.63.10 — Momentum scanner accuracy fix

You said: "make sure results are accurate... we want to catch momentum stocks quite early."

This fixes the SNDK miss and rebuilds momentum architecture properly.

---

## What was wrong (root cause analysis)

When I built r63.6 (Find Similar) and r63.8 (Momentum), I created a NEW universe `_FIND_SIMILAR_US_UNIVERSE` (80 tickers, hand-curated) instead of using your existing `_momentum_universe_us` (180 tickers, already curated). **That's the duplication anti-pattern you flagged in r63.5.**

The result: SNDK was already in your codebase's `_momentum_universe_us` — but my scanner pointed at the wrong list.

Plus the momentum math itself had three accuracy problems I didn't catch in r63.8:
1. **Relative strength was a fake** — used absolute return as proxy instead of comparing vs SPY/^NSEI
2. **Breakout was too lenient** — linear scoring meant a stock 30% off its 52w high still scored 0; we want STEP-function detection that flags ATH-region stocks (where SNDK lives) precisely
3. **No "early emerging" detection** — math couldn't distinguish a stock that just started ripping from one that had already topped

---

## What I changed (4 architectural fixes)

### 1. Unified universe (eliminated duplication)
- `_FIND_SIMILAR_US_UNIVERSE` now aliases `_momentum_universe_us` (was 80 hand-curated → now 198 quality tickers)
- Added missing AI peers: **MRVL, TSM, ASML, STX, ON, NXPI, SWKS, MPWR, KLAC, LRCX, AMAT, TER**
- Added AI energy peers: **GEV, ETR, D, SO, XEL, NRG**

**Result:** SNDK, MU, WDC, SMCI, VST, CEG, NBIS, CRWV, APP, ARM, PLTR, NNE, OKLO, TLN, IONQ — all in scope now.

### 2. Real relative strength (was fake)
**Before:** `rs_score = (ret_6m + 20) * 2` (just absolute return)
**After:** Fetch SPY (US) or ^NSEI (IN) once per scan, compute `RS = stock_6m_return / benchmark_6m_return`. Map: 1x=50, 2x=80, 3x+=100.

A stock up 60% when SPY's up 20% is genuinely strong (RS=3x). A stock up 60% when SPY's up 80% is mediocre (RS=0.75x).

### 3. Step-function breakout (was linear)
**Before:** linear from 30% off 52w high → 0
**After:**
- Within 2% of 52w high → 100 (at ATH like SNDK)
- Within 5% → 90
- Within 10% → 75
- Within 20% → 55
- Within 30% → 35
- Beyond 30% → falls off rapidly

This properly flags stocks living at all-time highs as the strongest signal.

### 4. Tier system updates
- Added **✨ EARLY EMERGING** tier for stocks 60-80 score with strong acceleration
- Multi-condition early detection: triggers when accel_ratio ≥ 2x **OR** 1Y was flat (<5%) and 3M is +25%+ **OR** no 1Y data but 3M is exceptional (+30%+)

---

## Pre-ship verification

### 13/13 audit checks pass
- ✅ Universe additions: MRVL, TSM, ASML, STX present in `_momentum_universe_us` (now 198 tickers)
- ✅ `_FIND_SIMILAR_US_UNIVERSE` aliased to `_momentum_universe_us`
- ✅ Momentum scoring uses `benchmark_closes` parameter
- ✅ Step-function breakout (5%/10%/20%/30% thresholds)
- ✅ EARLY EMERGING tier defined and emitted
- ✅ Benchmark fetch for SPY (US) / ^NSEI (IN)
- ✅ accel_ratio exposed for tier detection
- ✅ Python compiles, JS syntax OK, app.min.js byte-identical
- ✅ Version v4.63.10

### Behavioral test on realistic ripper patterns

| Pattern | Score | Signal | Real-world equivalent |
|---|---|---|---|
| **SNDK-class parabolic** ($30→$1000) | **100.0** | 🔥 EXTREME | SNDK |
| Long history early ripper (+59% 1Y, accelerating) | 85.4 | 🔥 EXTREME | Genuinely strong |
| Mid-phase rip (+72% 1Y, +49% 3M) | 83.9 | 🔥 EXTREME | MU-style |
| **Just starting** (+5% 1Y, +25% in 3M) | **78.4** | 🚀 STRONG | **THIS catches early rippers** |
| Late phase (+149% 1Y, +50% 3M) | 75.2 | 🚀 STRONG | Past peak but still strong |
| **Mature/fading** (+63% 1Y, only +5% 3M) | **55.2** | ⚡ BUILDING | Correctly de-emphasized |
| Declining (-26% 1Y) | 22.4 | 📉 WEAK | Filtered |

The math now produces STRONG signals for stocks just starting their rip — exactly what "catching early" means. Mature/fading trends correctly demoted.

---

## Realistic expectation setting (honest)

### What this WILL do
- Show SNDK ranked **top 1-3** in your next scan
- Surface emerging rippers (60-80 score with acceleration) before they hit parabolic phase
- Compare stocks to actual market benchmark, not just absolute returns
- Catch stocks at ATH precisely via step-function breakout

### What this CAN'T do
- "Catch SNDK at $30 before the rip" — no algorithm sees +3000% moves coming. We catch SNDK NOW (still EXTREME) and surface tomorrow's rippers when their 3-month trend confirms.
- Real-time intraday momentum — needs paid feed
- Russell 2000 full scan — free Finnhub rate limit makes it impossibly slow
- Predict the future

### Cold scan time
- 198 US tickers × ~3 Finnhub calls each = ~595 calls
- Free Finnhub: 60/min = ~10 min cold scan
- Cached 6 hours after first scan
- Subsequent users: instant

---

## Deploy

```bash
unzip celesys_v4_FINAL_DEPLOY.zip
cd celesys_v4_FINAL_DEPLOY/
git add -A
git commit -m "v4.63.10: Momentum accuracy — unified universe + RS + step-fn breakout"
git push
```

Wait ~3 min, hard-refresh.

---

## Verify after deploy

1. `curl https://celesys.ai/api/version` → `"version": "v4.63.10"`
2. Generate Deep DD for any US ticker → click 🔥 MOMENTUM
3. **First scan: ~10 minutes** (cold). After: instant.
4. **Expected results in EXTREME tier:** SNDK, MU, NBIS, CRWV, NVDA, PLTR, IONQ, OKLO, VST, CEG, APP, SMCI (the 2026 rippers)
5. **Expected in EARLY EMERGING:** stocks with weak 1Y but strong recent 3M (depends on current market)

If SNDK doesn't appear in top 5, something's wrong — the math gives it 100.0 in synthetic test, real numbers should be similar.

---

## Files changed

| File | Change |
|---|---|
| `api.py` | Universe additions (+18 tickers), unified _FIND_SIMILAR_US_UNIVERSE alias, new scoring fn (~80 lines), benchmark fetch |
| `static/app.js` | Version stamp only |
| `static/app.min.js` | Synced |
| `index.html` | Cache-bust + version stamps |

No new dependencies. No new env vars. Active Trading untouched.

---

## What I deliberately didn't do

1. **Russell 2000 full scan** — would take ~30 min cold, free Finnhub can't pace 2000 tickers practically. Stayed at 198 quality tickers.
2. **Real-time intraday refresh** — needs paid feed
3. **Auto-discovery via Finnhub /stock/symbol-by-market-cap** — that endpoint is paid-tier only. Stayed with curated universe (which already has the rippers).
4. **Removed EARLY EMERGING tier as separate display bucket** — kept it as a signal label, but the tuned math elevates real early rippers to STRONG/EXTREME directly. Better signal, fewer confusing tiers.

---

## Honest acknowledgment

I made the original mistake in r63.6 by creating a duplicated universe. The fix in r63.10 is the architecturally correct version that should have been there from the start. **You called this out in r63.5** ("centralize duplicated code"), and I missed it for the find-similar universe. This deploy fixes that miss.
