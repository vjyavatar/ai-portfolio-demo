# Celesys deploy — April 20, 2026 (r4)

Incremental over r3. Only `static/active-trading.js` changed vs r3.

## What's new in r4

### WATCHING threshold loosened (Option A)

**Problem:** fresh-scanned cards immediately showed INVALID. Root cause: the trigger is set 0.2% past spot at scan time, and the WATCHING band was also 0.2% — so a freshly-scanned card sat exactly at the edge of INVALID by arithmetic, not by market structure.

**Fix:** WATCHING band bumped from 0.2% to 0.4% (2× the trigger buffer). Now a fresh card lands in WATCHING, and only flips to INVALID if spot drifts against the thesis by more than 0.4%. Spot crossing the trigger still means ACTIVE.

Semantics are now clean:
- `ACTIVE` = triggered (spot has crossed the trigger level)
- `WATCHING` = within 0.4% of trigger in the against-direction (fresh scans land here; normal intraday drift)
- `INVALID` = more than 0.4% against the thesis (setup breaking down)

Also bumped the voice's "entry very close" threshold from 0.2% to 0.4% so voice + UI stay in sync.

## Everything from r3 still applies

r3 included (beyond r2): voice verdict fix (`v.label` → `v.verdict` at 3 sites). That stays.

r2 included: synthetic-premium block, FINNIFTY/MIDCPNIFTY removed, spot-based trigger, card collapse + bigger fonts, QT lot sizes, SYNTHETIC badge + button gate.

## Deploy

Only `static/active-trading.js` changed vs r3. If r3 is already deployed, push just that one file. Otherwise deploy the whole zip.

## What to verify after deploy

1. Select a trade whose spot is near its trigger — should show `🟡 WATCHING`, not `🔴 INVALID`.
2. Wait for spot to cross trigger — should flip to `🟢 ACTIVE`.
3. Voice should say "strong buy @ 90%" or "buy @ 77%" etc., NOT "neutral @ 77%" (r3 fix).
4. Verdict transitions on 90s refresh should trigger voice announcements (r3 fix).

## Known backlog (untouched)

Same as before:
1. DCF `fair_value = price × 1.05` placeholder
2. Stale cache returned without `_stale` flag
3. Scoring signals default to 50 when data missing
4. ATR defaults to `price × 0.01`
5. 52W range defaults to `price × 1.1 / 0.9`

Also flagged but not touched: scoring calibration — trades can reach BUY_SMALL with OVERPRICED options + WIDE spreads + RANGING regime (seen in DELL 202.5 CE screenshot, +13 points). Separate conversation if you want to tighten.
