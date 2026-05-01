# Celesys v4.63.15 — Fix: panel says "Sign in" even when logged in

You said: "Load earnings is not coming even after login"

You were right. Real bug. My fault. Found it and fixed it.

---

## What was wrong

My panel checked for the user's email in `window._authedEmail` and `localStorage.getItem('email')` — but the rest of your app sets the email in `window._verifiedEmail`. **I checked the wrong variable name.**

When my panel didn't find a value in either of my checked locations, it returned the "Sign in to view earnings calendar" message even though you were clearly logged in.

This bug affected **5 functions** I introduced this session:
1. `_csFindSimilarOpen()` — Find Similar scanner
2. `_csMomentumOpen()` — Momentum Leaders scanner
3. `_csEarningsCalOpen()` — Per-ticker earnings calendar
4. `_csEarningsThisWeekLoad()` — This-week banner load
5. `_csEwHomePanelLoad()` — Home page panel load (the one your screenshot exposed)

The other 4 may have been silently passing empty email to the API and getting "Premium required" errors, OR getting the email from elsewhere by coincidence. The home panel exposed it because it had a visible "Sign in" message.

---

## The fix (5 lines, one variable name change)

Before:
```javascript
var email = (window._authedEmail || window.localStorage.getItem('email') || '').trim();
```

After:
```javascript
var email = (window._verifiedEmail || window._authedEmail || window.localStorage.getItem('email') || '').trim();
```

Adding `window._verifiedEmail` as the FIRST checked location — that's where the rest of your app stores the email after login (lines 559, 570, 646 of app.js).

---

## Pre-ship verification

- ✅ 0 occurrences of the buggy `_authedEmail-only` lookup remain
- ✅ 5 occurrences of the fixed lookup chain present
- ✅ All Python compiles, JS syntax OK
- ✅ app.min.js byte-identical to app.js
- ✅ Version v4.63.15 across api.py, app.js, index.html

---

## Deploy

```bash
unzip celesys_v4_FINAL_DEPLOY.zip
cd celesys_v4_FINAL_DEPLOY/
git add -A
git commit -m "v4.63.15: Fix login detection — use window._verifiedEmail (was _authedEmail)"
git push
```

Wait ~3 min, hard-refresh.

---

## Verify after deploy

1. `curl https://celesys.ai/api/version` → `"version": "v4.63.15"`
2. Open https://celesys.ai → log in as yrk@eml.com
3. Yellow Earnings This Week panel should now show:  
   **"Tracked companies · click to load reports + outcomes"** (NOT "Sign in")
4. Click "Load earnings →" → should fetch and show the list

Plus you can now run the diagnostic from r63.14:

```bash
curl "https://celesys.ai/api/diag-data-sources?symbol=MU&email=yrk@eml.com"
```

(Both r63.14 and r63.15 ship in this zip.)

---

## Honest accountability

This is exactly the kind of bug that happens when I write code WITHOUT looking at how the rest of the app does it. I made up a variable name (`_authedEmail`) that I assumed would be set, instead of checking what your app actually uses (`_verifiedEmail`).

The audit checks I write don't catch this class of bug because they check structural correctness (does the function exist? does it compile?) not integration correctness (does it interoperate with the rest of the app?). That requires reading sibling code.

Same root cause as several other bugs today: I rushed without grounding in the existing codebase.

---

## What this deploy contains

| Component | Status |
|---|---|
| r63.14 diagnostic endpoint `/api/diag-data-sources` | Still here, ready to run |
| r63.13 yellow-tinted home panel | Still here, with login fix |
| r63.12 universe alias fix | Still here |
| r63.11 click-to-load semantics | Still here |
| r63.15 login detection fix | NEW |

After this deploys, please:
1. Hard-refresh
2. Confirm the panel says "Tracked companies · click to load" (not "Sign in")
3. Run the r63.14 diagnostic and send me the JSON output

That diagnostic output is what lets me fix the momentum scanner properly — it'll tell us whether yfinance.history(), Yahoo direct, or Stooq actually work from Render. Then r63.16 wires the working source.
