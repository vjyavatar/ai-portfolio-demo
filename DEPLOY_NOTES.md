# Celesys deploy — April 21, 2026 (r16)

Incremental over r15. Two files changed: `api.py`, `static/active-trading.js`.

## The situation

After r15 deployed, India scanner showed `IN: 0 scored in 13.0s, 0 buy`
and users saw "Scanner still warming up (boot takes ~30s) — retrying"
even after market opened. Three distinct issues, three fixes.

## Fix 1: MC fallback NoneType crash

**What failed:** r14's MoneyControl spot fallback assumed MC always
returns a dict under `data`. For unknown symbols like `MOM50` and
`CPSE`, MC returns `{"data": null}`. Code did `mc_r.json().get("data", {})`,
which returned `None` (because `{}` default only applies if the key
is missing, not if it's null). Then `.get("pricecurrent", ...)` on
None crashed every time.

**Log evidence:**
```
[OPTIONS-QUICK] MOM50: MC fallback also failed: 'NoneType' object has no attribute 'get'
[OPTIONS-QUICK] CPSE: MC fallback also failed: 'NoneType' object has no attribute 'get'
```

**Fix:** defensive parsing — `mc_r.json() or {}`, then `.get("data") or {}`,
then `isinstance(mc_data, dict)` guard, then try/except around the float
cast. Every layer now handles None gracefully.

## Fix 2: Known-no-options ETFs polluting scans

**What was happening:** NSE doesn't list option chains for most
ETFs — `NIFTYBEES`, `BANKBEES`, `GOLDBEES`, `SILVERBEES`, `ITBEES`,
`JUNIORBEES`, `MOM50`, `CPSE`, `ICICIB22`, `MAFANG`. But these were
in the scanner universe, so every scan:

1. Tried NSE `option-chain-equities` — returned empty
2. Fell through to MC fallback — returned spot only (or crashed on None)
3. Returned `success: false` — ticker dropped

That's **7 wasted scan slots** consuming HTTP calls and log noise per
scan cycle, for tickers that cannot possibly produce a trade.

**Fix:** `_NO_OPTIONS_SYMBOLS` set; these silent-drop before NSE is
called. Saves roughly 2-3 seconds per scan and cleans logs.

**If you want to keep these for price tracking elsewhere in the app
(not the options scanner):** leave them in `in_tickers` but they'll
be correctly dropped from the scanner. Other endpoints that call
`fetch_nse_stock_data` for spot/fundamentals are unaffected.

## Fix 3: Frontend lied about "warming up" for completed empty scans

**What failed:** when the scanner ran and genuinely returned 0 tickers
(because market was briefly stale, NSE hiccuped, or all universe
tickers failed), the UI still showed:

> "Scanner still warming up (boot takes ~30s) — retrying"

This is dishonest. The scan completed. It got 0 results. Users stared
at this message for 5+ minutes thinking the app was broken.

**Fix:** backend r10+ already sends `_last_scan_empty: true` when a
scan completes with zero results (as opposed to `tickers: []` from a
cold boot). Frontend now differentiates:

- `lastScanEmpty === true` → **"No trade opportunities right now —
  scanner found 0/47. Data sources may be rate-limited or market is quiet."**
- Cold boot (no scan yet) → "Scanner warming up (first boot takes ~30s) — retrying"

Users now know the difference between "we're still starting" and "we
ran and found nothing."

## What I did NOT fix

**Why indices/large-cap stocks are failing during scans.**

The screenshot you sent showed the tail-end of one scan cycle (the
ETF failures). I couldn't see what happened to NIFTY, BANKNIFTY,
SENSEX, HDFCBANK, RELIANCE, TCS — those log lines were scrolled
off-screen. My best guess: the boot scan ran 15 seconds after app
startup, which could be during pre-market stale window. NSE's
chain endpoint returns empty or missing-data during the first
minute of market open.

**To diagnose the root cause**, next session I need the FULL log
of one scan cycle — from the `[BOTTOM-NAV] Starting...` line to
`[BOTTOM-NAV] ✅ IN: N scored` — so I can see what NSE returned for
each ticker, not just the ETF failures.

## Deploy

Two files: `api.py`, `static/active-trading.js`. Push both. No env
changes, no requirements changes.

## Post-deploy checklist

1. **Render logs during a scan cycle** — you should NOT see repeated
   `NSE returned no data for NIFTYBEES` or `MOM50: MC fallback also
   failed`. Those symbols now silent-drop.

2. **The UI message** — when the scanner is empty after a completed
   scan, the strip should say "No trade opportunities right now — scanner
   found 0/47..." instead of "warming up."

3. **Real Indian stocks** — NIFTY, BANKNIFTY, SENSEX, HDFCBANK,
   RELIANCE should score normally if NSE is up. If `IN: 0 scored`
   still happens after market is fully open (~9:20 AM IST), capture
   the full log and we'll diagnose in the next session.

## Honest flags

1. **r16 makes the scanner behavior correct for expected-empty tickers
   and makes the UI honest, but it doesn't fix "why all of India is
   failing" if that's the actual situation.** I can't diagnose root
   cause without seeing NSE-side logs for NIFTY/RELIANCE/etc. during
   a failing scan cycle.

2. **The `_NO_OPTIONS_SYMBOLS` list is my best-guess set.** If NSE
   adds options to GOLDBEES tomorrow (unlikely but possible), we'd
   silently skip it. If you notice a symbol in that list that
   actually DOES have options, remove it.

3. **The UI message text is opinionated.** If you want different
   wording ("Market quiet — no signals" / "Waiting for opportunities"
   etc.), one-line edit in `active-trading.js` line 10189-10192.

## Known backlog (unchanged)

Scoring calibration, fair_value placeholder, score=50 default, ATR
default, 52W default, US rate-limit structural problem (r15 reduces
10x, doesn't eliminate).
