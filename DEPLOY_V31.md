# Smart Money v3.1 — Expanded Edition

This bundle implements **everything achievable** from the institutional spec using free data sources.

## What changed vs v3.0

### Layer 1 — Smart Money Detection (was 30%, now ~60% coverage)

| Signal | v3.0 | v3.1 |
|---|---|---|
| Insider buying | ✅ | ✅ |
| **Unusual volume vs float (RVOL)** | ❌ | ✅ NEW |
| **Float tightening (shorts covering)** | ❌ | ✅ NEW |
| **Low retail ownership measurement** | ⚠ proxy | ✅ proper |
| Institutional ownership | ⚠ static | ⚠ still static (needs SEC 13F) |
| Dark pool | ❌ | ❌ paid only |
| Options positioning | ❌ | ❌ Yahoo rate-limited |

### Layer 2 — Bottleneck Engine (was 60%, now ~90% coverage)

| Theme | v3.0 | v3.1 |
|---|---|---|
| HBM Memory | ✅ | ✅ |
| Power Infrastructure | ✅ | ✅ |
| **Cooling** | ❌ | ✅ NEW (MOD, VRT tagged) |
| Photonics | ✅ | ✅ |
| Advanced Packaging | ✅ | ✅ |
| **Transformers/Switchgear** | ❌ | ✅ NEW (HUBB, POWL, ETN) |
| **Rare Earths** | ❌ | ✅ NEW (MP, USAR, TROX, LAC) |
| AI GPU Capacity | ✅ | ✅ |
| Nuclear Baseload | ✅ | ✅ |
| **SMR (Small Modular Reactor)** | ❌ | ✅ NEW (SMR, OKLO, LEU) |
| **Defense Drones** | ❌ | ✅ NEW (KTOS) |
| **Submarine Capacity** | partial | ✅ expanded (GD, HII) |

Catalog grew from **32 stocks → 54 stocks across 28 themes**.

### Layer 3 — Before Breakout Engine (was 15%, now ~70% coverage)

| Signal | v3.0 | v3.1 |
|---|---|---|
| Revenue acceleration | ⚠ partial | ✅ proper (>20% YoY threshold) |
| **Hyperscaler mentions** | ❌ | ✅ NEW (scans `longBusinessSummary` for AWS/Azure/GCP) |
| **Government contracts** | ❌ | ✅ NEW (scans for DoD/Pentagon/DARPA/federal) |
| **AI exposure increasing** | ⚠ partial | ✅ NEW (scans for AI/ML/LLM keywords) |
| **Capacity expansion** | ❌ | ✅ NEW (heavy capex signal) |
| Rising backlog/order book | ❌ | ❌ needs earnings transcript parsing |
| Strategic partnerships | ❌ | ❌ needs news API key |

### Transparency (was 30%, now ~80% coverage)

| Feature | v3.0 | v3.1 |
|---|---|---|
| Score components breakdown | ✅ (hover SCORE) | ✅ |
| **Week-over-week Δ** | ❌ | ✅ NEW (`/api/smv3/snapshot` saves baseline) |
| **"What changed this week"** | ❌ | ✅ NEW (hover the Δ column) |
| **Signals fired list** | ❌ | ✅ NEW (10+ signals per stock, in tooltip) |
| BlackRock-level holder Δ | ❌ | ❌ needs SEC 13F scraper |

### Visualization (was 40%, now ~75%)

| Feature | v3.0 | v3.1 |
|---|---|---|
| Traffic-light SCORE pills | ✅ | ✅ |
| **Breakout chips (🚀 🏛 🤖)** | ❌ | ✅ NEW |
| **RVOL indicator** | ❌ | ✅ NEW |
| **WoW Δ column** | ❌ | ✅ NEW |
| Heatmap (sector × theme grid) | ❌ | ❌ separate frontend module |
| Radar chart per stock | ❌ | ❌ separate frontend module |

---

## Spec coverage — honest accounting

