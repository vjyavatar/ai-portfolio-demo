# Celesys deploy — April 20, 2026 (r8)

Incremental over r7. Only `static/active-trading.js` changed.

## What's new in r8: live data-age indicator on cards

**The problem:** you reported that card values (spot / buy / SL / target) stayed identical across refreshes for 5+ minutes. The backend cache is supposed to be 120s; either it's not refreshing, or the frontend is holding stale data, or the backend is handing back old timestamps. Without a visible timestamp we were flying blind.

**The fix (2 pieces):**

### 1. Capture backend timestamp into state
Every `/api/bottom-nav-scan` response already includes a `ts` field (epoch seconds when the scan ran). The frontend was ignoring it. Now we capture it as `state.dataTs` and surface it on every card.

### 2. Live-ticking age label on each card
Bottom-left corner of every top-3 card now shows:
```
DATA: 34s ago
```

Colors shift as time passes:
- **Gray** (≤90s) — fresh, within one refresh cycle
- **Amber** (91–180s) — one full cycle missed, suspicious
- **Red** (>180s) — stale, treat data as unreliable

The counter ticks every second **without full rerender** — piggy-backs on the existing 1s countdown timer to do direct DOM text updates via `data-age-ts` markers. No render cost.

**If DATA jumps back to "0s ago" when you refresh, cache is working correctly.**
**If DATA keeps climbing past 180s and stays red, the backend is genuinely serving stale data** and we need to investigate `_bottom_nav_cache` in `api.py` next.

## What this WON'T fix

This is a diagnostic, not a cure. If the backend is legitimately cached-stale (the 120s TTL isn't triggering a background refresh, or the refresh is erroring silently), you'll *see* the red "DATA: 3m 42s ago" label — but the data underneath will still be stale. The next step once you confirm staleness visually is a focused backend investigation of `_bottom_nav_cache` TTL behavior.

## Everything from r7 still applies

Scanner BLOCKED rows show reason inline, expanded card shows all blockers, light theme, horizontal TOP TRADES strip, always-visible Spot/Buy/SL/Target, 18px scanner rows, WATCHING band 0.4%, voice verdict fix, synthetic-premium block, Yahoo rate-wait, QT lot sizes.

## Deploy

Only `static/active-trading.js` changed. If r7 is live, push this one file.

## What to test

1. Load the page. Each card should show a gray `DATA: Ns ago` label at its bottom-left.
2. Watch for 2 minutes. The counter should tick up every second. If it freezes, the ticker itself is broken (tell me).
3. At ~90s the label should turn amber.
4. At ~180s it should turn red.
5. When the backend refreshes (should happen ~every 2 minutes for a fresh scan), the counter should reset to a small number. **If it doesn't reset, that's the staleness bug confirmed.**

## Honest flags

- The 1s ticker runs on every card. On a narrow viewport where cards might be hidden, we're still iterating through the DOM. Negligible cost (microseconds per tick) but worth knowing.
- The color-sync check compares `_el.style.color` string to the new color string. Browsers sometimes normalize colors (`rgb(…)` vs `#XXXXXX`), which would cause the check to always fail and cause redundant sets. Harmless but not perfectly optimized.
- If the backend `ts` field is ever missing or zero (e.g. boot-up empty response), `state.dataTs` stays null and no label renders. Cards will look like pre-r8 in that case.

## Known backlog (unchanged)

Scoring calibration (OVERPRICED+WIDE+RANGING → BUY_SMALL), fair_value placeholder, stale cache flag, score=50 default, ATR default, 52W default.
