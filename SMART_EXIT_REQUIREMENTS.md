# Celesys — Institutional Smart Exit Engine Requirements

**Status:** Specification captured for future implementation. The current shipped engine
(`/api/smart-exit-engine`, `smart_exit_v1`) does **not** meet this spec.
**Captured:** 2026-06-07 (r63.110.x sprint)

---

## 1. Core philosophy

The biggest mistake retail exit engines make is treating exits as the inverse of entries.
Institutions do **not** exit because a stock is down 10% or because RSI is overbought.
They exit because **the original thesis has degraded**.

The engine must answer one question every day:

> "If I had fresh capital today, knowing everything I know now, would I still want to own this stock?"

When the answer changes from *strong yes* to *no*, the exit score should deteriorate
**rapidly — before the price fully collapses**, not after.

A SELL should require **multiple independent dimensions to fail**, so that a high-quality
leader (MU, AVGO, NVDA, MRVL, PANW, CRWD) is not sold merely for a normal correction.

---

## 2. Tiered dimensions

| Tier | Dimension | Key metrics | Actions | Weight |
|------|-----------|-------------|---------|--------|
| 1 | **Capital Preservation** (highest priority) | Break below 200DMA; break below Stage-2 support; gap-down on earnings with heavy volume; multiple distribution days; relative-strength collapse; position exceeds risk budget | Reduce / Exit / Hedge | 25% |
| 2 | **Trend Integrity** | 21EMA>50EMA; 50DMA>150DMA; 150DMA>200DMA; higher highs/higher lows; ADX | Strong→Hold, Weakening→Trim, Broken→Exit | 20% |
| 3 | **Distribution Detection** | Down-volume spikes; distribution days; failed breakouts; large block selling; dark-pool activity; VWAP rejection | Smart money leaving even if price looks fine | 15% |
| 4 | **Relative Strength Deterioration** | RS rank; RS vs S&P 500; RS vs sector ETF; RS trend | Trapped capital / opportunity cost → trim | 15% |
| 5 | **Earnings Thesis** | Revenue growth; EPS growth; guidance changes; margin trends; analyst revisions | Thesis decay (e.g. 50%→35%→20% rev growth) raises exit score | 15% |
| 6 | **Leadership Status** | New-high frequency; sector leadership; RS leadership; market-cap flow | Loss of leadership raises trim score | 5% |
| 7 | **Valuation Risk** (lowest priority) | Forward PE; PEG; EV/Sales; FCF yield | Sell only when growth can no longer justify valuation | 5% |

**Final weighting to implement:**
Risk Protection 25% · Trend Integrity 20% · Distribution 15% · Relative Strength 15% ·
Earnings Thesis 15% · Leadership 5% · Valuation 5%.

Momentum-fund priority order (O'Neil / Minervini / Weinstein): Trend integrity →
Relative strength → Distribution → Earnings → Risk management. Valuation matters least
during strong momentum phases.

---

## 3. Exit decision matrix

Replace the binary BUY/HOLD/SELL with a graded scale (note: score here is an
**exit-pressure** score where higher = more reason to leave; align the implementation's
polarity explicitly):

| Composite | Action |
|-----------|--------|
| 90–100 | Strong Hold / Add |
| 80–89 | Hold |
| 70–79 | Hold with caution |
| 60–69 | Trim 25% |
| 50–59 | Trim 50% |
| 40–49 | Exit majority |
| <40 | Full Exit |

**Guard rail:** require multiple independent tier failures before any SELL-side verdict.

---

## 4. Data-availability reality (honest annotation for implementation)

**Correction (verified 2026-06-07):** there is **no** NSE/Google *history* fallback. Both
`_mcoc_fetch` (Momentum CoC) and the Smart Exit engine call `yfinance.history()` directly.
The Google Finance / Stooq references in the codebase are single-quote price fallbacks, not
history sources. In the live environment `yfinance` history **is** reachable (Momentum CoC
and SNOW's 3/5 triggers both prove it). The unreliable part is `.info` **fundamentals**,
which is why valuation/ownership triggers stay quiet. Therefore the `v1` HOLD verdicts are
mostly *directionally defensible* for structurally-intact leaders — the real problem is
**structural** (flat 5-trigger, valuation over-weighted, no entry price → profit-take inert,
not the tiered framework), not a data outage. `v2` fixes structure + honest-NULL weighting.

| Tier | Buildable now (price/volume + bench)? | Notes |
|------|----------------------------------------|-------|
| 1 Capital Preservation | **Mostly yes** | 200DMA break, support break, distribution-day count, RS collapse, drawdown vs risk budget all derive from price/volume. Earnings gap-down needs an earnings date/feed (partial). |
| 2 Trend Integrity | **Yes** | EMA/DMA stack, HH/HL, ADX all from price. |
| 3 Distribution | **Yes (price/volume proxy)** | Down-volume spikes, distribution days, failed breakouts, VWAP rejection computable. Dark-pool / block prints are **not** available — mark N/A, do not fake. |
| 4 Relative Strength | **Yes** | RS line vs benchmark + vs sector ETF from price ratios (already built for Momentum CoC stage pipeline). |
| 5 Earnings Thesis | **Data-gated** | Revenue/EPS growth, guidance, margin trend, analyst revisions need a fundamentals/estimates feed. Mark N/A until connected; do not fabricate. |
| 6 Leadership | **Partial** | New-high frequency + RS leadership computable; market-cap flow / sector leadership partial. |
| 7 Valuation | **Data-gated** | Forward PE/PEG/EV-Sales/FCF need fundamentals. Lowest weight, so absence is least harmful. |

**Honest-NULL principle:** any tier whose data is unavailable must report N/A and be
**excluded from the weighted denominator** (re-normalize over available weight), exactly as
the Momentum CoC engine treats missing factors. Never substitute a plausible default.

---

## 5. Gaps in the current engine (`smart_exit_v1`) to fix

1. **Data source:** migrate from direct `yfinance.info`/`.history()` to the resilient
   `_mcoc_fetch` (NSE/Google) path so triggers can actually evaluate on Render.
2. **Structure:** replace the flat five-trigger equal-ish sum (Institutional Selling, RS Break,
   Valuation Stretched, Technical Break, Profit-Take Territory) with the seven weighted tiers above.
3. **Polarity & matrix:** adopt the graded decision matrix; require multiple independent
   tier failures before SELL.
4. **Valuation de-emphasis:** drop valuation to 5% weight; it currently carries 20/100,
   over-weighting the least important dimension for momentum names.
5. **Thesis-degradation framing:** surface *why* the verdict changed (which tiers degraded),
   not just a composite number.

---

## 6. Acceptance criteria (when implemented)

- On Render, with Yahoo blocked, Tiers 1–4 and 6 still compute (via fallback price/volume + bench).
- Tiers 5 and 7 report N/A honestly and are excluded from the denominator.
- A quality leader in a normal correction (above 200DMA, trend intact, RS firm) returns
  **Hold / Hold-with-caution**, not SELL.
- A genuine breakdown (below 200DMA + distribution cluster + RS collapse) escalates to
  **Trim/Exit** even before price fully collapses.
- Every tier shows its inputs and a per-tier verdict; the composite explains which tiers drove it.
- Validation by execution (Python trace across hold / trim / exit scenarios) before shipping.
