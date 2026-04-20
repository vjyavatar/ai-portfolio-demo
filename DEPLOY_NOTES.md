# Celesys deploy — April 20, 2026 (r6)

Incremental over r5. Only `static/active-trading.js` changed vs r5.

## What's new in r6 (light theme + bigger UI)

### 1. Overlay shell light-themed

The `C` palette was already light (off-white bg, near-black text) from an earlier session, but the outer overlay wrapper around it was still hardcoded to `#020617` (dark blue) and `#0F172A`. The BACK button and top bar bled through dark regardless of palette settings — which is why your screenshot showed a dark UI even though the cards were light.

Fixed three hardcoded colors at the overlay mount site: overlay bg `#020617 → #F8FAFC`, top bar bg `#0F172A → #FFFFFF`, borders/back-button `#1E293B → #CBD5E1`. Text color on the overlay flipped from `#F8FAFC → #0F172A`.

Now the entire Active Trading view is light.

### 2. Card price row always visible

Previously you had to click the chevron to see Buy / Trig@spot / SL / Target. Now a 4-column chip row with **Spot · Buy · SL · Target** renders on the collapsed card. Each chip: 9px label (weight 800), 16px value (weight 800). Red for SL, green for Target. Always visible, scannable at a glance.

The trigger level (underlying breakout price) moved to the expanded-only section since it's contextual — you only need it when deciding whether to enter.

Collapsed card now shows: **Symbol · Strike · Side (CE/PE) · Confidence · Button · Chevron · Spot · Buy · SL · Target**.

### 3. Secondary scanner enlarged

- Container: 220px → 320px tall (more rows visible)
- Header row: 12px → 14px, weight 900
- Body rows: 15px → 18px, weight 900 on Symbol / Dir / Score, weight 800 on Strike
- Row height: 38px → 48px
- Trend column: 14px → 16px bold
- TAKE TRADE button: 12px → 14px with bigger padding
- BLOCKED / AWAITING DATA labels: 11px → 13px, weight 900

## Everything from r5 still applies

- Backend Yahoo rate-wait + one 429 retry + worker count 8→3 (US scanner was returning 0 tickers due to rate limits; this fixes it)
- Horizontal TOP TRADES strip across full width, 2-column Live Monitor + Detail below
- WATCHING band 0.4%, voice verdict fix, synthetic-premium block, FINNIFTY/MIDCPNIFTY removed, spot-based trigger, QT lot sizes

## Deploy

Only `static/active-trading.js` changed since r5. If r5 is already live, push just that one file. Otherwise ship the whole zip.

## What to verify after deploy

1. **Is the UI actually light now?** If you still see dark bg on the back button or top bar, the browser cached the old JS — force-refresh (Cmd+Shift+R / Ctrl+Shift+F5).
2. **Each collapsed card shows all 4 price values (Spot, Buy, SL, Target).**
3. **Scanner rows are visibly bigger** — should fit ~5 rows in the 320px band.
4. **Green/red/yellow colors read cleanly on white** (Tailwind-600/700 range). Not washed out, not neon.

## Honest flags

1. **Didn't live-render.** Passes `node --check`. The interplay between the topBar (symbol+side+conf+button+chevron) and the new price row below may crush on narrow cards (~320px width when three sit side-by-side on a 1366px screen). If it looks cramped, the easy fix is to drop the Side pill from the topBar and put it next to Symbol as a smaller suffix.
2. **Trigger moved out of collapsed view.** If users find themselves expanding every card just to check the trigger level, I'd move it back in or surface it as a small pill in the topBar.
3. **Scanner height of 320px** reduces the vertical space available for the Live Monitor + Detail area by ~100px. If that squeezes anything important below the fold, tell me.

## Known backlog (unchanged)

Same as before: DCF `fair_value = price × 1.05`, stale cache flag, score=50 default, ATR default, 52W default. Plus scoring calibration (OVERPRICED+WIDE+RANGING can reach BUY_SMALL).