| Spec section | v3.0 | v3.1 |
|---|---|---|
| 5-column UX | 100% ✅ | 100% ✅ |
| Scoring formula | 100% ✅ | 100% ✅ |
| Layer 1 signals | 30% | **60%** |
| Layer 2 bottlenecks | 60% | **90%** |
| Layer 3 "Before Breakout" | 15% | **70%** |
| WHY NOW | 100% ✅ | 100% ✅ |
| Transparency (deltas) | 30% | **80%** |
| Visualization | 40% | **75%** |
| **Overall** | **~55%** | **~80%** |

The remaining 20% needs:
- **SEC EDGAR 13F scraper** for true institutional Δ ("BlackRock added 4%") — separate ~1-week project
- **News API key** (Finnhub/Marketaux) for partnership/contract event detection
- **Earnings transcript parsing** for backlog/order book tracking
- **Paid feeds** for dark pool + options flow

---

## DEPLOY (3 commands)

Same simple deployment as v3.0:

1. Replace these 4 files in your repo:
   - `api.py` → repo root
   - `smart_money_v3.py` → repo root
   - `static/app.js` → static/
   - `static/app.min.js` → static/

2. Push:
   ```powershell
   git add api.py smart_money_v3.py static/app.js static/app.min.js
   git commit -m "Smart Money v3.1 - expanded edition with layer-3 signals"
   git push origin main
   ```

3. Wait ~90 seconds for Render. Hard-refresh browser (Ctrl+Shift+R).

---

## NEW: Snapshot endpoint for week-over-week deltas

The WoW Δ column needs a baseline. To save the current scan as next week's comparison:

```
https://celesys.ai/api/smv3/snapshot?region=US&mcap=large
```

Run this **once a week** (or set up as a cron job). The next scan will show "+5.2" or "-3.1" Δ vs that snapshot.

You can save snapshots for any tier:
```
https://celesys.ai/api/smv3/snapshot?region=US&mcap=mid
https://celesys.ai/api/smv3/snapshot?region=IN&mcap=large
```

Snapshots are stored as JSON files on disk (Render's `/tmp` — they survive within a deploy but reset on redeploy).

To survive redeploys, you can mount a persistent volume in Render or pass an env var:
```
SMV3_SNAPSHOT_DIR=/data/smv3_snapshots
```

---

## Verify it's working

After deploy, test these URLs:

1. **Main scanner** (should return v3.1-expanded version):
   ```
   https://celesys.ai/api/smv3?region=US&mcap=large
   ```
   Look for `"spec_version": "v3.1-expanded"` in the JSON.

2. **Bottleneck catalog** (should show 28 themes, 54 stocks):
   ```
   https://celesys.ai/api/smv3/bottlenecks
   ```

3. **UI** — click **🧠 Smart Money v3** tab. You should see:
   - NEW **WoW Δ** column (empty until you save a snapshot)
   - NEW **BREAKOUT** chips column with 🚀 🏛 🤖 emoji
   - NEW **RVOL** column showing 1.0x, 1.3x, etc.
   - Hover the SM SCORE → see "Signals: inst_ownership_sweet_spot · revenue_30pct_plus · ..."

---

## Sandbox test results (with mocked yfinance)

```
MU         score= 86.5  STRONG BUY  bottleneck=HBM Memory
  breakout: hyper=3 gov=1 ai=3 rvol=1.32
  signals_fired (10): inst_ownership_sweet_spot, strong_buy_consensus,
    unusual_volume_1.32x, shorts_covering_14pct, bottleneck_HBM_Memory, ...

NVDA       score= 87.1  STRONG BUY  bottleneck=AI GPU Capacity
  breakout: hyper=3 gov=1 ai=3 rvol=1.32
  signals_fired (11)

MP         score= 82.3  STRONG BUY  bottleneck=Rare Earths   ← NEW theme
HUBB       score= 85.1  STRONG BUY  bottleneck=Transformers/Switchgear  ← NEW theme
VRT        score= 84.8  STRONG BUY  bottleneck=Datacenter Power+Cool   ← Cooling added

AAPL       score= 71.9  BUY  bottleneck=None
  why: Revenue +33% · hyperscaler exposure · government contracts · strong analyst consensus
       ← All from business-summary scan, no bottleneck mapping
```

---

## Revert if needed

```powershell
git revert HEAD --no-edit
git push origin main
```

Site returns in ~90 seconds.
