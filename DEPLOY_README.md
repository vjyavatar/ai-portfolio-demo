# Celesys v4 — r61.3 (3 bug fixes + 30-min DD cache)

You spotted 2 bugs in the screenshots. This deploy fixes both, plus adds the caching strategy you asked for.

---

## Bugs you reported

### Bug 1: Insider Activity shows 7 buys / 15 sells but **$0.00M**

That's wrong. With 22 transactions for MU over 6 months, dollar values can't all be zero.

**Root cause:** My code grabbed counts from `tk.insider_purchases` (the cleaner summary endpoint), but the dollar values are only available in `tk.insider_transactions` — and my old code skipped that parse step when summary was used.

**Fix:** Always iterate `insider_transactions` for dollar values, regardless of which source provided counts. If transactions don't parse, return `null` (frontend shows "—") instead of fake "$0.00M".

### Bug 2: Bottom Line says "0/100 AVOID" while the report header shows "100/100 STRONG BUY CANDIDATE"

Same MU report, same data, two different verdicts. That's a bug in my Bottom Line synthesis.

**Root cause:** My synthesis read `thesis["score"]` but the actual key is `thesis["investability_score"]`. Always returned 0 → always classified as AVOID.

**Fix:** Read `thesis["investability_score"]` (the correct key, with `thesis["score"]` as fallback for safety).

---

## Caching strategy you asked for

You said: *"call batch job once... complete data... and put in cache every half an hour."*

**Done.** Added 30-minute cache on the entire Deep DD endpoint:

```
Request: /api/investor-due-diligence?symbol=MU&region=US
  ├─ Cache HIT  → return cached payload instantly (no Yahoo call)
  └─ Cache MISS → fetch all data fresh → cache for 30 min → return
```

**Cache key:** `dd_v3:{region}:{symbol}` (e.g., `dd_v3:US:MU`)
**TTL:** 30 minutes (1800s)
**Bumped to v3:** invalidates old cached responses with the bugs above

**Why 30 min?** Fundamentals (margins, ROE, debt) update quarterly. Insider data updates with Form 4 filings (irregular). Sector returns update daily. 30 min is fresh enough for a research report and protects you from Yahoo rate limiting.

**Response includes:**
- `_cached: true` when served from cache
- `_cache_age_sec: <int>` so you can show "data from 12 min ago" if you want

The cache uses your existing `_smart_cache` infrastructure — same one that protects the Bottom Nav scanner. No new dependencies.

---

## What this does for Yahoo rate limiting

**Before:** Every page load (or refresh) on a Deep DD page triggered:
- 1× `tk.info`
- 1× `tk.history(period="2y")`
- 1× `tk.insider_transactions`
- 1× `tk.insider_purchases`
- 1× `tk.institutional_holders`
- 1× `tk.earnings_history`
- N× peer fetches (1× per peer)

**= ~8-15 Yahoo calls per Deep DD load.**

**After:** First load fetches once and caches. Next 30 min of loads (same ticker) = **zero Yahoo calls**. Different users hitting same ticker = same cache.

If you have 50 users looking at MU around earnings, that's 50 page loads. Old: 400-750 Yahoo calls. New: ~10-15 Yahoo calls (one initial fetch + maybe a 30-min refresh).

---

## Files changed

| File | Change |
|---|---|
| `api.py` | Insider $ value fix (Section 11.1) + Bottom Line score field fix + 30-min DD cache wrapper |
| `static/app.js` | Frontend renders "—" when $ value is null (instead of fake $0.00M) |
| `static/app.min.js` | Synced |
| `index.html` | Version hash bumped |

Everything from r61.0/r61.1/r61.2 still intact (Bottom Line, Layman blocks, all sections).

---

## Deploy

```bash
unzip celesys_v4_FINAL_DEPLOY.zip
cd celesys_v4_FINAL_DEPLOY/
git add -A
git commit -m "r61.3: Fix insider \$ values + Bottom Line score field + 30-min DD cache"
git push
```

**IMPORTANT after deploy:**
- The cache key bumped to `dd_v3` — old cached responses (with the bugs) are abandoned automatically. First load of any ticker after deploy will be slow (cache miss → fresh fetch). After that, fast.
- Hard-refresh browser (Ctrl+Shift+R) to load the updated `app.min.js?v=...`

---

## Smoke test

### TEST 1 — MU report (the failing case)

1. Open Deep DD on MU
2. Bottom Line should now show **STRONG BUY CANDIDATE** (matching the 100/100 score above)
3. Insider Activity grid should show real $ values (e.g., $4.2M sells, $1.1M buys, -$3.1M net flow) — OR "—" if MU's transactions truly didn't parse $ values

### TEST 2 — Cache verification

1. Open Deep DD on MU → first load takes 5-15s (cache miss, fresh fetch)
2. Refresh the page within 30 min → near-instant load (cache hit)
3. Check API response: `_cached: true` field present, `_cache_age_sec` shows seconds elapsed

To force a fresh fetch, wait 30+ min OR hit a different ticker first then come back.

### TEST 3 — Multiple users / tickers

Open Deep DD on AAPL, NVDA, TSLA in succession. Each first load = fresh. Second load = cached. Bottom Line verdict should always match the score in the header.

---

## Verified before packaging

- ✅ `api.py` compiles
- ✅ `app.js` and `app.min.js` pass `node --check`
- ✅ Cache HIT path returns cached payload
- ✅ Cache MISS path fetches → caches → returns
- ✅ Cache TTL is 1800s (30 min)
- ✅ Cache key v3 invalidates old cached responses
- ✅ Old buggy `thesis.get("score")` line removed
- ✅ New line reads `thesis["investability_score"]`

---

## Rollback

To revert just the cache: in `api.py`, remove the `_dd_cache_key` block at top of DD function and the `_smart_cache_set` call before return.

To revert all r61.3: restore previous `api.py`, `app.js`, `app.min.js` from r61.2.
