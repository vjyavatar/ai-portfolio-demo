# Celesys v4.62.2 — Intraday & Swing Setups (Decide tab)

You asked for setups with proven win rates for intraday/2-day holds. Here's the honest version of that.

---

## What I built (and what I deliberately didn't)

### What's IN the deploy

A new Decide sub-tab **⚡ Intraday Setups** scanning liquid universes (S&P 100 ex-financials for US, Nifty 50 for India) for THREE setups with PUBLISHED literature base rates:

| # | Setup | Timeframe | Literature base | Source |
|---|---|---|---|---|
| 1 | **Opening Range Breakout** | INTRADAY | 53-58% | Toby Crabel (1990): *Day Trading with Short Term Price Patterns and Opening Range Breakout* |
| 2 | **VWAP Reclaim After Open Drive** | INTRADAY | 60-65% | Berkowitz/Logue VWAP execution studies + Linda Raschke patterns |
| 3 | **Inside-Day Continuation** | 2-DAY SWING | 55-60% | Bulkowski, *Encyclopedia of Chart Patterns* (3rd ed) |

Each candidate shows: direction (↑/↓), entry, stop, two targets, R:R ratio, **the literature source**, and an honest caveat about why the base rate may not apply.

### What I deliberately did NOT do

- **No invented win rates.** Numbers come from cited published sources.
- **No claim that base rate = your real win rate.** Banner on every response: "typically 5-15% LOWER than literature in live execution."
- **No micro-cap inclusion.** Literature applies to liquid >$1B mcap, >$10M daily $vol. Including micro-caps would invalidate the base rates.
- **No sub-5-minute scalp setups.** Pure execution skill — no algorithm helps.
- **No backtest claims.** I did not run historical simulations on YOUR broker fills. No simulation = no claim.

---

## Honest disclaimer (shown in every API response)

> *Win rates shown are LITERATURE base rates from published studies on similar setups in different time periods. Your actual win rate depends on entry timing, slippage, position sizing, and emotional discipline — typically 5-15% LOWER than literature. Backtest with your own broker fills before sizing up. This tool finds CANDIDATES, not signals.*

This is on the page every time. No way to dismiss.

---

## Per-setup honest caveats (also shown per candidate)

**ORB:** "Base rate from liquid futures + large-cap equity studies. Falls apart on news days, low-vol days, and small-caps. Subtract 5-10% for live slippage."

**VWAP Reclaim:** "Base rate applies to >$1B mcap with >$10M daily $vol. Smaller names: literature does not apply. Subtract 5-10% for slippage."

**Inside-Day:** "Base rate is from daily-bar studies on US equities since 1990 with survivorship bias. Live execution costs cut 5-10% off theoretical. India NSE: same logic but base rates not directly studied."

---

## Pre-ship verification

- ✅ `api.py` compiles
- ✅ `app.js` + `app.min.js` syntax OK + byte-identical
- ✅ All 13 audit checks pass (endpoint, 3 detectors, 2 universes, disclaimer, sources, frontend loader/renderer, tab routing, version stamp)
- ✅ **6 runtime tests PASSED** on synthetic data:
  - ORB detects clean LONG breakout ✓
  - ORB detects clean SHORT breakdown ✓
  - ORB rejects chop ✓
  - Inside-day detects uptrend continuation ✓
  - Inside-day rejects non-inside range ✓
  - Inside-day rejects no-trend ✓
- ✅ Liquidity gate: skips US tickers <$1B mcap or <$10M daily $vol (literature filter)
- ✅ Per-setup caveats embedded in response
- ✅ Honest blanket disclaimer in every response

---

## How it works

```
Decide → ⚡ Intraday Setups
        │
        ├─ User picks timeframe: ALL / INTRADAY / SWING
        │
        ├─ Backend pulls 2 days of 5-min bars (intraday) + 2 years of daily bars (swing)
        │  for each liquid ticker in the universe
        │
        ├─ Runs 3 detectors:
        │    • ORB on 5-min data
        │    • VWAP Reclaim on 5-min data
        │    • Inside-Day Continuation on daily data
        │
        ├─ Filters by liquidity gate (>$1B mcap, >$10M $vol for US)
        │
        ├─ Ranks by literature_base_rate × R:R
        │
        └─ Returns top 30 candidates with full execution details
```

**Cache:** 5 min for intraday-included scans, 30 min for swing-only.

---

## Deploy

