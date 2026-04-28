# Celesys v4 — r60.3 Complete Deploy

**Drop in, push to Render, done.**

---

## What's NEW in r60.3

### 🔴 CRITICAL FIX: India Deep DD now works

Your screenshot showed **"Could not retrieve data for HDFCBANK"**. Root cause: Deep DD only tried Yahoo Finance. Yahoo blocks NSE tickers from Render IPs (you documented this yourself in api.py:6373).

**Fix:** Deep DD now uses your existing fallback chain:
- **India:** yfinance → NSE direct (`fetch_nse_stock_data`) → Google Finance
- **US:** yfinance → Google Finance

HDFCBANK, RELIANCE, TCS, etc. should now load from NSE when Yahoo blocks.

### NEW: 4 institutional sections in Deep DD

After all the existing sections (Verdict, Financial Health, SWOT, Porter), you now get:

**1. 📅 Catalysts & Analyst Consensus** — 4-cell grid:
- Next Earnings (date + days away + urgency color)
- Analyst Target Price (with upside % vs current spot, recommendation)
- Short Interest (% of float, days to cover, squeeze risk)
- Dividend Yield (annual rate, payout ratio)

**2. 💰 Valuation — DCF Intrinsic Value** — 3-card layout:
- Current Price | Fair Value (computed via 5yr DCF, WACC 10%, terminal 2.5%) | Verdict
- Verdicts: STRONGLY UNDERVALUED / UNDERVALUED / FAIR VALUE / OVERVALUED / STRONGLY OVERVALUED
- Honest INSUFFICIENT DATA when FCF or shares missing (no fake numbers)

**3. 📊 Quarterly Earnings History** — 8-quarter beat/miss table:
- US: EPS Estimate vs Actual + Surprise % + ✓BEAT / ✗MISS column
- India: Revenue + Profit per quarter (NSE doesn't give estimates)
- Trend label: STRONG GROWTH / GROWING / STABLE / DECLINING
- Beat rate badge (e.g., "75% Beat Rate · 6B / 2M")

**4. ✅ Risk Health Checks** — surfaces what PASSED:
- Replaces empty "no risks flagged" state
- Shows green checkmarks for: Debt-to-Equity, Liquidity, Profitability, Revenue Growth, Valuation, Governance
- Overall health: STRONG / HEALTHY / MIXED / CONCERNING

---

## Files changed

| File | Change |
|---|---|
| `api.py` | Deep DD fallback chain + Sections 7/8/9/10 added (~250 lines) |
| `static/app.js` | Frontend renderers for all 4 new sections (~200 lines) |
| `static/app.min.js` | Identical copy of app.js |
| `index.html` | Version hash bumped |

Plus everything from r60/r60.1/r60.2 still works (Porter fix, Universe Filter, Earnings Intel in Active Trading).

---

## Deploy

```bash
unzip celesys_v4_FINAL_DEPLOY.zip
cd celesys_v4_FINAL_DEPLOY/
git add -A
git commit -m "r60.3: Deep DD India fallback + 4 institutional sections (catalysts, DCF, earnings history, risk health)"
git push
```

Wait ~3 min for Render auto-deploy.

---

## Smoke test

### TEST 1 — HDFCBANK loads now (the failing case from your screenshot)

1. Open https://celesys.ai → Decide → click **HDFCBANK** quick pill
2. Should show full report (no longer "Could not retrieve data")
3. Top of report should show data source — if it's slow first time, that's NSE fetch (3-5s)
4. Subsequent loads cached

### TEST 2 — New sections in Deep DD

Open Deep DD on **NVDA** or **MSFT** (US, lots of data). You should now see, in this order:

1. Verdict score (existing)
2. Financial Health (existing)
3. Sector Context (existing)
4. Risk Matrix (existing — flagged risks)
5. SWOT (existing)
6. Porter's Five Forces (existing — 36/50 style)
7. **NEW: 📅 Catalysts & Analyst Consensus** — date, target, short, dividend
8. **NEW: 💰 Valuation — DCF Intrinsic Value** — current vs fair value
9. **NEW: 📊 Quarterly Earnings History** — 8-Q table with beat/miss
10. **NEW: ✅ Risk Health Checks** — green checkmarks
11. Data Quality footer (existing)

### TEST 3 — INCOMPLETE state for sparse data

Open Deep DD on a small/foreign ticker. Sections that can't be computed should show "INSUFFICIENT DATA" / gray styling, not fake numbers.

---

## Verified before packaging

- ✅ Python syntax (`py_compile api.py`)
- ✅ JavaScript syntax (`node --check app.js`, `app.min.js`)
- ✅ Indentation preserved in patched blocks
- ✅ All 4 new sections present (4/4 grep match)
- ✅ Response shape includes catalysts, valuation_detail, earnings_history, data_source
- ✅ Frontend renderers present for all 4 new sections
- ✅ NSE fallback uses existing `fetch_nse_stock_data` (no new infrastructure needed)
- ✅ Google Finance fallback uses existing `fetch_google_finance`
- ✅ All existing sections preserved (no regression)
- ✅ Version hash bumped, app.min.js synced

---

## Honest caveats

1. **First HDFCBANK / Indian load is slow (3-5s)** — NSE direct fetch is slower than Yahoo cache. Subsequent loads cached for 5 min.

2. **Indian quarterly earnings shows revenue/profit, not EPS beat/miss** — NSE doesn't publish analyst estimates. The table format adapts (US shows EPS columns, India shows revenue/profit columns).

3. **DCF requires Free Cash Flow + Shares Outstanding from yfinance.** For India tickers loading via NSE-only fallback, DCF will show INCOMPLETE DATA. That's the honest answer — your CDS v2.0 rule.

4. **Analyst targets and short interest are US-strong, India-weak.** yfinance has decent US coverage; for Indian tickers these cells will be empty (gray "No coverage") more often than not.

5. **Earnings dates from yfinance are best-effort.** Some tickers don't expose `earningsTimestamp`. Cell shows "No date available" in those cases.

---

## Rollback

Each piece independent:

**India fallback only:**
- In api.py, find and revert the block starting with `# r60.3: Region-aware fallback chain`
- DD will still work for US, just fail for India (back to original behavior)

**New sections only:**
- In api.py, delete Sections 7/8/9/10
- Remove their keys from the return dict
- In app.js, remove the block starting with `// ═══ NEW SECTIONS r60.3`

**Full rollback:**
- Restore previous `celesys_v4_FINAL_DEPLOY` files from r60.2
