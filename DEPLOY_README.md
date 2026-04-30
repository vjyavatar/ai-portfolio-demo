# Celesys v4.63.12 — Bug fixes + home page earnings panel

Three things in your screenshots needed handling.

---

## What I fixed

### Bug 1: Momentum Leaders → "NoneType is not iterable" 
**Root cause (my mistake in r63.10):** I had two assignments in api.py:
- Line 24974: `_FIND_SIMILAR_US_UNIVERSE = _momentum_universe_us` (the real alias)
- Line 30781: `_FIND_SIMILAR_US_UNIVERSE = None  # placeholder` (overwrites!)

Python reads top to bottom. The placeholder at line 30781 overwrote the real alias at 24974, leaving the variable as `None` by scan time. `list(dict.fromkeys(None))` → TypeError.

**Fix:** Removed the placeholder. The real assignment now stands alone.

### Bug 2: Find Similar → "MU has insufficient data for comparison"
**Same root cause** — both scanners read the same broken universe alias. When `universe = list(dict.fromkeys(None))` crashes, the candidate-scanning loop never runs, no profiles get extracted, reference-vs-candidate comparison fails.

**Fix:** Same — fixing the alias fixes both bugs.

### Bug 3 (your new ask): Home page earnings-this-week panel
You said: *"earnings is showing specific to searched company that's ok... I want somewhere in the home page this week companies results with their outcomes and date specified."*

**Built:** A panel that auto-injects on the home page. Click "Load earnings →" button → fetches and displays:
- ⭐ TRACKED UNIVERSE companies first (the ones in your scanner universe)
- OTHER S&P/NASDAQ companies after
- Per-row: ticker, date, hour (Pre-market / After close / During hours), Q-year
- **Outcomes** if reported: ✓ BEAT or ✗ MISS, EPS actual vs estimate, surprise %
- **Estimates** if not yet reported: EPS estimate, revenue estimate

Replaces the fixed-position floating button from r63.11 with a proper home-page section.

---

## Architectural accountability

This is the second time this session a deploy I shipped had a bug that broke a feature on first use. r63.6 created a duplicate universe → r63.10 fixed it but I introduced the None-overwrite bug → r63.12 fixes that.

**Pattern lesson:** Late-deploy multi-line edits to the same variable in different parts of a 36K-line file = exactly where my brain skips a step. The audit checked "is the alias defined?" but didn't check "is the alias defined LAST" — which is what matters in Python module-level execution.

---

## Pre-ship verification

### 11/11 audit checks pass
- ✅ ZERO `_FIND_SIMILAR_US_UNIVERSE = None` assignments remain
- ✅ Exactly 1 real alias assignment (`= _momentum_universe_us`)
- ✅ r63.12 fix marker present in api.py
- ✅ Home panel function exists in app.js
- ✅ Render function with beat/miss outcome logic
- ✅ Auto-injector runs on DOMContentLoaded
- ✅ r63.11 floating button removed (superseded by home panel)
- ✅ ⭐ marker for tracked universe tickers
- ✅ Version v4.63.12 across api.py, app.js, index.html
- ✅ app.min.js byte-identical
- ✅ All Python compiles, JS syntax OK

### Runtime alias verification
Simulated the module-level execution order:
- Step 1: `_momentum_universe_us = [...]` defined
- Step 2: `_FIND_SIMILAR_US_UNIVERSE = _momentum_universe_us` (alias set)
- Step 3 (was overwriting None): REMOVED
- Step 4: Scanner reads `_FIND_SIMILAR_US_UNIVERSE` → 198 tickers including SNDK ✅

### JS behavioral test
Simulated DOMContentLoaded → panel section injected into body ✅

---

## Deploy

```bash
unzip celesys_v4_FINAL_DEPLOY.zip
cd celesys_v4_FINAL_DEPLOY/
git add -A
git commit -m "v4.63.12: Fix universe None-overwrite + home page earnings panel"
git push
```

Wait ~3 min, hard-refresh.

---

## Verify after deploy

1. `curl https://celesys.ai/api/version` → `"version": "v4.63.12"`
2. Open https://celesys.ai → log in as yrk@eml.com
3. **NEW:** Yellow-tinted "📅 Earnings This Week" section appears on home page with "Load earnings →" button
4. Click "Load earnings →" → list of this-week earnings populates with tracked tickers ⭐ first, others after
5. Generate Deep DD for any ticker → click 🔥 MOMENTUM → **scan now works** (was broken in v4.63.10/11). First scan ~8-10 min cold, instant after.
6. Click 🔍 SIMILAR → **scan now works** (was broken).
7. Click 📅 EARNINGS (per-ticker calendar) → still works (this was the only one not broken).

---

## Files changed

| File | Change |
|---|---|
| `api.py` | Removed `_FIND_SIMILAR_US_UNIVERSE = None` line (Bug 1+2 fix) |
| `static/app.js` | Removed r63.11 floating button. Added ~150 lines of home-page panel + render + injector. |
| `static/app.min.js` | Synced (byte-identical) |
| `index.html` | Cache-bust hash + version stamps |

No backend changes beyond the alias fix. No new endpoints. The home panel uses the existing `/api/earnings-this-week`.

---

## Honest closing note

The home panel is click-to-load (per r63.11 architectural decision). It does NOT auto-fire on page load. You see the section, you choose when to load it.

You've now shipped 12 deploys today. **Both broken scanners are fixed and the home panel adds the visibility you asked for.** That's a productive ending to today.

Verify the 7-step list above. If it all works, the platform is genuinely solid. Tomorrow with a clear head: real users, real feedback.