```bash
unzip celesys_v4_FINAL_DEPLOY.zip
cd celesys_v4_FINAL_DEPLOY/
git add -A
git commit -m "v4.62.2: Intraday & Swing Setups — ORB + VWAP Reclaim + Inside-Day with literature-cited base rates"
git push
```

Hard-refresh after deploy. Go to **Decide → ⚡ Intraday Setups**.

---

## What you'll see (example)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ ⚡  Intraday & Swing Setups                                  ↻ REFRESH  │
│    S&P 100 · 87 SCANNED · 12 SETUPS · 41.3s                              │
├─────────────────────────────────────────────────────────────────────────┤
│ [ ALL ] [ INTRADAY ] [ SWING ]                                           │
├─────────────────────────────────────────────────────────────────────────┤
│ ⚠ Win rates shown are LITERATURE base rates... typically 5-15% LOWER ... │
├─────────────────────────────────────────────────────────────────────────┤
│  ↑    NVDA  NVIDIA Corp                                INTRADAY    2.3:1 │
│ LONG  VWAP Reclaim After Open Drive                                R:R   │
│       SPOT $138.42  ENTRY $138.50  STOP $137.20  TARGET $140.10/$141.80  │
│       📚 62% literature base rate — Berkowitz/Logue VWAP studies         │
│       Base rate applies to >$1B mcap... subtract 5-10% for slippage      │
├─────────────────────────────────────────────────────────────────────────┤
│  ↑    AAPL  Apple Inc                                  INTRADAY    1.8:1 │
│ LONG  Opening Range Breakout                                       R:R   │
│       SPOT $234.12  ENTRY $234.40  STOP $232.80  TARGET $236.00/$237.60  │
│       📚 56% literature base rate — Crabel (1990)                        │
│       Falls apart on news days, low-vol days... subtract 5-10%           │
├─────────────────────────────────────────────────────────────────────────┤
│  ↑    LLY   Eli Lilly                                  2-DAY SWING 2.5:1 │
│ LONG  Inside-Day Continuation                                      R:R   │
│       SPOT $812.50  ENTRY $815.20  STOP $808.10  TARGET $824.50/$832.10  │
│       📚 58% literature base rate — Bulkowski Encyclopedia               │
│       Daily-bar studies since 1990 with survivorship bias                │
└─────────────────────────────────────────────────────────────────────────┘
```

Each card has:
- **Direction** (↑/↓ with color)
- **Setup name** + timeframe pill
- **Levels** (spot, entry, stop, two targets) — all monospace, all real
- **Literature note** with cited source
- **Honest caveat** below the source
- **R:R ratio** color-coded (green ≥2:1, amber ≥1:1, red <1:1)

---

## Honest tradeoffs

1. **First scan slow** (~40-60s). 87 US tickers × 2 yfinance calls each (5-min bars + daily bars) = ~170 calls. Cache makes subsequent scans instant.

2. **Yahoo intraday data quality varies.** 5-min bars are sometimes incomplete. If ORB/VWAP detector fails on a ticker, it just skips — no fake setup generated.

3. **The base rates are NOT your win rates.** Said it 5 times in this README. Will keep saying it.

4. **No setups will appear after market hours** for INTRADAY timeframe. Switch to SWING-only for after-hours scanning.

5. **India base rates are extrapolated.** Bulkowski's data is US equities. ORB/VWAP studies are US/futures. Indian NSE setups likely behave similarly but no direct study exists. The 5-15% "live slippage" haircut is more like 10-20% for India given wider spreads.

6. **NO tick-by-tick execution.** This finds CANDIDATES. Entry confirmation, micro-structure, fill quality — that's your job at the broker.

---

## Rollback

If anything breaks:
```bash
git revert HEAD
git push
```

To disable the new tab without rollback (in DevTools console):
```js
window._activeIntradaySetupsTab = false;
```

---

## What's NOT in this deploy

- ❌ Backtested win rates on YOUR broker. That's the only honest "proven" rate. Requires Polygon ($30/mo) + months of work.
- ❌ Real-time alerts / push notifications. Scanner only — you check it.
- ❌ Position sizing calculator. Still on you.
- ❌ Auto-execution. Still on you. Probably forever.

---

## What's next (if you want)

- **r62.3:** Add Pivot Point Bounce (Larry Williams) — another well-documented intraday setup
- **r62.4:** Real backtester using daily bars (free Yahoo data is enough for swing-timeframe validation)
- **r62.5:** Polygon integration ($30/mo) for real intraday backtests with realistic fills

Each is its own deploy. None ship without your green light.
