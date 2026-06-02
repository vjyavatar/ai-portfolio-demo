# 🚀 r63.93.1 — DEPLOY IN 3 COMMANDS

You don't need to edit `api.py` by hand anymore. There's a script that does it.

## What's still broken (from your logs)

`/api/smart-money-scanner` returns 404 because `api.py` has not been edited to register the new routes. Your other endpoints work — the service is healthy. The new routes just aren't loaded yet.

## How to fix (3 commands, ~2 minutes)

### Step 1 — Get all 3 files into your repo

From this zip, copy these to the **same folder as `api.py`**:
- `smart_money_router.py`
- `earnings_router.py`
- `install_routers.py`

### Step 2 — Run the installer

In a terminal, from the folder containing `api.py`:
```powershell
python install_routers.py
```

The script will:
- ✅ Verify the files are in the right place
- ✅ Make a backup at `api.py.backup`
- ✅ Add the import lines next to your existing imports
- ✅ Add the `app.include_router()` calls right after `app = FastAPI(...)`
- ✅ Verify the result still parses as valid Python
- ✅ Tell you exactly what was changed

Running it twice is safe — it detects already-installed routers and skips.

### Step 3 — Commit and push

```powershell
git add api.py smart_money_router.py earnings_router.py
git commit -m "r63.93.1: register smart-money + earnings routers"
git push origin main
```

Wait ~90 seconds for Render to redeploy. Then verify:

Open this URL: `https://celesys.ai/api/smart-money-scanner?region=US&mcap=large`

You should see JSON starting with `{"success": true, "universe_size": 100, ...}` — first call takes 30-90 seconds.

## If anything goes wrong

The script makes a backup before touching anything. Restore it with:
- Windows: `copy api.py.backup api.py`
- Mac/Linux: `cp api.py.backup api.py`

Then send me:
- The full output of `python install_routers.py`
- The first 20 lines of your `api.py`

I'll find the issue in one round.

## Why this approach is different

Last 4 releases I asked you to manually paste 200 lines into `api.py`. That kept failing — either the paste was never done, or it happened in the wrong place. The script removes that entire failure mode. It finds `app = FastAPI(...)` automatically and adds exactly 4 lines.
