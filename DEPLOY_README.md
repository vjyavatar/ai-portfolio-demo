# Celesys v4 — r61.2 (Insider Activity bug fix)

**You spotted a bug. This deploy fixes it.**

---

## What you reported

Your screenshot showed:
> Insider Activity · NEUTRAL · BUYS: 0 · SELLS: 0 · NET FLOW: +$0.00M

That's not "no insider activity" — that's a parse failure being rendered as if it were real data.

---

## Root cause (two bugs)

### Bug 1: yfinance column-name mismatch

The `tk.insider_transactions` DataFrame returns different column names depending on yfinance version:
- Some versions: `Shares`, `Value`, `Position`
- Other versions: `Shares Traded`, `Total Value`, `Relation`

My old code looked for `"Shares"` only. When the column was actually named `"Shares Traded"`, every row returned `None` → 0 buys, 0 sells. The DataFrame wasn't empty so the parser thought it was working.

### Bug 2: Wrong default sentiment

When buys=0 and sells=0, my old code hit this branch:
```python
"NEUTRAL" if buys == sells   # ← matches 0 == 0
```

So it displayed **NEUTRAL** with all zeros instead of marking the data as INCOMPLETE.

---

## What this deploy fixes

**Backend (api.py):**
1. **Two-strategy data fetch** — tries `tk.insider_purchases` (cleaner summary endpoint with rows: Purchases / Sales / Net / Total / Net%) FIRST, falls back to `tk.insider_transactions` for transaction details
2. **Robust column detection** — accepts multiple column-name aliases (`Shares` OR `Shares Traded` OR `Quantity`; `Value` OR `Total Value`; `Position` OR `Relation` OR `Title`)
3. **Honest INCOMPLETE state** — if both endpoints return empty AND parser yields 0/0, mark `data_quality: INCOMPLETE` with a real reason instead of fake NEUTRAL

**Frontend (app.js):**
1. **Defensive INCOMPLETE check** — even if backend somehow returns 0 buys + 0 sells with "FULL" quality, frontend re-classifies as INCOMPLETE
2. **No fake grid** — when INCOMPLETE, you see the explanation, not a 0/0/+$0.00M grid

---

## What you'll see after deploy

For tickers WITH insider activity (NVDA, AAPL, TSLA):
- Real buy/sell counts pulled from the cleaner `insider_purchases` summary
- Sentiment based on actual ratios (BUYING/SELLING/STRONG variants)
- Grid only renders when there's real data

For tickers WITHOUT insider activity (or with parse failure):
- Clean INCOMPLETE state with reason like *"No insider buy/sell transactions found in last 6 months. This is common for stocks where insiders only receive equity grants."*
- No fake 0/0 grid

For India tickers loaded via NSE fallback:
- Shows promoter holding % (the only insider-style data NSE provides)
- Marks PARTIAL with explanation

---

## Files changed

| File | Change |
|---|---|
| `api.py` | Section 11.1 rewrite — two-strategy fetch + robust column detection |
| `static/app.js` | Defensive INCOMPLETE re-classification in insider render block |
| `static/app.min.js` | Synced |
| `index.html` | Version hash bumped |

Everything else from r61.1 (Bottom Line, Layman blocks) preserved.

---

## Deploy

```bash
unzip celesys_v4_FINAL_DEPLOY.zip
cd celesys_v4_FINAL_DEPLOY/
git add -A
git commit -m "r61.2: Fix Insider Activity 0/0 NEUTRAL bug — robust yfinance column handling"
git push
```

Wait ~3 min, hard-refresh the page (Ctrl+Shift+R), open Deep DD on a US stock with known insider activity (NVDA, AAPL, TSLA, MSFT) → should now show real numbers.

---

## Smoke test

### TEST 1 — Stock with active insider trading (e.g. AAPL or TSLA)

Open Deep DD on AAPL → scroll to Insider Activity →
- Should show real buy/sell counts (typically 5-30 transactions over 6 months)
- Sentiment should be BUYING or SELLING based on ratio
- Net flow should be a non-zero $ amount

### TEST 2 — Stock with no insider activity (small/foreign)

Open Deep DD on a less-covered ticker →
- Should show INCOMPLETE state with explanatory text
- NO 0/0/+$0.00M grid
- Layman block from r61.1 still appears

### TEST 3 — India ticker (via NSE fallback)

Open Deep DD on HDFCBANK or RELIANCE →
- Should show promoter holding % with PARTIAL badge
- Honest message: "NSE provides promoter % but not transaction-level data"

---

## Verified before packaging

- ✅ `api.py` compiles
- ✅ `app.js` JS syntax OK
- ✅ `app.min.js` byte-identical to `app.js`
- ✅ Logic tested against 3 scenarios: valid summary data / empty data / alternate column names — all behave correctly
- ✅ Existing r61.1 layman blocks untouched
- ✅ Existing Bottom Line synthesis untouched

---

## Rollback

If anything breaks, revert these 4 files from the previous deploy:
- `api.py`
- `static/app.js`
- `static/app.min.js`
- `index.html`
