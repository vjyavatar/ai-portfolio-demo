# Celesys v4 — r60 Complete Deploy Package

**This is the complete project. Drop-in replacement for your r59 build.**

## What to do

1. **Unzip this folder** somewhere
2. **Replace your existing celesys repo files** with these (or just commit the whole folder as a new version)
3. **Push to Render** — that's it

```bash
# Example deploy flow:
unzip celesys_v4_FINAL_DEPLOY.zip
cd celesys_v4_FINAL_DEPLOY/
git add -A
git commit -m "r60: Porter Five Forces fix + centralized universe classifier"
git push
```

Render auto-deploys on push. Wait ~3 minutes, then smoke-test below.

---

## What's in here

The complete celesys codebase, identical to your r59 build, except:

| File | Status | What changed |
|---|---|---|
| `api.py` | **MODIFIED** | Porter Five Forces fix (line ~28204) + UC import (line 20) + 3 new UC routes (line ~29924) |
| `static/app.js` | **MODIFIED** | Porter Five Forces frontend handles null scores + INCOMPLETE/PARTIAL badges (line ~11900) |
| `static/app.min.js` | **MODIFIED** | Identical copy of `app.js` (per your build rule) |
| `universe_classifier.py` | **NEW FILE** | 755 tickers classified across IN/US in LARGE/MID/SMALL/MICRO/ETF/INDEX |
| `index.html` | **MODIFIED** | Version hash bumped (forces browser cache refresh) |
| Everything else | unchanged | identical to r59 |

---

## Verified before packaging

- ✅ `api.py` compiles cleanly (`python -m py_compile`)
- ✅ `universe_classifier.py` loads 755 tickers (IN: 366, US: 389)
- ✅ `start.py` compiles cleanly
- ✅ Porter backend patch present (1 occurrence)
- ✅ UC import present (1 occurrence)
- ✅ UC routes present (3 occurrences: `/api/universe`, `/api/universe-classify`, `/api/universe-stats`)
- ✅ Porter frontend patch present (1 occurrence)
- ✅ `app.js` and `app.min.js` byte-identical (your existing build rule)

---

## Smoke test after deploy

```bash
# 1. Universe classifier health
curl 'https://celesys.ai/api/universe-stats'
# Expected: {"IN": {"LARGE": 101, "MID": 118, ...}, "US": {...}, "total": 755}

# 2. Get all US large caps
curl 'https://celesys.ai/api/universe?region=US&tier=LARGE'
# Expected: ~100 tickers including AAPL, MSFT, NVDA, GOOGL

# 3. Classify a single ticker
curl 'https://celesys.ai/api/universe-classify?ticker=IONQ&region=US'
# Expected: {"tier": "MICRO", "source": "static"}

# 4. Visual: Porter Five Forces fix
# Open celesys.ai → Deep DD on a high-margin name (NVDA, MSFT)
# Industry Attractiveness should show 30-45/50 with all 5 force bars
# (NOT the previous 52/50 broken display)

# 5. Visual: Porter on low-data ticker
# Open Deep DD on a sparse-data ticker
# Should show "—" gray bars for missing forces + PARTIAL/INCOMPLETE badge
# (NOT fake 5/10 baselines)
```

---

## What was fixed

### 1. Porter Five Forces "52/50" math bug

**Before:** `industry_attractiveness = 50 - (porter_total - 25)` could produce 25-70 but display said "/50". Sum of 23 → output 52. Mathematically impossible.

**After:** `industry_attractiveness = max(0, min(50, round(50 - avg * 5, 1)))` properly bounded 0-50.

### 2. Porter Five Forces fake baselines

**Before:** 4 of 5 forces hard-coded to score=5 with notes like "Generic baseline". Violated your CDS v2.0 "no fake assumptions" rule.

**After:** Each force computed from real fundamentals:
- **Supplier Power** → from gross margin
- **Buyer Power** → from operating margin
- **Competitive Rivalry** → from peer count + revenue growth + op margin
- **Threat of Substitution** → from gross margin + sector
- **Threat of New Entry** → from gross margin + ROE

When data is missing, force returns `score=null` and frontend renders gray "—" rows instead of fake bars. Below 3 real forces → `INCOMPLETE_DATA` verdict.

### 3. Centralized Universe Classifier

**Before:** Ticker classification (large/mid/small/micro) duplicated across 4+ endpoints. Inconsistent. Hard to update.

**After:** Single `universe_classifier.py` module. Three new endpoints:
- `GET /api/universe?region=US&tier=LARGE` — get ticker list
- `GET /api/universe-classify?ticker=X&region=US` — classify single ticker
- `GET /api/universe-stats` — counts per region per tier

Use from anywhere in the codebase:
```python
from universe_classifier import UC
UC.classify("AAPL", "US")              # → "LARGE"
UC.get("US", "LARGE")                   # → ['AAPL', 'MSFT', ...]
UC.bucket_tickers(["AAPL","IONQ"], "US")  # → {'LARGE': ['AAPL'], 'MICRO': ['IONQ']}
```

---

## Rollback

Each fix is independent:

- **Porter rollback only:** revert `api.py` and `static/app.js` to your previous version
- **UC rollback only:** delete `universe_classifier.py` and remove `from universe_classifier import UC` from `api.py` line 20
- **Full rollback:** revert all 4 files to your r59 build

The 3 new UC routes can be removed without affecting any existing functionality — nothing currently depends on them yet.

---

## What's NOT in this deploy

These are deferred to keep this deploy focused and low-risk:

- **Refactor of /api/top-picks, /api/multibagger-hunter, /api/early-momentum-radar, /api/microcap-challenge** to consume UC. Their existing hardcoded lists still work. Migrate one endpoint at a time in subsequent deploys.
- **Tiered scanner** (NIFTY 500 / S&P 500 cold scan): builds on UC. Ship UC first, layer the scanner on top in r61.
- **Earnings Move Intelligence** (from earlier conversation): also deferred. Layer on top once UC is verified working in production.

This deploy ships ONLY the Porter fix + UC infrastructure. Two changes. Provable. Reversible.
