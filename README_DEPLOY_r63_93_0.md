# 🚨 READ THIS FIRST — r63.93.0 DEPLOYMENT GUIDE

## What's broken right now (diagnosed from your Render logs)

Your Render logs show:
```
[r63.92.0] /api/dd-volume-profile ... 200 OK     ← service running latest version
GET /api/smart-money-scanner ... 404 Not Found    ← THIS ROUTE DOESN'T EXIST
```

**Conclusion: the Python file for Smart Money Scanner was NEVER added to your `api.py`.**

The .py files I've been shipping in zips are SOURCE FILES. They don't auto-install. They have to be physically integrated into your `api.py`. Until that happens, no number of redeploys will fix the 404.

## What I'm doing in this release (r63.93.0)

Making the integration as easy as possible: **2 new files in the zip root** + **4 lines you add to api.py**. That's it. No more pasting hundreds of lines into the middle of api.py.

---

## ⚡ DEPLOYMENT — exactly 5 steps

### Step 1 — Copy these 2 files into your repo

From the zip, copy these to the **SAME FOLDER as your `api.py`** in your repo (the project root):
- `smart_money_router.py`
- `earnings_router.py`

So your folder looks like:
```
celesys-repo/
├── api.py                       ← already there
├── smart_money_router.py        ← NEW (copy from zip)
├── earnings_router.py           ← NEW (copy from zip)
├── static/
│   ├── app.js
│   └── app.min.js
└── ...
```

### Step 2 — Check if you have an old earnings handler in `api.py`

Open `api.py`. Press **Ctrl-F**. Search for: `earnings-this-week`

- If you find a `@app.get("/api/earnings-this-week")` decorator with a function below it → **DELETE that entire function** (the decorator line + every line until the next `def` or `@app.` at the same indent level).
- If you find nothing → skip to Step 3.

(Skip this check for smart-money-scanner — it doesn't exist anywhere yet.)

### Step 3 — Add these 4 lines to `api.py`

**Find** the line near the top of `api.py` that says something like `from fastapi import FastAPI` or `app = FastAPI(...)`.

**At the very top of api.py, with other imports**, add:
```python
from smart_money_router import router as smart_money_router
from earnings_router import router as earnings_router
```

**Right after `app = FastAPI(...)` line**, add:
```python
app.include_router(smart_money_router)
app.include_router(earnings_router)
```

### Step 4 — Commit and push

```powershell
git add api.py smart_money_router.py earnings_router.py
git commit -m "r63.93.0: add smart money scanner + earnings router"
git push origin main
```

### Step 5 — Watch Render rebuild + verify

1. Open your Render dashboard. Watch the build log.
2. Wait for "Deploy succeeded" (~90 seconds).
3. Open this URL in your browser:
   `https://celesys.ai/api/smart-money-scanner?region=US&mcap=large`
4. **Expected**: a JSON response starting with `{"success": true, "universe_size": 100, ...}`. First request takes 30-90 seconds (yfinance fetches). Reload after a minute if the first request times out — the second hit comes from cache instantly.
5. **If you still see `{"detail":"Not Found"}`**: check the Render build log for Python errors. Most likely problems:
   - You forgot to `git add` the new .py files (most common!)
   - The `import` lines are misspelled
   - You pasted `app.include_router(...)` BEFORE `app = FastAPI(...)` — order matters

---

## If it STILL doesn't work after step 5

Take a screenshot of:
1. The first 30 lines of your `api.py` (where the imports + `app = FastAPI` live)
2. The Render build log for the failed deploy

Send both. I'll find the issue in 30 seconds.

## What lights up after this deploys

| Feature | Before | After |
|---|---|---|
| Smart Money Scanner | 404 — "Backend Not Yet Wired" | Live table with VOL 4Q + INSIDER 4Q cells populated |
| Earnings Calendar | Cisco/NVDA missing | Major companies always shown when they have earnings |
| Smart Money panel on Analyze page | Empty cards | VOL + INSIDER cells populated |

What stays empty until SEC EDGAR is wired (separate, bigger lift):
- OWN 4Q cells (needs 13F quarterly history)
- TOP HOLDERS section (needs prior-quarter 13F comparison)

That's 2 of 4 columns lighting up immediately. The other 2 come later.

---

## Why this kept failing the last 3 releases

I was shipping `_WORKING_ENDPOINT.py` files thinking pasting their entire body into the middle of `api.py` was simpler. It isn't — it's actually harder, because:
- 200 lines of code in the middle of a 25,000-line file is easy to skip / forget / paste in the wrong place
- The route-decorator approach mixes with existing routes, harder to undo

The router-module approach in this release is the standard FastAPI pattern. 2 files + 4 lines. Cleaner, safer, undoable.

That's on me — should have done it this way from r63.87.
