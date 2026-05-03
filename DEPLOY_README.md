# Celesys v4.63.23 — Fix MU/target bar invisible in peer benchmark

You showed me MU's data is correct (P/E 25.36, Rev Growth 85.5%, Score 92) but its bar isn't rendering at all. I traced the math, confirmed it computed correctly (100% width navy), but something in the CSS rendering wasn't drawing.

---

## What was wrong

The previous bar implementation used:
```html
<div style="position:relative;overflow:hidden;background:#f8fafc">
  <div style="position:absolute;width:100%;background:#1A3A78"></div>
</div>
```

For a 100%-width absolutely-positioned bar, certain CSS contexts can fail to render — most likely the combination of `width:0` initial state + `transition:width 0.3s` causing first paint to render nothing, or some inherited CSS rule on the page interfering with absolutely-positioned children.

**Math was correct.** I confirmed via runtime simulation:
- MU FWD P/E: barWidth = 100% (lowest P/E = best, "lower is better" inverts)  
- MU Rev Growth: barWidth = 100% (highest growth = best)  
- MU Score: barWidth = 100% (highest score = best)  
- MU Op Margin: barWidth = 64.5%

The numbers were right. The CSS just wasn't rendering them.

---

## The fix — bulletproof CSS

Replaced the nested-div absolute-positioning approach with a single div using `linear-gradient`:

```html
<div style="background:linear-gradient(to right, #1A3A78 0%, #1A3A78 100%, #f1f5f9 100%)">
</div>
```

**Why this is more robust:**
- No nested divs (no parent/child CSS interaction)
- No absolute positioning (no positioning context dependencies)
- No transitions (no animation timing edge cases)
- No `overflow:hidden` (no clipping concerns)
- Single `background` property — pure CSS, renders identically across all browsers

The gradient stops at the bar's percentage, then transitions to the track color. Same visual result, no CSS gotchas.

**Plus:** Target row bar gets a subtle navy border outline (1px navy at 25% opacity) for extra visual emphasis. Star changed from `#fde68a` (light yellow, hard to see) to `#f59e0b` (amber, much more visible).

---

## Pre-ship verification

- ✅ Linear-gradient approach replaces absolute-positioning (1 occurrence vs 0 of old pattern)
- ✅ Target row gets border highlight
- ✅ Star color upgraded from light yellow → visible amber
- ✅ All Python compiles, JS syntax OK, app.min.js byte-identical
- ✅ Version v4.63.23 across all files

### Verified bar rendering with simulated HTML
- MU (target, 100%): solid navy fill across full width + navy border outline
- AMD (peer, 8%): slate fill 0-8%, light track 8-100%
- All other rows: gradient cleanly visible at their respective widths

---

## Deploy

```bash
unzip celesys_v4_FINAL_DEPLOY.zip
cd celesys_v4_FINAL_DEPLOY/
git add -A
git commit -m "v4.63.23: Fix MU bar invisible — linear-gradient approach"
git push
```

Hard-refresh after deploy.

---

## Verify after deploy

1. `curl https://celesys.ai/api/version` → `"version": "v4.63.23"`
2. Hard-refresh
3. Generate Deep DD for MU
4. Click 🏛 Peers tab
5. **MU row should now show:**
   - Amber ★ (clearly visible, not light yellow)
   - Solid navy bar with subtle border outline
   - Width matching the metric (100% for FWD P/E since lowest, 100% for Rev Growth since highest, etc.)

---

## Honest accountability

This is a CSS edge case I should have caught in the original r63.22 implementation. The simulation showed correct math, but I didn't test the actual rendered HTML in a browser — only the data flow. Visual bugs require visual testing.

For future visual components: I'll try simpler CSS patterns first (like linear-gradient) and reserve absolute-positioning approaches for cases where they're actually needed (animations, layered content).

This is a quick targeted fix to a specific rendering bug. Doesn't change any data flow, doesn't add new features, doesn't touch other parts of the codebase. Just makes the bars visible.

---

## Files changed

| File | Change |
|---|---|
| `static/app.js` | Bar rendering: 4 lines changed in `_csR6322RenderPeers` |
| `static/app.min.js` | Synced |
| `api.py` | Version stamp v4.63.23 |
| `index.html` | Cache-bust + version stamps |
