# Celesys v4.63.14 — Diagnostic: actually test what works from Render

You called me out fairly: *"Option A.. you are not testing considering all scenarios"*

You were right. I tested from this sandbox network (which has a strict allowlist that blocks almost everything) and concluded "all sources blocked." **Sandbox ≠ Render.** Different networks, different access. I should have built a diagnostic that runs on Render itself.

This deploy does that.

---

## What r63.14 ships

**A new endpoint:** `/api/diag-data-sources?symbol=MU&email=yrk@eml.com`

Tests 5 different historical price data sources from Render's actual network:

| # | Source | What I claimed earlier | What we'll learn |
|---|---|---|---|
| 1 | Finnhub `/stock/candle` | "Paid tier only" (per docs) | Real status from your free key |
| 2 | yfinance `tk.history()` | "IP-blocked from Render" | Confirmed only for insider/13F endpoints — `.history()` may work |
| 3 | Yahoo chart API direct | Untested | Different endpoint from yfinance lib |
| 4 | Stooq CSV | "Blocked from Render" | Untested from Render specifically |
| 5 | Google Finance scraper | Already in code | Cross-check |

For each: `success`, `data_points`, `sample_close`, `elapsed_ms`, `error`, `source_url`.

Plus a summary `interpretation` field that tells you which sources worked and which to wire into the momentum scanner.

---

## Why this matters

The momentum scanner requires **historical OHLCV** (1 year of daily closes per ticker). My r63.8/r63.10/r63.12 builds tried Finnhub `/stock/candle` first then yfinance fallback — got 0 qualified tickers in the screenshot you showed.

**Hypothesis options:**

1. **Finnhub candle works, my code has a bug** — the diagnostic will confirm
2. **Finnhub candle 403's, yfinance works, my fallback chain is broken** — the diagnostic will confirm  
3. **Both 403, but Yahoo direct or Stooq works** — wire those instead
4. **Everything blocked from Render** — only paid Finnhub solves it

Without the diagnostic, I'm guessing. With it, you have proof.

---

## How to use it after deploy

```bash
curl "https://celesys.ai/api/diag-data-sources?symbol=MU&email=yrk@eml.com"
```

Or from a browser if logged in. Returns JSON like:

```json
{
  "success": true,
  "symbol": "MU",
  "working_sources": ["yfinance_history", "yahoo_chart_direct"],
  "results": {
    "finnhub_candle": {"success": false, "error": "Returned None or empty", ...},
    "yfinance_history": {"success": true, "data_points": 252, "sample_close": 138.42, ...},
    "yahoo_chart_direct": {"success": true, "data_points": 252, ...},
    "stooq_csv": {"success": false, "error": "..."},
    "google_finance": {"success": true, "data_points": 1, ...}
  },
  "interpretation": "2/5 sources work. USE THE FIRST WORKING ONE for momentum scanner price history."
}
```

**Send me the output.** Then I'll wire the actual working source into the momentum scanner in r63.15. No more speculation.

---

## Pre-ship verification

### 9/9 audit checks pass
- ✅ Diag endpoint `/api/diag-data-sources` defined
- ✅ Tests all 5 sources (Finnhub candle, yfinance, Yahoo direct, Stooq, Google)
- ✅ Returns honest per-source results with timing
- ✅ Premium gate required (so it's not abusable)
- ✅ Version v4.63.14 across all files
- ✅ All Python compiles, JS syntax OK, app.min.js byte-identical

---

## Deploy

```bash
unzip celesys_v4_FINAL_DEPLOY.zip
cd celesys_v4_FINAL_DEPLOY/
git add -A
git commit -m "v4.63.14: Diagnostic — actually test data sources from Render"
git push
```

Wait ~3 min, then run:

```bash
curl "https://celesys.ai/api/diag-data-sources?symbol=MU&email=yrk@eml.com"
```

(Replace email with whatever yrk@eml.com is — your premium email)

**Send me the JSON output.** Once we know what works, r63.15 fixes the momentum scanner properly.

---

## Honest accountability

I should have done this 6 deploys ago. When the screenshot showed "Qualified: 0" I jumped to "everything is blocked, pay $50/mo or give up" instead of testing what was actually broken. That was lazy reasoning combined with conflating sandbox failures with Render failures.

You pushed back correctly. r63.14 is the diagnostic step I should have built first.

---

## Files changed

| File | Change |
|---|---|
| `api.py` | Added `/api/diag-data-sources` endpoint (~140 lines) + `import data_sources as _ds` |
| `static/app.js` | Version stamp only |
| `static/app.min.js` | Synced |
| `index.html` | Cache-bust + version stamps |

No frontend changes. No new dependencies. No production behavior change for existing features. Pure diagnostic.

---

## After this ships

1. Run `curl https://celesys.ai/api/diag-data-sources?symbol=MU&email=yrk@eml.com`
2. Send me the JSON output
3. I'll write r63.15 that wires the working source(s) into momentum scanner
4. SNDK and other rippers should appear in the next scan

That's the path forward. Diagnose first, fix correctly second. Sorry for jumping to conclusions earlier.
