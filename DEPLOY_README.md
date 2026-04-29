# Celesys v4.62.3 — Production loading states (UX fix)

You correctly called out that the Intraday Setups screen sat blank with just static text and no spinner. That's below production standard. Fixed.

---

## What was broken

Looking at the screen in your screenshot — the loading state was a single `<div>` with text "Pulling 5-min bars + daily history for liquid names..." That's it. No spinner. No progress. No timer. No abort. No timeout. If the API hangs, you'd sit there forever wondering if it's working.

I shipped this in r62.2 (Intraday Setups) AND in r62.0 (Micro-Cap Hunter). Both screens had the same UX bug.

**The pattern was already established in your own codebase** (lines 6005, 6917, 10074 — those use proper spinners with `animation:spin`). I just didn't follow the established pattern when I shipped new features. That's on me.

---

## What's in r62.3

A reusable production loading component `_csLoader()` + a `_csFetchWithTimeout()` helper, then wired into both broken loaders.

### `_csLoader()` provides:
1. **Spinner** with CSS rotation (the universal "I'm working" signal)
2. **Title + subtitle** so user knows what's loading
3. **Status line** that can be updated mid-scan (e.g., "Pulling data..." → "Running detectors...")
4. **Indeterminate progress bar** that pulses (visual continuity)
5. **Live elapsed time counter** (ticks every 0.5s, color escalates if scan is slow)
6. **Estimated typical time** (set per-loader so user knows what's normal)
7. **CANCEL button** that aborts the scan
8. **Color escalation** — text turns amber after 1.5× expected, red after 2.5× with warning message

### `_csFetchWithTimeout()` provides:
- 2-minute hard timeout via AbortController
- Properly cleans up timeout on completion
- Triggers AbortError that the catch handler recognizes

### Error path is now actionable:
- Old: "Network error: Failed to fetch" (mystery)
- New: "Scan timed out after 2 minutes. Yahoo is likely rate-limiting. Try again in a few minutes." with a **RETRY button**

---

## Where it's wired

Both new loaders now use the helper:

| Screen | Before | After |
|---|---|---|
| **Decide → Intraday Setups** | static text, no spinner, no timeout | full loader + 2 min timeout + retry |
| **Decide → Micro-Cap Hunter** | static text + ad-hoc bar, no timeout | full loader + 2 min timeout + retry |

Other loaders in the app (Pro Scan, Top Trades, etc.) were already using the working spinner pattern from before — those are unchanged.

---

## Pre-ship verification

- ✅ `api.py` compiles
- ✅ `app.js` + `app.min.js` syntax OK + byte-identical
- ✅ All 8 loader components present (unique ID, spinner CSS, cancel button, elapsed counter, status line, abort callback, live ticker, cleanup)
- ✅ Helper code actually executes without error (eval-tested)
- ✅ Both Intraday and Hunter use `_csLoader` + `_csFetchWithTimeout`
- ✅ AbortError properly handled with actionable message
- ✅ RETRY buttons on every error state

---

## Deploy

```bash
unzip celesys_v4_FINAL_DEPLOY.zip
cd celesys_v4_FINAL_DEPLOY/
git add -A
git commit -m "v4.62.3: Production loading states with spinner + timer + abort + 2min timeout"
git push
```

Hard-refresh after deploy.

---

## What you'll see now (instead of static text)

```
┌────────────────────────────────────────────────────────────────────┐
│ ⚡  Intraday & Swing Setups                                        │
│    SCANNING S&P 100 · ALL                                          │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│                   ⟳ (spinning)                                     │
│                                                                    │
│              Intraday & Swing Setups                               │
│         SCANNING S&P 100 · ALL TIMEFRAMES                          │
│                                                                    │
│         ████████░░░░░░░░░░░░░░░░░░░░░  (pulsing)                   │
│                                                                    │
│   Pulling 5-min bars + daily history for liquid names...           │
│                                                                    │
│         ELAPSED: 12s          ~ 45s TYPICAL                        │
│                                                                    │
│                     [ CANCEL ]                                     │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

If the scan crosses 1.5× expected (~67s for intraday), elapsed time turns amber. At 2.5× (~112s), it turns red and adds a warning: "Taking longer than usual — Yahoo may be rate-limiting. Wait or cancel."

If the scan crosses 2 minutes, it auto-aborts with a friendly error + RETRY button.

---

## Honest note

I should not have shipped a "Loading..." text-only state in r62.0 or r62.2. Other loaders in your codebase already had spinners. I had the pattern in front of me and didn't apply it. **Going forward, every new loader I write will use `_csLoader`** — it's the canonical pattern in your codebase now.

You shouldn't have to remind me about basic UX. I'll do better.

---

## What's next

If after deploying this you find any OTHER loading states still showing flat text, point me to them and I'll convert. But the two recent ones (Intraday + Hunter) were the obvious bugs.

Beyond UX:
- **r62.4** — Real backtester for the 3 setups (validate the literature base rates against your own broker fills)
- **r62.5** — Pivot Point Bounce setup added to the scanner
- **r62.6** — Polygon paid API integration ($30/mo) for reliable intraday data

None ship without your green light.
