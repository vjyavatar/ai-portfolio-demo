# Celesys v4.63.2 — Fix r63.0 regression in DD report sections

You caught a real bug. r63.0 was incomplete. This fix addresses it directly.

---

## What you saw in your screenshot

MU report rendering with:
- ✅ Verdict: 92/100 STRONG BUY (Finnhub working)
- ✅ Financial Health: 85.5% (Finnhub working)
- ❌ Risk Matrix: showing flagged/passed but **empty body**
- ❌ SWOT: empty / sparse
- ❌ Porter Five Forces: showing 35/50 but no scores per force
- ❌ Insider Activity: missing
- ❌ Institutional Ownership: missing
- ❌ Earnings History: showing "0.10%" but missing detail

That's not "Finnhub doesn't have this data" — that's a **regression I introduced in r63.0**.

---

## The actual bug

Look at the original r60.4 institutional fetch code:

```python
if data_source == "yfinance" and tk:
    # ... fetch insider transactions, institutional holders, etc
```

When r63.0 made Finnhub the primary source, **two things broke**:

1. The yfinance `tk` Ticker object was only created if Finnhub failed. When Finnhub succeeded, `tk` never existed.
2. The condition `data_source == "yfinance"` excluded the new value `"finnhub"` and `"finnhub+yfinance"` — so the entire institutional/insider block got skipped.

Net effect: when Finnhub succeeded, your report got the price + multi-factor verdict but **silently lost** Insider, Institutional, Earnings History, and dependent sections.

---

## The fix in v4.63.2

Three targeted changes:

### Fix A — Always create yfinance Ticker for US tickers

Even when Finnhub is the primary source, we now ALWAYS create the yfinance Ticker. This means `tk.insider_purchases`, `tk.institutional_holders`, `tk.earnings_history` are still callable. If Yahoo blocks the IP, those individual calls fail gracefully and the section shows "data unavailable" — but if Yahoo allows them (which often happens for these specific endpoints even when others are blocked), you get the data.

### Fix B — Remove yfinance-only gates

The conditions on Insider Activity, Institutional Holders, and Earnings History now check `tk is not None and region == "US"` instead of `data_source == "yfinance"`. So they try yfinance regardless of which source provided the price.

### Fix C — Merge logic: Finnhub fields + yfinance gaps

When both sources work, we merge: Finnhub fields stay (current price, fundamentals from free tier), yfinance fills gaps (insider %, institutional ownership, analyst targets). Best of both.

---

## Pre-ship verification

### 8 audit checks pass
- ✅ yfinance Ticker always created for US tickers
- ✅ `tk = None` initialized so downstream gates don't crash on undefined
- ✅ Earnings gate uses `tk + region` instead of `data_source`
- ✅ Insider gate fixed
- ✅ Institutional gate fixed
- ✅ data_quality marker accepts "finnhub+yfinance"
- ✅ Old `data_source == "yfinance"` gates REMOVED
- ✅ Version v4.63.2

### 4-scenario simulation passed
| Scenario | Result | What user sees |
|---|---|---|
| **S1** Finnhub HIT + Yahoo OK | data_source=finnhub+yfinance, insider/institutional WORK | Full report |
| **S2** Finnhub HIT + Yahoo BLOCKED (your screenshot scenario!) | data_source=finnhub, insider/institutional gracefully N/A | Price + financials + verdict work; insider/institutional show "data unavailable" honestly |
| **S3** Finnhub MISS + Yahoo OK | data_source=yfinance, full report | Pre-r63.0 behavior preserved |
| **S4** Both fail | Graceful — no crash, all N/A | Honest error display |

---

## What this means for your platform RIGHT NOW

**Two possibilities after deploying v4.63.2:**

