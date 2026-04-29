# Celesys v4.62.4 — Diagnostic fix for /api/version

This is a TINY one-purpose deploy. It does NOT fix the Yahoo blocking. It fixes my mistake from v4.61.11.

---

## What I got wrong

In v4.61.11 I claimed `/api/version` would expose `dd_disk_cache` stats. It didn't — that part of the patcher silently skipped. I told you to run `curl /api/version` and share the disk cache state, and your response (correctly) didn't have those fields.

**My fault.** The disk cache code IS in your deployment (verified — all 6 markers present in api.py), but the diagnostic endpoint was never updated to expose it.

This deploy fixes only that.

---

## What v4.62.4 changes

`/api/version` response now includes:

- `dd_disk_cache` — `{exists, size_bytes, n_entries, age_sec}`
- `memory_cache_size` — current in-memory cache entry count
- `dd_cached_tickers` — sorted list of which symbols are cached (capped at 50)
- `dd_cached_count` — total DD-related entries

That's the only change. Same TSLA "Could not retrieve data" error will still happen until we solve Yahoo IP blocking — this just lets us SEE what's going on.

---

## Deploy

```bash
unzip celesys_v4_FINAL_DEPLOY.zip
cd celesys_v4_FINAL_DEPLOY/
git add -A
git commit -m "v4.62.4: Fix /api/version to expose disk cache diagnostics"
git push
```

---

## After deploy, please run

```bash
curl https://celesys.ai/api/version
```

You should now see something like:

```json
{
  "version": "v4.62.4",
  "build_date": "2026-04-29 ...",
  "dd_disk_cache": {"exists": true, "n_entries": 8, "size_bytes": 12340, "age_sec": 1830},
  "memory_cache_size": 47,
  "dd_cached_tickers": ["AAPL", "GOOGL", "META", "MSFT", "NVDA", "TSLA", "AMZN", "JPM"],
  "dd_cached_count": 8
}
```

This output tells me:
1. Whether disk cache survived deployments
2. How many tickers ever fetched successfully (pre-seed worked or not)
3. Whether TSLA has any cached data we can fall back on

**Once you paste this back, I have actual data to make a real recommendation.** No guessing. No assumptions about what's working.

---

## What this deploy does NOT do

- Does NOT fix Yahoo blocking your IP
- Does NOT add Stooq/Finnhub/Alpha Vantage fallbacks
- Does NOT change anything user-facing
- Does NOT touch the Decide tabs, Active Trading, or anything else

Pure diagnostic instrumentation. Smallest possible change.

---

## Likely scenarios from the diagnostic output

**Scenario A: `n_entries: 0` or `dd_disk_cache: {exists: false}`**
→ Pre-seed never worked from initial deploy (Yahoo was already blocking)
→ Need to add a real fallback source (Stooq/Finnhub/Polygon)

**Scenario B: `n_entries: 5-12, dd_cached_tickers includes TSLA`**
→ Disk cache is working but TSLA's cache expired or got evicted
→ The stale-cache fallback should still work — there's a code bug

**Scenario C: `n_entries: 5-12, dd_cached_tickers does NOT include TSLA`**
→ Disk cache works for some tickers, never reached TSLA
→ Need to add TSLA to pre-seed list, or wait for Yahoo to recover

Each scenario has a different fix. I'm not going to guess between them — your `/api/version` output will tell me which.

---

## Rollback (if needed, but very unlikely)

```bash
git revert HEAD
git push
```

Only changes one endpoint. Lowest possible risk deploy.
