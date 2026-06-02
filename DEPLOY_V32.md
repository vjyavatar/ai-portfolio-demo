# Smart Money v3.2 — Layman Edition

## What's new in v3.2

Same v3.1 engine — but the UI now **explains itself in plain English**.

### Three changes for understandability

**1. Collapsible explainer panel at the top** ("📖 How to read this scanner")

Opens automatically on first visit. Explains every column in plain English:

> **SM SCORE (0–100)** — overall verdict. Higher = better. ≥75 is STRONG BUY, ≥60 BUY, ≤30 AVOID.
>
> **ACCUM** — institutional accumulation strength.
> • **Aggressive** = big money is piling in hard
> • **Moderate** = steady buying
> • **Weak** = no clear institutional interest
>
> **STAGE** — where the stock is in its run.
> • **Early** = forming a base, room to run
> • **Expansion** = trending up, sweet spot
> • **Crowded** = near highs, late-stage, careful
>
> **BOTTLENECK** — the supply-constraint story (e.g. HBM Memory, AI GPUs). Stocks with bottlenecks have *pricing power*. Higher severity = stronger story.
>
> **BREAKOUT** — early-warning emoji chips:
> 🚀 mentions hyperscalers (AWS/Azure/GCP)
> 🏛 has government / DoD contracts
> 🤖 strong AI exposure
> 📉 shorts covering (squeezable)
> 🏗 expanding capacity
>
> **RVOL** — relative volume vs 3-month average. Above 1.3x = unusual interest.

Plus a "🎯 How the BUY decision is made" section showing:
- The 5-component weighted formula (30/25/20/15/10)
- All 5 verdict tiers with example explanations
- An honest caveat: "screening tool, not financial advice"

**2. Plain-English subtitles under each label in the table**

| Technical label | Layman subtitle |
|---|---|
| SM SCORE 88 | "top tier" |
| SM SCORE 65 | "solid" |
| SM SCORE 50 | "neutral" |
| **STRONG BUY** | "all signals aligned" |
| **BUY** | "worth a starter" |
| **HOLD** | "mixed signals" |
| **TRIM** | "signals weakening" |
| **AVOID** | "major red flags" |
| Aggressive | "heavy buying" |
| Moderate | "steady interest" |
| Weak | "no clear signal" |
| Early | "room to run" |
| Expansion | "trending up" |
| Crowded | "near highs, careful" |

So a stock card now reads naturally: *"MU · STRONG BUY · all signals aligned · Aggressive heavy buying · Expansion trending up · HBM Memory severity 95"*

**3. Auto-opens on first visit, collapses on return**

Uses `localStorage.smv3_help_seen` so users only see the full explainer the first time. Click the summary to re-open it any time.

---

## DEPLOY (same as before — only 2 files changed)

Since v3.2 only changes the frontend, you can ship a tiny diff:

1. Replace these 2 files in your repo:
   - `static/app.js`
   - `static/app.min.js`

2. Push:
   ```powershell
   git add static/app.js static/app.min.js
   git commit -m "Smart Money v3.2 - layman-friendly explainer"
   git push origin main
   ```

Wait ~90 seconds for Render. **Hard-refresh (Ctrl+Shift+R)** to clear cached JS.

---

## What you'll see

When you click **🧠 Smart Money v3** tab:

1. A blue "📖 How to read this scanner" box at the top (auto-open first time)
2. The same ranked table — but every row now has plain-English subtitles
3. Hover the SM SCORE → see "Signals fired: insider_buying · revenue_30pct_plus · ..."
4. Hover the WoW Δ → see what changed since last week
5. Click any row → opens full institutional research report

---

## Why this matters

The old v3.1 was technically powerful but **looked like a Bloomberg Terminal screen**. New users couldn't tell:
- whether 70 was a good score
- what "ACCUM Moderate" meant in real terms
- why a stock was tagged "Crowded" instead of celebrated for being near highs
- what makes a BUY a BUY vs a STRONG BUY

Now they can — in one glance. The technical labels stay (institutional users want them) but the meaning is right there underneath.

---

## Revert if needed

```powershell
git revert HEAD --no-edit
git push origin main
```

Site comes back in ~90 seconds.