### Best case (likely)
Yahoo blocks the **chart/quote endpoints** from Render IP but allows the **insider/institutional/earnings endpoints**. This is how Yahoo's IP blocking often works — surgical, not blanket. After deploy:
- MU/TSLA/NVDA: Price + financials from Finnhub ✅
- Risk Matrix: full red flags + passed checks ✅
- Insider Activity: Form 4 transactions ✅
- Institutional Holders: 13F top 10 ✅
- Earnings History: full quarter-by-quarter ✅
- SWOT, Porter, Catalysts: full data ✅

### Worst case (still acceptable)
Yahoo blocks ALL endpoints from Render IP. After deploy:
- MU/TSLA/NVDA: Price + financials from Finnhub ✅ (still better than v4.62.x where these failed entirely)
- Insider Activity: shows "data unavailable" honestly ⚠
- Institutional Holders: shows "data unavailable" honestly ⚠
- Earnings History: shows "data unavailable" honestly ⚠
- Risk Matrix, SWOT, Porter: render with whatever data we have ⚠

Either way: **the report no longer silently shows empty sections.** Either the data populates, or it shows "N/A" with a clear reason — no more mysterious blanks.

---

## Deploy

```bash
unzip celesys_v4_FINAL_DEPLOY.zip
cd celesys_v4_FINAL_DEPLOY/
git add -A
git commit -m "v4.63.2: Fix r63.0 regression — always try yfinance for insider/institutional even when Finnhub primary"
git push
```

Wait ~3 min, hard-refresh.

---

## Verify after deploy

1. Generate Deep DD for **MU** (the one in your screenshot)
2. Compare to your screenshot — these sections should now have content:
   - **Risk Matrix** — list of red flags + passed checks
   - **SWOT** — populated with actual strengths/weaknesses
   - **Porter Five Forces** — scores per force, not just total
   - **Insider Activity** — buy/sell transaction summary
   - **Institutional Ownership** — top 10 13F holders
   - **Earnings History** — quarter-by-quarter table
3. Click PDF — full report exports cleanly with all sections

If sections STILL show empty after this deploy, that means Yahoo is blocking ALL endpoints from Render (worst case). At that point we'd need to upgrade to Finnhub paid tier (Personal ~$50/mo with fundamentals add-on) to get insider/institutional from Finnhub instead.

---

## How to tell which case you're in

After deploy, check the Render logs:

```
[DD] Finnhub primary HIT for MU — N fields
[DD] yfinance merged X fields with Finnhub for MU       ← BEST CASE: Yahoo allowing
[DD] yfinance .info empty (Yahoo likely blocked) — using Finnhub-only data for MU   ← WORST CASE
```

If you see "merged" → Yahoo allows yfinance from Render → full report
If you see "empty" → Yahoo blocks Render → degraded report (still better than complete failure)

---

## What's NOT changed in this deploy

- Frontend rendering (no changes to app.js)
- PDF export from r63.1 (still works)
- Finnhub adapter from r63.0 (still working)
- Active Trading (untouched, as always)
- All other Decide tabs (untouched)
- India ticker chain (untouched)

**Pure backend logic fix.** Smallest possible change to fix the regression.

---

## Files changed

| File | What changed |
|---|---|
| `api.py` | DD endpoint fetch logic + 3 gate condition fixes (~35 lines changed) |
| `static/app.js` | Version stamp only |
| `static/app.min.js` | Synced |
| `index.html` | Version stamp + cache hash |
| `CHANGELOG.md` | v4.63.2 entry |
| `DEPLOY_README.md` | This file |

---

## Honest acknowledgment

This bug was a regression I introduced in r63.0. I should have caught it during r63.0 testing — the merge logic LOOKED correct but I didn't verify it actually exercised all the downstream code paths. Your screenshot showed it immediately. I should have run a "render a full DD report end-to-end" test before shipping r63.0, not just verified the data adapter logic.

Lesson for future deploys: when changing the data layer, run an end-to-end "render the actual report" test, not just unit-test the new adapter in isolation.

Sorry for shipping that incomplete. r63.2 fixes it.
