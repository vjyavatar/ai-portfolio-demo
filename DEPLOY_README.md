# Celesys v4.61.10 — Production Deploy

**Single canonical version: `v4.61.10`** — stamped in 7 places so you always know what's running.

---

## How to verify deployed version

After pushing, verify with any ONE of these:

```bash
# From terminal:
curl https://celesys.ai/api/version
# → {"version": "v4.61.10", "build_date": "2026-04-29 03:10:46 UTC", ...}
```

```js
// From browser DevTools console (F12):
window.CELESYS_VERSION
// → "v4.61.10"
```

**Or just look at the bottom-right corner of any page** — there's a tiny `v4.61.10` stamp.

If you see an older version, your browser cached old JS. Hard-refresh: **Ctrl+Shift+R**.

---

## What's in v4.61.10 (cumulative summary)

Every r61.x improvement bundled:

| Feature | Source |
|---|---|
| ✅ Aladdin-grade DD entry page (replaces ugly purple-box screen) | r61.8 |
| ✅ Stale-cache fallback (7-day) — survives Yahoo rate-limiting | r61.8 |
| ✅ Multi-factor Bottom Line (10 weighted factors) | r61.7 |
| ✅ Layman PLAIN + NOTE blocks on all 16 sections | r61.7 |
| ✅ Combined Institutional Summary + 5 sub-cards | r61.6 |
| ✅ Earnings Intel friendly messages | r61.5 |
| ✅ Split institutional layman with specific numbers | r61.4 |
| ✅ Insider $ values fix | r61.3 |
| ✅ Bottom Line score field fix | r61.3 |
| ✅ 30-min DD cache | r61.3 |
| ✅ Insider 0/0 NEUTRAL bug fix | r61.2 |
| ✅ Layman + Bottom Line foundation | r61.1 |
| ✅ Design system (`celesys-ds.css`) | r61.0 |
| ✅ 6 institutional sections in DD | r60.4 |
| ✅ Catalysts + DCF + Earnings History + Risk Matrix v2 | r60.3 |
| ✅ Earnings Move Intelligence + Universe Filter | r60.2/r60.1 |
| ✅ Porter formula fix + Universe Classifier | r60.0 |

See `CHANGELOG.md` for full history.

---

## What's NOT enabled

- 🔇 **r61.9 Deep DD report sidebar shell** — built but disabled by default (untested on real data). Enable in DevTools: `window._csDdShellEnabled = true; loadDeepDD();`
- ❌ Other Decide screens (Top Trades, PMS, Pro Scan) — left untouched per your request
- ❌ Active Trading — left untouched per your request

---

## Files in this zip

```
celesys_v4_FINAL_DEPLOY/
├── api.py                    (33K+ lines — APP_VERSION + /api/version added)
├── data_sources.py           (region-aware fallback layer)
├── earnings_intel.py         (with friendlier INCOMPLETE messages)
├── universe_classifier.py    (755 tickers IN+US classified)
├── start.py
├── index.html                (meta tag + footer stamp + cache-bust)
├── DEPLOY_README.md          (this file)
├── CHANGELOG.md              (full version history)
└── static/
    ├── app.js                (~22K lines — version banner on load)
    ├── app.min.js            (byte-identical to app.js)
    ├── active-trading.js     (~13K lines — v53 marker)
    ├── options-engine.js     (untouched)
    ├── premium-override.js   (untouched)
    ├── celesys-ds.css        (design system tokens)
    └── celesys-ds-preview.html  (visible at /ds-preview)
```

---

## Pre-ship verification

All passed before packaging:
- ✅ `api.py`, `data_sources.py`, `earnings_intel.py`, `universe_classifier.py`, `start.py` — all compile
- ✅ `app.js`, `app.min.js`, `active-trading.js`, `options-engine.js`, `premium-override.js` — all pass `node --check`
- ✅ `app.min.js` byte-identical to `app.js`
- ✅ `APP_VERSION = "v4.61.10"` in api.py
- ✅ `window.CELESYS_VERSION = "v4.61.10"` in app.js
- ✅ `/api/version` endpoint returns v4.61.10
- ✅ Footer stamp visible
- ✅ Cache-bust version hash bumped (forces browser refresh)

---

## Deploy

```bash
unzip celesys_v4_FINAL_DEPLOY.zip
cd celesys_v4_FINAL_DEPLOY/
git add -A
git commit -m "v4.61.10 production: cumulative r61.x — Aladdin entry + stale cache + multi-factor verdict + complete layman"
git push
```

Wait ~3 min for Render to build. Then **hard-refresh** browser (Ctrl+Shift+R).

Verify deployment:
```bash
curl https://celesys.ai/api/version
```
Expected: `{"version": "v4.61.10", ...}`

---

## After deploy — what should look different

### Decide → Deep DD (entry page)
**OLD:** Big "Deep Due Diligence" white card + purple "What you get" box + tiny ticker input
**NEW:** Compact navy DD badge header + 2-col layout (bold input on left, scope sidebar on right)

### Decide → Deep DD (after generating report on, say, MU)
- 🎯 Bottom Line at top with composite score breakdown (shows `37/100 HOLD/SELECTIVE` for MU now, not the misleading `100/100 STRONG BUY`)
- PLAIN + NOTE blocks at top of every section
- 🏛 Institutional Summary card before 5 sub-cards
- Yellow STALE banner at top if Yahoo is rate-limiting (instead of hard error)
- Insider Activity shows real $ values, not $0.00M

### Footer (every page)
- Tiny `v4.61.10` stamp bottom-right corner

### DevTools Console (every page load)
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 CELESYS v4.61.10  loaded · 2026-04-29 03:10:46 UTC
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[ActiveTrading] v53 loaded — v4.61.10 — Bundled with cumulative r61.x improvements
```

---

## If something looks wrong after deploy

1. **Verify version actually deployed:**
   ```bash
   curl https://celesys.ai/api/version
   ```
   If it shows old version, the push didn't go through.

2. **Verify browser isn't cached:**
   - Open DevTools → Network tab → reload
   - Look at `app.min.js` — should show fresh download, not "(disk cache)"
   - If still cached: Ctrl+Shift+R to hard-refresh, or clear browser data for celesys.ai

3. **Send screenshot + console:**
   If still wrong, send a screenshot showing the page + DevTools Console (F12 → Console tab). Console errors are how I diagnose.

---

## Rollback

```bash
git revert HEAD
git push
```

To disable r61.9 shell at runtime (already disabled by default in this build):
```js
window._csDdShellEnabled = false;
```

---

## Next steps (when you're ready)

If everything looks good after this deploy, I can build:
- **r62.0** — Apply Aladdin design system to other Decide screens (Top Trades, Top Investments, etc.)
- **r62.x** — Active Trading rebuild (separate, careful, toggleable)
- **r62.x** — Background pre-warmer for Yahoo (so cold caches aren't cold)

But none of those happen unless you ask. Cumulative is shipped, version is stamped, you're in control.
