# Celesys v4 — r60.1 Complete Deploy

**This zip is the complete project. Drop in, push to Render, done.**

---

## What's NEW in r60.1 (this deploy)

### Universe Filter Bar in Active Trading

**Where it appears:** Decide tab → Active Trading → directly under the header strip (between the "CELESYS · ACTIVE TRADING / IN/US/SPY/QQQ" header and the "TOP TRADES" cards).

**What it shows:**
```
UNIVERSE  [ ALL 102 ]  [ LARGE 102 ]  [ MID 147 ]  [ SMALL 83 ]  [ MICRO 17 ]  [ ETF 35 ]   102 tickers · US
```

**What it does:**
- Shows the live universe count for the current region
- Click any pill to filter (e.g., click MICRO to show only IONQ-style names)
- Click again or click ALL to deselect
- Auto-refreshes when you switch IN ↔ US
- Cached client-side (one fetch per region)

The filter exposes `window._celesysUniverseFilter(symbols)` — any other render function can call it to apply the active filter.

---

## Files changed in this deploy

| File | Change |
|---|---|
| `static/active-trading.js` | + Universe Filter Bar component, mounted under header, v50 |
| `index.html` | Version hash bumped (forces browser cache refresh) |

Plus everything from r60 (Porter fix + universe classifier backend) which was already deployed.

---

## How to deploy

```bash
unzip celesys_v4_FINAL_DEPLOY.zip
cd celesys_v4_FINAL_DEPLOY/

# Replace your existing repo contents with these files
git add -A
git commit -m "r60.1: Universe Filter Bar in Active Trading"
git push
```

Render auto-deploys. Wait ~3 min. Smoke test below.

---

## Smoke test after deploy

### 1. Visual — Universe Bar in Active Trading

Open https://celesys.ai → Decide → Active Trading

You should see, just below the header (CELESYS · ACTIVE TRADING / IN US / SPY QQQ IWM ...):

```
UNIVERSE  [ ALL 102 ]  [ LARGE 102 ]  [ MID 147 ]  [ SMALL ##]  [ MICRO ## ]  [ ETF ## ]
```

Click the **MICRO** pill — it should highlight blue and stay selected. Click again to deselect.

### 2. Console log — v50 confirmation

Open browser DevTools console (F12) and look for:

```
[ActiveTrading] v50 loaded — Universe Filter Bar added
```

If you see `v49` instead, hard-refresh the page (Cmd+Shift+R / Ctrl+Shift+F5).

### 3. Universe API endpoints (already verified working in r60)

```bash
curl 'https://celesys.ai/api/universe-stats'
curl 'https://celesys.ai/api/universe?region=US&tier=LARGE'
curl 'https://celesys.ai/api/universe-classify?ticker=IONQ&region=US'
```

### 4. Porter Five Forces fix (from r60)

Open Deep DD on a high-margin name (NVDA, MSFT). Industry Attractiveness should show 30-45/50 (NOT 52/50).

---

## Verified before packaging

- ✅ `api.py` compiles cleanly
- ✅ `universe_classifier.py` loads 755 tickers
- ✅ `static/active-trading.js` JS syntax OK (node --check)
- ✅ `static/app.js` JS syntax OK
- ✅ Universe bar function defined exactly once
- ✅ Mount call present after `renderHeader()`
- ✅ Version hashes bumped in `index.html`
- ✅ v50 console log marker present

---

## Rollback

If the universe bar breaks anything:
- In `static/active-trading.js`, remove the line `wrap.appendChild(renderUniverseBar());` (around line 5238)
- That disables the UI without removing code

If you want to fully revert:
- Restore the previous `static/active-trading.js` from your r60 deploy
- Bump `index.html` `?v=` parameter to bust browser cache

---

## What's NOT done in this deploy

Same as r60 — these are deferred:

- **Refactor of /api/top-picks, /api/multibagger-hunter, /api/early-momentum-radar, /api/microcap-challenge** to consume the universe classifier
- **Tiered scanner** (NIFTY 500 cold scan)
- **Earnings Move Intelligence widget**
- **Hooking the universe filter into the secondary scanner** — currently the filter pill highlights but doesn't yet filter the bottom scanner table. That's the next small step.

This deploy ships ONLY the visible Universe Filter Bar UI on top of the r60 backend. Provable. Reversible.
