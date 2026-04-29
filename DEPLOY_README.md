# Celesys v4 — r61.5 (verified clean + earnings intel message improvement)

## What's in this deploy

This bundles **r61.4** (layman split + enrichment from earlier today) + a small message improvement:

### r61.4 — Layman improvements (from earlier today)
- Split combined `institutional.layman` into 5 sub-laymen (insider / holders / risk-adjusted / peers / chart) — fixes the "bleed" you saw in your screenshot
- Enriched all laymen with specific numbers (Sharpe 1.46, 82% inst ownership, etc.)
- Added 4 missing frontend hooks
- Cache bumped to v4

### r61.5 — Earnings Intel message improvement (this deploy)
The "Missing 4 key fields: earnings_history, next_earnings_date, post_earnings_moves, implied_move_inputs" message you saw is now a human-readable explanation:

**Before:**
> Missing 4 key fields: earnings_history, next_earnings_date, post_earnings_moves, implied_move_inputs

**After:**
> No upcoming earnings catalyst on the calendar. Either the company recently reported (next earnings ~3 months away) or our data provider hasn't published the next confirmed date yet. Check back closer to the typical reporting cycle.

This is contextual:
- Missing next_earnings + implied → message above
- Missing only next_earnings → "Next earnings date unavailable"
- Missing only options data → "Options chain unavailable for implied-move estimate"
- Missing earnings history → "Past EPS records unavailable"

Technical field list still preserved in `_missing_technical` for debugging.

---

## About the JS error in your screenshots

Your Image 2 and Image 3 show `JS Error (line 1): Uncaught SyntaxError: Function statements require a function name` at the bottom.

I ran exhaustive syntax checks on every JS file in this build:
- ✅ `app.js` — clean
- ✅ `app.min.js` — clean (byte-identical to app.js)
- ✅ `active-trading.js` — clean
- ✅ `options-engine.js` — clean
- ✅ `premium-override.js` — clean
- ✅ All inline scripts in `index.html` — clean
- ✅ Strict mode parse — clean
- ✅ Custom anonymous-function-statement scanner — found nothing

**Conclusion:** the JS error is from the OLDER deployed version on Render, not from this build.

When you push r61.5 the version hash bumps and the browser will fetch the new clean code, and that error should disappear.

If after pushing r61.5 + hard-refresh the error STILL appears, screenshot the browser DevTools console (F12 → Console tab) — that will show the actual file and line number, which the in-page error banner doesn't.

---

## About Image 1 (Earnings Move Intelligence "NO DATA")

This is correct behavior, not a bug. The MU report shows "Earnings on 2026-03-18 (-42 day(s) away)" — earnings was 42 days ago. There's no upcoming earnings to analyze.

After r61.5 deploys, the message becomes:
> No upcoming earnings catalyst on the calendar. Either the company recently reported (next earnings ~3 months away)...

Much clearer than the old "Missing 4 key fields" technical dump.

---

## Files changed (vs r61.3)

| File | Change source |
|---|---|
| `api.py` | r61.4 (split institutional layman + enriched laymen + cache v4) |
| `static/app.js` | r61.4 (5 new frontend hooks for split sub-laymen) |
| `static/app.min.js` | Synced byte-identical |
| `earnings_intel.py` | r61.5 (human-readable INCOMPLETE messages) |
| `index.html` | Version hash bumped |

---

## Deploy

```bash
unzip celesys_v4_FINAL_DEPLOY.zip
cd celesys_v4_FINAL_DEPLOY/
git add -A
git commit -m "r61.5: Layman split + enrichment + human-readable earnings intel messages"
git push
```

Wait ~3 min, **hard-refresh Ctrl+Shift+R** (the version hash bump should also force this), then:

1. Open MU Deep DD → scroll to Insider Activity. Layman should now ONLY discuss insider activity (counts, sentiment, $ flow). No more Sharpe/ownership bleed.

2. Scroll down — see separate layman blocks on Institutional Ownership, Risk-Adjusted Returns, Peer Comparison, Price Chart cards.

3. Earnings Move Intelligence panel — instead of "Missing 4 key fields" you'll see a human explanation.

4. JS error banner should be gone (assuming it was from the older deploy).

If the JS error persists after deploy + hard-refresh, open DevTools Console (F12) and paste me the actual error with line/file info — that's the only way to track it down further.

---

## Verified before shipping

- ✅ All 4 Python files compile
- ✅ All 5 JS files pass `node --check`
- ✅ Strict mode parsing clean
- ✅ No anonymous function statements at statement position (custom scan)
- ✅ `app.min.js` byte-identical to `app.js`
- ✅ All 11 layman frontend hooks present
- ✅ Cache bumped to v4 (invalidates v3 entries)
- ✅ Earnings intel falls back to friendly message
