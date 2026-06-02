# Deeper Decision Cards — Detailed Inferences

## What's new

Every existing inference **stays exactly as it is**.

NEW: a richer **"📋 WHAT THIS MEANS FOR YOUR DECISION"** expandable card is added under three sections:

1. **ROIC vs WACC** (Capital Efficiency)
2. **IF YOU ALREADY HOLD** (in the Decision Summary box)
3. **IF YOU DON'T HOLD** (in the Decision Summary box)

Each card has a **3-layer structure**:

> **① WHAT YOU'RE SEEING** — the raw data point in plain English with the actual numbers
>
> **② WHY IT MATTERS** — business / portfolio implications, what historical patterns this resembles
>
> **③ WHAT TO DO** — concrete actions, exit triggers, position sizing, what to watch for

## Tone color-coding

Each card adapts its color to the scenario:

| Tone | Color | When |
|---|---|---|
| 🟢 **Positive** | Green accent | ROIC spread ≥5pp, Aligned Bull scenario, high-conviction setups |
| 🔴 **Negative** | Red accent | Negative ROIC spread, Aligned Bear, do-not-enter scenarios |
| 🟡 **Mixed** | Amber accent | ROIC barely positive, Weak Momentum, Quality-but-Bad-Timing |
| 🟣 **Neutral** | Indigo accent | Mixed signals, undecided scenarios |

## Example — ROIC vs WACC (positive tone) for a value creator like MU

**① What you're seeing:**
- This company earns **34.3%** on every dollar of capital it deploys (ROIC).
- It costs **8.9%** to fund that capital — debt interest + shareholder expectations (WACC).
- The **spread is +25.4 percentage points**. Each retained dollar compounds shareholder wealth.

**② Why it matters:**
- This is the kind of business Buffett looks for — high ROIC over many years is the single strongest predictor of long-term shareholder returns.
- Companies with persistent ROIC > WACC can fund their own growth without diluting shareholders or piling on debt.
- However, no spread lasts forever. Watch competitive intensity, capital intensity, and pricing power.

**③ What to do:**
- **Bull case is structurally supported.** Compounding math works in your favor.
- Suitable for **core long-term position**. Position sizing can be larger than typical.
- **Monitor warning signs:** ROIC trending down 2 quarters in a row · capital intensity rising · new competitors with pricing power · debt outpacing EBITDA.
- Re-evaluate if spread narrows below 5pp for 2 consecutive quarters.

## Example — IF YOU ALREADY HOLD (mixed signals)

**① What you're seeing:**
- Current price **$20** · Fair value **$22** · Implied upside **+10%**.
- Your stop is at **$17** (a 15% drawdown).
- Risk-reward ratio **0.67 : 1** — unfavorable.
- Three systems: Quality **HOLD** · Timing **NEUTRAL** · Trend **NEUTRAL**.

**② Why it matters:**
- Mixed signals mean the systems disagree — typical in transition periods.
- Adding here is a leveraged bet on which signal resolves first. Selling everything risks missing the resolution if it's bullish.
- The institutional playbook in mixed scenarios is *position-sized waiting*.

**③ What to do:**
- **Maintain current position.** Don't add capital, don't panic-sell.
- Set price alerts at **$18** (add trigger if 2/3 systems turn bullish) and **$17** (exit on bearish flip + volume).
- Review weekly. Signal resolves within 4-8 weeks typically.
- If position > 5% of portfolio, trim to the Half-Kelly figure shown above.

## How the cards adapt to the actual scenario

All numbers come from the live report — current price, SMA50, SMA200, stop, fair value, position size, scenario type. The text varies based on:

- ROIC spread bucket (≥5pp / 0-5pp / negative)
- Scenario (Aligned Bull / Aligned Bear / Weak Momentum / Quality Wait / Mixed)
- Risk-reward ratio (favorable / acceptable / unfavorable)

So MU's card will read very differently from a struggling small-cap's card — even though the structure is identical.

## Files changed

| File | Change |
|---|---|
| `static/app.js` | Added `window._deeperDecisionCard()` helper + 3 injection points |
| `static/app.min.js` | Synced |
| `api.py` | No change |
| `stock_intelligence.py` | No change |
| `smart_money_v3.py` | No change |

Only **2 files** changed vs prior deploy.

## DEPLOY (3 commands)

```powershell
git add static/app.js static/app.min.js
git commit -m "Deeper decision-oriented inferences (ROIC, IF YOU HOLD/DON'T)"
git push origin main
```

Wait ~90 seconds. Hard-refresh browser (Ctrl+Shift+R).

## Verify

1. Generate a report for any ticker
2. Scroll to **🏛️ ROIC vs WACC** section → expand the "📖 Institutional Analysis" accordion → click into the ROIC section
3. Below the existing "💡 In simple terms" caption, you'll see a new collapsible:
   > **📋 WHAT THIS MEANS FOR YOUR DECISION — ROIC vs WACC**
4. Scroll to the **DECISION SUMMARY** box (the big colored panel)
5. Below each of the green "IF YOU ALREADY HOLD" and blue "IF YOU DON'T HOLD" cards, you'll see new "📋 WHAT THIS MEANS FOR YOUR DECISION" collapsibles
6. All three open by default — tap the summary to collapse

## Preview without deploying

`decision_card_preview.html` is in the outputs folder — open in any browser to see the 4 card variations (positive / negative / mixed / neutral) rendered with sample data.

## Revert if needed

```powershell
git revert HEAD --no-edit
git push origin main
```

Site returns in ~90 seconds.

## Why not the Correlation Cluster Map?

I found that section is referenced in `app.js` but its `_correlationClusterMap()` function is defined in a separate file I don't have access to in this session. Adding a decision card there would require seeing that function's code first. We can add it in a follow-up if you share that file — or you can do the same pattern there using `window._deeperDecisionCard()` since the helper is now globally available.
