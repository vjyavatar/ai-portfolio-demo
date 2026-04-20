# Celesys deploy — April 20, 2026 (r5)

Incremental over r4. `api.py` and `static/active-trading.js` both changed.

## What's new in r5

### Backend: fix Yahoo rate-limit causing 0 US tickers

**Problem seen in Render logs:** every US ticker hit `Chain fetch error: Too Many Requests` → dropped by the strict no-fabrication policy → `BOTTOM-NAV ✅ US: 0 scored`. Empty scanner.

**Root cause:** 8 parallel scanner threads called `tk.option_chain()` concurrently with no rate discipline. Yahoo's per-IP concurrent-request cap got tripped; every call failed.

**Fix (3 parts, api.py):**
1. Added `_yahoo_rate_wait()` before `tk.option_chain()` in `_options_quick_impl`. This is a module-level mutex that serializes across threads with 1.5s spacing.
2. Added **one retry on 429/"Too Many Requests"** with a 3s backoff. Yahoo's cap is per-burst, not per-hour, so a single patient retry usually succeeds.
3. Reduced US worker count from 8 → 3. With the global rate-wait, 8 threads would just queue anyway. 3 is cleaner and leaves per-burst headroom.

Expected scan time: ~20s for US (previously 22s with 0 results). Fits inside 2-min cache comfortably.

### Frontend: horizontal TOP TRADES strip

Three cards side-by-side at the top of the screen instead of stacked in a left column. Below them: Live Monitor + Detail in a 2-column layout.

**Layout before (r4):**
```
┌───┬────┬────┐
│TOP│LIVE│DTL │
│   │    │    │  (3-column vertical)
│   │    │    │
├───┴────┴────┤
│  SCANNER    │
```

**Layout after (r5):**
```
┌─────────────┐
│ TOP TRADES  │  (full-width horizontal strip)
│ [1][2][3]   │
├─────┬───────┤
│LIVE │DETAIL │
│     │       │  (2-column below)
├─────┴───────┤
│  SCANNER    │
```

Each card still has its own chevron. Expanding one card grows only that column; the other two stay at collapsed height. Search bar moved into the strip's header row.

Held/off-scan positions still pinned — now appear in their own horizontal mini-strip ABOVE the 3-up (max 3 visible).

### Everything from r4 still applies

- WATCHING band 0.4% (fresh cards land in WATCHING, not INVALID)
- Voice verdict fix (`v.label` → `v.verdict`)
- Synthetic-premium block, FINNIFTY/MIDCPNIFTY removed, spot-based trigger, SYNTHETIC badge, QT lot sizes

## Deploy

Push `api.py` + `static/active-trading.js`. Nothing else changed. Layout change will be immediately visible on reload.

## What to verify

1. Render logs: US scan should now show `US: N scored in ~20s, M buy` where N > 0 (not 0). If still 0 after deploy, Yahoo's rate limit is per-hour not per-burst — needs a different fix (longer cache TTL).
2. UI: top-trades are now a horizontal strip across the full width.
3. Click a card's chevron — only that card expands, others stay small.
4. Search bar works from within the strip header.
5. Mobile / narrow viewport: three 1fr columns may look cramped under 900px. I did not add a breakpoint — flag if this is an issue.

## Known backlog

Same as before (fair_value placeholder, stale cache flag, score=50, ATR default, 52W default). Also still open: scoring calibration where OVERPRICED+WIDE+RANGING can still reach BUY_SMALL.

## Honest flags

- I didn't live-test the new horizontal layout. It passes `node --check` but the interplay between `flex: 0 0 auto` on the strip and `grid repeat(3, 1fr)` on the cards could look different on wide vs narrow screens.
- The `tk.option_chain()` retry is wrapped in a try/except that only retries on rate-limit keywords. If Yahoo returns a generic error that isn't recognized (new error message, connection reset, etc), no retry will fire — the original exception propagates and the ticker drops. This is intentional but may need tuning.
