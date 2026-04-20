# Celesys deploy — April 20, 2026

## Files changed vs. the previous deploy

Three files were modified. All other files are byte-identical to the original archive.

| File | Why |
|------|-----|
| `api.py` | (1) Synthetic option-premium fabrication removed from all three fallback paths. (2) FINNIFTY + MIDCPNIFTY dropped from India scanner universe. |
| `static/active-trading.js` | (1) Synthetic-premium detector + red badge + `onExecute` hard-block. (2) ENTRY trigger redesigned — now evaluates underlying spot against a side-aware trigger level (CE breaks above, PE breaks below), not option premium against a premium level. |
| `static/options-engine.js` | Canonical `window._QT_LOT_SIZES` table with post-Jan-2026 NSE values. All 6 local lot-size maps routed through it. |

Everything else in the archive (`app.js`, `app.min.js`, `premium-override.js`, `premium-theme.css`, `index.html`, `manifest.json`, `sw.js`, `start.py`, `requirements.txt`, `runtime.txt`, `n8n-workflows.json`, `docs/`, `tools/`, `AT_PORT_PLAN.md`) is unchanged.

## Deploy order

1. Push `api.py` first. This stops synthetic option-premium generation at the source and removes FINNIFTY/MIDCPNIFTY from the scanner.
2. Push both JS files. They're independent of each other; order doesn't matter.
3. The backend's `_bottom_nav_cache` has a 2-minute TTL. Expect up to 2 minutes of stale data after step 1 — trigger a manual Render restart if you need a clean cut-over.

## Key behavior changes users will notice

- **Scanner shows fewer tickers during NSE outages.** When the NSE option chain is unavailable, affected tickers now drop out silently instead of appearing with fabricated premiums. Render logs show `[SYNTH-PREMIUM-BLOCKED]` for each drop, so you can monitor frequency.
- **No more FINNIFTY / MIDCPNIFTY in the Top Trades / scanner.** Users can still analyze them via the Quick Trade tab if they hit those symbols directly.
- **ENTRY panel actually shows ACTIVE now.** Previously the evaluator compared the option premium to a premium-level trigger with CE-only logic, so PE cards were permanently INVALID and CE cards only went ACTIVE by coincidence. Now it compares underlying spot against a side-aware spot trigger.
- **Scanner card label changed** from `Trig 215.22` to `Trig@spot 24611.50` so users don't confuse a spot-level number with a premium-level number.
- **QT rupee values change for index options.** The lot size QT uses is now correct (NIFTY 65 instead of 75, MIDCPNIFTY 120 instead of 75, FINNIFTY 60 instead of 40). Every max-profit / max-loss / margin / net-premium number is now accurate. Note: users who memorized old numbers will see them shift.

## What to monitor after deploy

1. Render logs: grep for `[SYNTH-PREMIUM-BLOCKED]` — frequency reveals how often NSE was failing silently before. Spikes indicate NSE rate-limiting.
2. Scanner count in Bottom Nav: should be similar to before since the synthetic fallback was only firing intermittently. A sustained drop means something else is wrong.
3. One ENTRY card sample: select a ticker, wait for 90s refresh, verify status shows a sensible state (ACTIVE / WATCHING / INVALID with small distance), not a permanent INVALID.
4. One QT NIFTY trade: confirm `Net Debit × 65 = total cost in rupees` matches the broker's expectation.

## Known backlog (not fixed in this deploy)

Five other silent-substitution bugs identified during audit but intentionally not touched (scope creep avoidance):

1. `api.py:17823` — DCF `fair_value = price × 1.05` placeholder flowing into sell targets
2. `api.py:2467` — stale cache returned without `_stale` flag
3. `options-engine.js:9212` — scoring signals default to 50 ("neutral") when data missing
4. `app.js:7587, 18559, 18605` — ATR defaults to `price × 0.01` when unavailable
5. `api.py:2476` — 52-week range defaults to `price × 1.1 / price × 0.9` when Yahoo doesn't return it

Prioritize based on which you see in Render logs or user reports.
