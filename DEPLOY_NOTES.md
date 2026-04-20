# Celesys deploy — April 20, 2026 (r9)

Incremental over r8. Only `static/active-trading.js` changed.

## What's new in r9: cards much bigger

Everything on the top-3 cards scaled up for readability:

| Element           | r8                  | r9                  |
|-------------------|---------------------|---------------------|
| Symbol + strike   | 22px / weight 800   | **28px / weight 900** |
| Side pill (CE/PE) | 11px                | **14px**            |
| Confidence        | 26px / weight 800   | **34px / weight 900** |
| Sub-label (uncal) | 9px                 | **11px / weight 800** |
| Price chip label  | 9px                 | **11px / weight 900** |
| Price chip value  | 16px                | **22px / MONO / weight 900** |
| TAKE TRADE button | 36×100 / 11px label | **48×128 / 14px label** |
| LIVE/PENDING pill | 36×100 / 11px       | **48×128 / 14px**   |
| DATA: Ns ago      | 9px                 | **11px / weight 900** |
| Card padding      | 10px                | 14-16px (22px bottom for age label) |

Price values now render in MONO font for tabular alignment — so the decimals line up vertically when you scan across Spot → Buy → SL → Target.

## 🚨 URGENT: Your last screenshot confirmed the staleness bug

Every card showed `DATA: 122m 32s ago` in red. **The backend hasn't refreshed in over 2 hours.** This means `_bottom_nav_cache` in `api.py` is stuck — the background refresh thread either isn't firing or is erroring silently after the boot scan.

The r8 indicator did its job: it made the invisible visible. But we still need to fix the cache staleness itself. That's a **separate backend investigation** — not in this r9 zip. Suggested next move after deploying r9:
1. Check Render logs for `[BOTTOM-NAV] ✅ US: N scored in Ts` lines.
2. If that line appears only once at boot and never again, the 120s background-refresh path in `bottom_nav_scan` is broken.
3. Likely culprits: `_bottom_nav_busy` flag getting stuck (thread crashed after setting it, never cleared); Yahoo 429s killing the refresh thread silently; the `threading.Thread(daemon=True)` never actually starting under uvicorn's event loop.

I can investigate in a fresh session focused just on that.

## Deploy

Only `static/active-trading.js` changed. Push one file or the whole zip.

## What to verify

1. Each card should be noticeably larger and bolder. Confidence should dominate visually (34px).
2. Price values align in monospaced columns down the row.
3. `DATA: Ns ago` at bottom-left should be readable at a glance, color-shifting.

## Honest flags

- The strip's grid is still `repeat(3, 1fr)`. With 34px confidence + 128px button + chevron + 28px symbol + side pill, the top row needs ~400px per card to not wrap. On a 1440px screen this fits easily. On a 1200px screen it'll be tight. On a 1024px screen the top row will wrap or crush — if you see that, tell me and I'll drop the side pill (CE/PE color is already on the left-edge border) or shrink the button.
- The size bump doesn't fix the cache staleness bug — that's backend. This deploy makes the UI better while the bug is visible.

## Known backlog (unchanged)

Scoring calibration, fair_value placeholder, stale cache flag, score=50 default, ATR default, 52W default. Plus now: `_bottom_nav_cache` not refreshing after boot scan.
