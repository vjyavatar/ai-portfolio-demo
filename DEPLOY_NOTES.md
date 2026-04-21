# Celesys deploy — April 20, 2026 (r10)

Incremental over r9. Both `api.py` and `static/active-trading.js` changed.

## The big fix: cache + routing gaps

Your session-opening question was "why is the data 2 hours stale" and my deep trace found FIVE root causes, not one. This deploy addresses all five.

### Gap 1 — Stuck busy-flag defense (FIXED)

`_bottom_nav_busy` was a set that threads added to at scan start and removed at scan end (in a `finally`). If the thread died outside the try/finally (SIGKILL, OOM, kernel interrupt), the flag stuck forever and no future scan could fire. **This was the most likely root cause of your 2-hour staleness.**

Fix: added `_bottom_nav_busy_since` tracking when each flag was set. The endpoint checks on every request: if a flag is older than `_BUSY_MAX_AGE` (180s, much longer than any real scan), force-clear it and spawn a fresh thread.

### Gap 2 — Keep-last-good policy (FIXED)

Previous behavior: if a scan returned 0 tickers (e.g. Yahoo 429 storm wiping every US ticker), the cache was OVERWRITTEN with `{tickers: []}`. Good data from an earlier scan was lost.

Fix: if a scan returns 0 tickers AND the previous cache had tickers, preserve the previous snapshot. Original `ts` stays (so the frontend data-age chip still grows — the user sees the staleness). Two sidecar flags get added: `_last_scan_attempt` (when we last TRIED) and `_last_scan_empty: true` (so UI can show the distinction).

### Gap 3 — Longer TTLs (FIXED)

- India: 120s → **300s** (NSE is reliable; no need to hammer)
- US: 120s → **180s** (Yahoo needs breathing room between bursts)

### Gap 4 — Indian stock routing (FIXED — this was a real bug)

`nse_options` has always supported both the index endpoint (`option-chain-indices`) AND the stock endpoint (`option-chain-equities`). But `_options_quick_impl` hard-coded a whitelist of 5 indices and sent everything else to Yahoo, which **does not carry Indian stock option chains**.

Result: every Indian single-stock scan (HDFCBANK, RELIANCE, TCS, BANKBEES, GOLDBEES, ITBEES, etc.) returned `_chain_unavailable` and got dropped. Your 47-ticker India scan was really a 3-ticker scan (just the indices that worked).

Fix: broadened the NSE-first routing from `is_india_index` to `is_india` (all India symbols). Indian stocks that fail NSE now return honest failure instead of the pointless Yahoo fallback.

**Test after deploy:** pull up HDFCBANK or RELIANCE in QT. Option chain should render. If it doesn't, NSE's stock-equity endpoint response shape differs from what `nse_options` normalizes and we need a small follow-up.

### Gap 5 — Stale state visible to user (FIXED, both halves)

Backend endpoint now returns:
- `_stale: true` when serving cache past TTL (refresh in progress)
- `_cache_age_sec: <int>` so frontend can compute/display
- `_last_scan_empty: true` when keep-last-good policy is active

Frontend shows on each card's bottom-left:
- `DATA: 34s ago` (gray) — normal
- `STALE: 4m 12s ago` (amber) — cache past TTL, refreshing in background
- `LAST-GOOD: 8m 30s ago` (red) — last scan returned empty, showing old data

## Everything from r9 still applies

Light theme, horizontal TOP TRADES strip, big card typography (34px confidence, 22px prices, MONO font, 14px button), 18px scanner rows, BLOCKED-with-reason, WATCHING 0.4%, voice verdict fix, synthetic-premium block, QT lot sizes.

## Deploy

Both files changed: `api.py` and `static/active-trading.js`. Push both or the whole zip.

## What to verify after deploy

1. **India scanner count > 3**: logs should now show `[BOTTOM-NAV] ✅ IN: N scored` where N is 10-30+, not just the 3 indices. If it's still ≤3, `nse_options` is returning something unexpected for stocks.
2. **Age label prefix reflects state**: normally `DATA:`, turns to `STALE:` after 5min, turns to `LAST-GOOD:` if Yahoo has a bad spell.
3. **Staleness recovers**: the 2-hour freeze you saw should be impossible now — if the flag gets stuck, endpoint force-clears after 180s.

## Honest flags

1. **Gap 4 is the highest-risk change.** I broadened NSE routing without live-testing the response shape from `option-chain-equities`. If it differs from `option-chain-indices`, Indian stock cards may render with garbled fields. First live test should be HDFCBANK in QT.
2. **Keep-last-good extends the staleness window.** Under sustained Yahoo 429s you could see `LAST-GOOD` data that's many minutes old and still treats Spot/Buy/SL/Target as tradable. The red color + LAST-GOOD prefix is meant to signal "don't actually trade this." If users trust the numbers anyway, we need a stronger gate (e.g. disable the TAKE TRADE button when `_last_scan_empty` is active).
3. **Stuck-flag defense has a 180s window.** If a scan legitimately takes >180s (Yahoo stalls badly), a second scan could spawn before the first finishes — both writing to the same cache slot. Last-write-wins; not a data corruption issue, just wasted work. Acceptable.

## Known backlog (unchanged)

Scoring calibration (OVERPRICED+WIDE+RANGING → BUY_SMALL), fair_value placeholder, score=50 default, ATR default, 52W default.
