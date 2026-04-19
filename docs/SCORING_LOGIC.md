# SCORING LOGIC — Celesys Active Trading

This is the full mathematical and decision-making logic behind every number
you see on screen. Exact constants from the current production code
(v41, `static/active-trading.js`).

If you want to challenge why the engine said STRONG BUY when you would have
said AVOID — this is the document to read. Every score is traceable.

---

## TABLE OF CONTENTS

1. The scoring pipeline (end-to-end flow)
2. The 6-factor confidence score (0-100)
3. Consensus engine (-50 to +70 points)
4. Regime classifier (5 states)
5. Kelly position sizing
6. Portfolio risk gates
7. SL / target derivation (ATR-adaptive)
8. Lifecycle evaluator (CONTINUE / ADD / REDUCE / EXIT)
9. Session phase and its impact
10. Event calendar logic
11. Partial profit (scale-out)
12. Attribution bucketing
13. Calibration harness
14. Full example trace

---

## 1. THE SCORING PIPELINE

Every 5 minutes the engine executes this pipeline:

```
Backend /api/bottom-nav-scan
        ↓
   Raw ticker data (OHLC bars, chain, OI, PCR, VWAP, etc.)
        ↓
   For each ticker:
        mapScanRowToTrade(row)
          ├─ detectSide(row)         → CE or PE
          ├─ 6-factor score          → confidence 0-100
          ├─ state classification    → early / ideal / late / avoid
          ├─ ATR-adaptive SL/target  → trade.sl, trade.target
          └─ build trade object
        ↓
   Rank all trades by confidence
        ↓
   Top 3 → state.trades[]
   Rest  → state.scanner[] (top 6 shown)
        ↓
   For each open position:
        partialProfitManager.evaluate(pos, currentPrice)
          → SCALE_OUT if ≥1.5R, else HOLD
        liveTradeGuide.evaluate(pos, trade, raw)
          → CONTINUE / ADD / REDUCE / EXIT
        ↓
   Render three-column UI
```

Nothing in this pipeline uses fake data. Every missing value produces null
(not a plausible default), and downstream logic explicitly checks for null.

---

## 2. THE 6-FACTOR CONFIDENCE SCORE

The 0-100 number at the top of every trade card. Six factors combined with
these weights:

| Factor | Weight | What it measures |
|--------|--------|------------------|
| **Trend Strength** | 25% | Directional momentum across recent bars |
| **VWAP Alignment** | 20% | Spot vs VWAP + distance |
| **OI Structure** | 20% | Call/Put build-up divergence |
| **Volume Confirmation** | 15% | Recent volume vs average |
| **Strike Quality** | 10% | How close strike is to spot (ATM preferred) |
| **Risk/Reward** | 10% | Target distance vs SL distance |

### Trend Strength scoring (0-100)

Based on higher-highs/lower-lows count + directional streak + sma slope.
Returns null if <10 bars of data.

### VWAP Alignment scoring (0-100)

```
distance_pct = (spot - vwap) / spot × 100

CE scoring:
  > 1.0%  above VWAP → 75 (strong)
  0.3-1.0 above     → 85 (ideal — VWAP acting as support)
  0-0.3 above       → 70 (neutral-bull)
  below VWAP        → 35 (fighting VWAP)

PE mirror: distances flipped.
```

### OI Structure scoring (0-100)

Uses `ce_buildup[0].chg` and `pe_buildup[0].chg` — change in open interest
for the top-buildup call and put strikes.

```
Classify(chg):
  > +20000 lots → +2  (strong build)
  > 0          → +1  (build)
  > -10000     →  0  (flat)
  ≤ -10000     → -1  (unwind)

CE trade:
  CE build +1 AND PE build +2 → 95  (writing PUTs, call buying)
  CE build +1 AND PE build +1 → 82
  PE build +2 alone            → 75
  At least one positive        → 65
  PE unwinding                 → 35  (short covering of puts = bearish)
  default with PCR ≥ 1.3       → 60
  default                      → 45
```

This pattern detects institutional positioning. Retail buys calls and puts;
institutions write them. When CE OI unchanged but PE OI builds massively,
institutions are selling puts = they expect price to hold = bullish.

### Composite

```
score = Σ (factor_i × weight_i)
       ÷ Σ (weight_i)   ← normalize by available factors

If 2+ factors are null (missing data), score is capped at 65
and the card shows "OI+Vol unavailable" badges.
```

### State classification from score

| Score | State | Meaning |
|-------|-------|---------|
| ≥ 85 | **ideal** | Elite setup, full Kelly size |
| 72-84 | **early** | Good but may need confirmation |
| 60-71 | **late** | Chase risk, reduced R:R |
| < 60 | **avoid** | Don't trade |

---

## 3. CONSENSUS ENGINE (-50 to +70 points)

Builds on top of the confidence score. Adds/subtracts **points** based on
every available module. Verdict derives from total points:

| Total points | Verdict | Size multiplier | Color |
|--------------|---------|-----------------|-------|
| ≥ 35 AND caveats ≤ 1 | **STRONG_BUY** | 1.0 × Kelly | green |
| ≥ 18 | **BUY** | 0.75 × Kelly | green |
| ≥ 5 | **BUY_SMALL** | 0.5 × Kelly | blue |
| -5 to 4 | **NEUTRAL** | 0.25 × Kelly | orange |
| < -5 OR blocker | **AVOID** | 0 | red |

### Base score contribution

```
points += (confidence - 60)
```
So a 95 confidence contributes +35 points by itself. A 50 confidence
contributes -10 points.

### Regime alignment

| Regime | Trade side | Points |
|--------|-----------|--------|
| TRENDING_UP | CE | +10 |
| TRENDING_UP | PE | -15 |
| TRENDING_DN | PE | +10 |
| TRENDING_DN | CE | -15 |
| RANGING | any | -5 |
| VOLATILE | any | -10 |
| MIXED | any | 0 |

### GEX regime

| GEX tag | Points |
|---------|--------|
| BREAKOUT (negative GEX, dealers amplify moves) | +8 |
| RANGE (positive GEX, dealers pin price) | -8 |
| NEUTRAL | 0 |

### Trend compass

```
cmp.aligned = (shortTerm == longTerm) AND both != NEUTRAL
cmp.conflict = shortTerm != longTerm, both != NEUTRAL

aligned + matches trade side: +12
conflict: -10
```

### IV vs HV

```
ratio = atmIV / annualizedHV

OVERPRICED  (ratio > 2.5): -8 points
ELEVATED    (1.8-2.5):     -3
FAIR        (0.7-1.8):      0
DISCOUNTED  (0.4-0.7):     +3
UNDERPRICED (< 0.4):       +8
```

### Alpha decay

Tracks engine's hit rate on past trades.

| Status | Condition | Points |
|--------|-----------|--------|
| HEALTHY | ≥20 trades, ≥55% win | +3 |
| DEGRADING | 20-20 close to 50/50 | -5 |
| DECAYED | ≥20 trades, <45% win | **BLOCKS trade entirely** |

### Kelly sizing contribution

```
If Kelly sizing returns 0 lots (negative edge):
  BLOCKS trade

edge < 0.05 (thin edge):
  warning, no point change

edge > 0.3 (strong):
  +5 points
```

### Smart Money Concepts (SMC)

Direction-aware. Points apply only if trade side matches the SMC signal:

| Signal | Matching side | Opposing side |
|--------|---------------|---------------|
| Bullish FVG (spot inside) | CE +6 | PE -4 |
| Bearish FVG | PE +6 | CE -4 |
| At bullish Order Block | CE +7 | PE -5 |
| At bearish Order Block | PE +7 | CE -5 |
| BOS Bullish (break of structure) | CE +10 | PE -12 |
| BOS Bearish | PE +10 | CE -12 |
| CHoCH Bullish (trend reversal) | CE +12 | PE — |
| CHoCH Bearish | PE +12 | CE — |
| Bullish Liquidity Sweep | CE +8 | PE -6 |
| Bearish Liquidity Sweep | PE +8 | CE -6 |
| EMA 9>21>50 (stacked bull) | CE +6 | PE -8 |
| EMA 9<21<50 (stacked bear) | PE +6 | CE -8 |
| Strong bullish candle close | CE +5 | PE -4 |
| Strong bearish candle close | PE +5 | CE -4 |
| Upper wick rejection | PE +3 | CE -5 |
| Lower wick rejection | CE +3 | PE -5 |

A fully-aligned bullish setup (FVG + OB + BOS + sweep + EMA + candle) could
contribute up to +46 points on top of the base confidence score.

### External feeds (pre-open gap, VIX)

Only active during pre-open and first 30 min of session.

```
STRONG_GAP_UP (> +0.5%):
  CE: +8,  PE: -8
GAP_UP (+0.15 to +0.5%):
  CE: +4,  PE: -4
STRONG_GAP_DOWN / GAP_DOWN: mirror

VIX change > +5%:
  -3 points (risk-off), warning
VIX change < -5%:
  +2 points (risk-on)
```

### IV term structure

```
NORMAL (near < far):   no change (healthy contango)
INVERTED (near > far): -4 points, warning (event priced in)
HUMPED (mid > near, far): -2 points
```

### Order flow

Based on bid-ask spread at ATM + buyer/seller aggression proxy.

```
Liquidity TIGHT:       +3
Liquidity NORMAL:       0
Liquidity WIDE:        -4
Liquidity VERY_WIDE:   -10 (likely unfillable)

Aggression aligned with trade: +4
Aggression against trade:      -3
```

### Hard blockers (any one → AVOID)

1. **Portfolio risk gate closed** — max concurrent, daily loss, drawdown,
   cooldown (5s between opens)
2. **Alpha DECAYED** — engine has lost its edge recently
3. **Kelly negative edge** — math says no trade
4. **Event within 1 day with HIGH IV crush risk** — RBI/FOMC/earnings

---

## 4. REGIME CLASSIFIER

Runs on the lead index's last 10 bars (5-min). Three metrics:

```
Metric 1: directional streak
  hhhl = count of (bar[i].h > bar[i-1].h AND bar[i].l > bar[i-1].l)
  llih = count of (bar[i].l < bar[i-1].l AND bar[i].h < bar[i-1].h)

Metric 2: trend efficiency
  netMove = |close[9] - open[0]|
  cumRange = Σ (bar[i].h - bar[i].l)
  efficiency = netMove / cumRange
    > 0.4 = strong trend (net move ≥ 40% of total swing)
    < 0.15 = ranging (price returns to start)

Metric 3: volatility coefficient
  ranges = [bar[i].h - bar[i].l for each bar]
  volCV = stdev(ranges) / mean(ranges)
    > 0.6 = spiky/whipsaw
```

### Classification

```
if volCV > 0.6 AND efficiency < 0.4:
  VOLATILE
elif efficiency > 0.4 AND hhhl ≥ 4 AND direction > 0:
  TRENDING_UP
elif efficiency > 0.4 AND llih ≥ 4 AND direction < 0:
  TRENDING_DN
elif efficiency < 0.2:
  RANGING
else:
  MIXED
```

### Kelly multiplier by regime

| Regime | Kelly × |
|--------|---------|
| TRENDING_UP / TRENDING_DN | 1.2 (aggressive) |
| MIXED | 1.0 |
| RANGING | 0.7 |
| VOLATILE | 0.5 (half size) |

---

## 5. KELLY POSITION SIZING

For each trade, the system computes:

```
risk_per_share = |entry - SL|
reward_per_share = |target - entry|
b = reward_per_share / risk_per_share   (payoff ratio)

p = scoreToWinProb(confidence)
q = 1 - p

edge = (p × b) - q

Kelly fraction f* = edge / b
  (if edge < 0 → Kelly = 0 → BLOCK)

fractional Kelly = f* × 0.25 × regime_multiplier
  (0.25 = quarter-Kelly, industry standard for safety)

Clamped to: max 10% of capital, min 0.5% of capital

rupees_at_risk = capital × fractional_Kelly
lots = floor(rupees_at_risk / (risk_per_share × lot_size))
```

### scoreToWinProb curve (before calibration)

| Score | Win probability |
|-------|----------------|
| <55 | 0.48 |
| 55-67 | 0.52 |
| 68-75 | 0.56 |
| 76-85 | 0.60 |
| 86-95 | 0.64 |
| ≥96 | 0.67 |

### After calibration (≥100 closed trades, ≥3 buckets with ≥10 each)

The theoretical curve is replaced with the user's actual paper-trade
win rates per 5-point bucket. Falls back to theoretical for buckets
with insufficient data.

---

## 6. PORTFOLIO RISK GATES

Checked before every EXECUTE and before every new-trade announcement.

```
config:
  maxConcurrent: 3           (pending + active)
  maxDailyLossPct: 3         (stops trading if day P&L ≤ -3%)
  maxDrawdownPct: 5          (stops if drawdown from peak > 5%)
  cooldownSeconds: 5         (min between opens — prevents double-clicks)

checkAllow() returns:
  { allow: true } OR
  { allow: false, reason: "Max concurrent positions reached (3/3)" }
```

---

## 7. SL / TARGET DERIVATION (ATR-ADAPTIVE)

Shipped in v40. Previous flat 15%/30% replaced with:

```
ATR14 = mean of true-range for last 14 bars
delta ≈ function of moneyness:
  ATM (±1%):     0.50
  ~1% OTM:       0.35
  ~2% OTM:       0.25
  ~1% ITM:       0.65

advance_move = ATR14 × 1.5 × delta
slPct = advance_move / premium
  clamped to [0.08, 0.25]

tgtPct = slPct × 2     (always 2:1 R:R)
  clamped to [0.20, 0.50]

sl = premium × (1 - slPct)
target = premium × (1 + tgtPct)
trigger = premium × 1.02
```

### Why adaptive matters

| Regime | ATR % of spot | Old flat SL | New adaptive SL |
|--------|--------------|-------------|-----------------|
| Low-vol NIFTY day | 0.2% | 15% (noise stops) | 8% (floor) |
| Normal day | 0.6% | 15% | ~16% |
| High-vol gap day | 1.5%+ | 15% (whipsaw) | 25% (cap) |

### Fallback

If ATR unavailable (<5 bars): reverts to flat 15% SL / 30% target.
`slBasis` on each trade records which path was taken
("atr_0.85%_delta_0.50" or "flat_default").

---

## 8. LIFECYCLE EVALUATOR (CONTINUE / ADD / REDUCE / EXIT)

Every 5-min bar close, for each active position:

### Priority order

```
1. If currentPrice ≥ target:
   → EXIT (won), voice urgent
2. If currentPrice ≤ SL:
   → EXIT (lost), voice urgent
3. If consensus engine now returns AVOID:
   → EXIT with reason = first blocker, voice urgent
4. If fresh consensus ≥ 35 points AND pnl > 5% AND original score ≥ 80
     AND verdict == STRONG_BUY:
   → ADD — signal strengthening, consider adding 25-50%
5. If fresh consensus < 5 points OR compass flipped to conflict
     OR regime flipped between TRENDING/other:
   → REDUCE — trim to half, set tighter stop
6. Else:
   → CONTINUE with P&L-appropriate message
```

### CONTINUE message variants (by P&L)

```
pnl > 15%:   "Up X%. Trail your stop to lock in profits."
5% to 15%:   "In profit by X%. Continue for target."
-5% to 5%:   "Tracking normally. Signal intact."
< -5%:       "Drawdown X% but signal still valid. Give it room."
```

### Voice throttling

- EXIT / ADD / REDUCE: always spoken
- CONTINUE: only when P&L crosses a 10% bucket (e.g., +10% → +20%)

This prevents the 5-min-tick voice spam while keeping critical transitions
audible.

---

## 9. SESSION PHASE

Classifies current wall-clock time:

### India (NSE, 09:15 – 15:30 IST)

| Phase | Time window | Signal multiplier | Character |
|-------|-------------|-------------------|-----------|
| OPENING | 09:15 – 09:45 | 1.1× | Range expansion, news reactions |
| MORNING | 09:45 – 12:00 | **1.2×** | Best conviction window |
| LUNCH | 12:00 – 13:30 | 0.75× | Chop, lower win rate |
| AFTERNOON | 13:30 – 15:00 | 1.0× | Trend resumption or reversal |
| CLOSING | 15:00 – 15:30 | 0.85× | Squaring off, whipsaw |

### US (NYSE/NASDAQ, 09:30 – 16:00 ET)

Same phase names, time windows shifted for US session.

### Impact

- `signalMultiplier` is used by lifecycle and attribution logic to calibrate
  the engine's confidence in a signal based on time-of-day.
- During LUNCH, `sessionGuide.shouldTakeNew()` returns CAUTION.
- During CLOSING, it returns SKIP for new trades.

---

## 10. EVENT CALENDAR LOGIC

```
checkTrade(trade, region):
  upcoming = events where:
    eventDate >= now AND
    eventDate <= now + 2 days AND
    region matches (ALL / IN / US) AND
    ticker list matches (or null = all tickers)

  if no upcoming:           return CLEAR
  if soonest ≤ 1 day AND ivCrushRisk == HIGH:
                            return BLOCK
  else:                     return WARN
```

### 2026 seeded events

- RBI MPC: 2026-02-06, 04-09, 06-05, 08-06, 10-01, 12-04
- FOMC: 2026-01-28, 03-18, 04-29, 06-17, 07-29, 09-16, 11-04, 12-16
- Union Budget: 2026-02-01

All marked HIGH IV crush risk. User can add custom events via localStorage.

---

## 11. PARTIAL PROFIT (SCALE-OUT)

Runs every 5m bar close, BEFORE lifecycle evaluator.

```
For each active position:
  if already scaled out → SKIP
  R = |entry - SL|
  reward = currentPrice - entry
  R_multiple = reward / R

  if R_multiple ≥ 1.5:
    halfLots = ceil(originalLots / 2)
    close halfLots at currentPrice (realized gain = partialPnlPct)
    position.sizingLots -= halfLots
    position.sl = position.entryPremium   (raise SL to break-even)
    position.scaledOutAt = now
    emit position:scaledOut event
    voice: "Hit one and half R. Booked fifty percent. Remainder trails."
```

### Why this matters mathematically

If position hits target at 2R after scale-out:
```
P&L = (1.5R × 0.5 lots) + (2R × 0.5 lots) = 1.75R total
```

If remainder stops at break-even:
```
P&L = 1.5R × 0.5 lots + 0 × 0.5 lots = 0.75R
```

You **cannot lose** on a scaled-out trade. Worst case is +0.75R.

---

## 12. ATTRIBUTION BUCKETING

Every closed position is bucketed by:

```
bucketKey = phase + '_' + regime + '_' + side + '_' + (gammaMode ? 'G' : '-')

example: "MORNING_TRENDING_UP_CE_-"
```

For each bucket, computed:
- `count`, `wins`, `losses`
- `winRate` = wins/count × 100
- `netPnl` = sum of all realizedPct
- `avgWin`, `avgLoss`
- `expectancy` = netPnl / count (per-trade average P&L)

### Surfacing thresholds

- Minimum 5 trades in a bucket before it appears in the UI
- "YOUR EDGE" section shows top 3 best + top 3 worst buckets
- When a trade is selected whose bucket has ≥5 trades: shows
  "THIS SETUP: 67% win rate over 8 trades"

---

## 13. CALIBRATION HARNESS

Records every closed trade's `entryConfidence` → `status` (won/lost) in
5-point buckets (0-4, 5-9, ..., 95-99).

### Application threshold

```
totalCount ≥ 100 AND
≥3 buckets have ≥10 trades each
```

When both conditions met, `kellySizer.scoreToWinProb` is replaced with:

```
empiricalWinProb(score):
  bucket = floor(score / 5) * 5
  if buckets[bucket].n ≥ 10:
    return buckets[bucket].wins / buckets[bucket].n
  else:
    return theoretical_fallback(score)
```

`kellySizer._calibrated = true` flag surfaces in UI confidence sub-label:
"95% · calibrated" instead of "95% · uncal".

Data persists in `localStorage['at_calibration']` across sessions.

---

## 14. FULL EXAMPLE TRACE

A real trade flow with numbers:

**Setup:** NIFTY spot 24,500. Top-3 scan finds NIFTY 24500 CE at premium 150.

**Raw data:**
- OHLC bars: bullish trending (HH-HL confirmed, efficiency 0.48, hhhl 6)
- Chain: ce_buildup[0].chg = +15,000, pe_buildup[0].chg = +35,000
- VWAP: 24,450 (spot above)
- ATM IV: 16%, realized vol 10%
- GIFT NIFTY: +0.35% (GAP_UP)
- India VIX: 14.2 (-0.8%)

**Confidence score computation:**
- Trend: bullish HH-HL + efficiency 0.48 → 85
- VWAP: spot 24500 vs vwap 24450, distance 0.2% above → 70
- OI: CE chg +1 AND PE chg +2 → 95 (institutions writing puts)
- Volume: current 1.3× avg → 78
- Strike: spot 24500 = ATM exactly → 100
- R:R: derived from ATR-adaptive SL/target (see below)

```
weighted = (85*0.25 + 70*0.20 + 95*0.20 + 78*0.15 + 100*0.10 + 85*0.10)
         = 21.25 + 14.00 + 19.00 + 11.70 + 10.00 + 8.50 = 84.45
```

→ **Confidence = 84** → state = "early" → score color green

**SL/target (ATR-adaptive):**
- ATR14 = 35 points (0.14% of spot)
- delta (ATM) = 0.50
- advance_move = 35 × 1.5 × 0.5 = 26.25 points ≈ ₹13 on premium
- slPct = 13 / 150 = 0.087 → clamps to 0.08
- tgtPct = 0.16 → clamps to 0.20
- SL = 150 × 0.92 = 138
- Target = 150 × 1.20 = 180
- trigger = 150 × 1.02 = 153

**Regime classifier on NIFTY bars:**
- hhhl = 6, efficiency = 0.48, volCV = 0.35
- Classification: `TRENDING_UP` (efficiency > 0.4, hhhl ≥ 4, direction > 0)
- Kelly multiplier: 1.2×

**Consensus engine:**
- Base: (84 - 60) = +24
- Regime TRENDING_UP + CE trade: +10 ✓ "aligned"
- GEX: BREAKOUT detected: +8 ✓
- Compass: aligned BULLISH on both timeframes: +12 ✓
- IV/HV: 16%/10% = 1.6× → FAIR, no change
- Alpha: HEALTHY: +3
- Kelly: edge 0.28: within thresholds, no bonus
- SMC:
  - EMA 9>21>50: +6 ✓
  - Strong bullish candle: +5 ✓
  - Lower wick rejection (CE): +3 ✓
- External: GAP_UP for CE: +4 ✓
- VIX: -0.8% → no change
- Order flow: NORMAL liquidity, aggression = BUYER matching CE: +4 ✓
- **Total points: +79**

→ Verdict: **STRONG_BUY** (≥35 points)
→ Size multiplier: 1.0 × Kelly
→ Color: green

**Kelly sizing (capital ₹100,000):**
- winProb from score 84 → 0.60
- payoff b = (180-150)/(150-138) = 30/12 = 2.5
- edge = (0.60 × 2.5) - 0.40 = 1.10
- Kelly f* = 1.10 / 2.5 = 0.44
- fractional = 0.44 × 0.25 × 1.2 = 0.132 → clamp to 0.10 (10% cap)
- Rupees at risk = ₹10,000
- Cost per lot = 12 × 75 = ₹900 (risk × lot size)
- Lots = floor(10000 / 900) = 11 ✓

**Voice announcement on EXECUTE:**
> "NIFTY 24500 CE opened. 11 lots, 10 percent capital, break even 0.8 percent."

**At 5-min bar close with price at 165 (+10%):**
- R_multiple = 15/12 = 1.25 → not yet 1.5R, HOLD
- Fresh consensus: points still +70 (signal intact)
- lifecycle = CONTINUE: "Up 10 percent. Signal still intact. Continue for target."

**At next bar, price at 175 (+16.7%):**
- R_multiple = 25/12 = 2.08 → ≥1.5R → **SCALE_OUT**
- Close 6 lots (ceil of 11/2) at 175, realized +16.7% on those
- Remaining 5 lots, SL raised to 150 (break-even)
- Voice: "NIFTY 24500 CE hit one and half R. Booked fifty percent at plus 17 percent. Remainder trails with break-even stop."

**Eventually target at 180 hits:**
- Remaining 5 lots close at 180 (+20%)
- Bucket recorded: MORNING_TRENDING_UP_CE_-
  → 1W, winRate contribution, expectancy contribution
- Calibration: entryConfidence 84, status=won → buckets[80].wins++

Final trade P&L (if target hit):
```
(16.7% × 6 lots) + (20% × 5 lots) = 100.2 + 100 = 200.2 / 11 = 18.2% avg
```

With 1:0.08 SL, this single trade would have been 18.2% on ~0.08 risk
= ~2.3R realized.

---

## 15. WHAT'S UNCALIBRATED

Honestly stated:
- The 6-factor weights (25/20/20/15/10/10) are research-informed, not
  backtested on NSE data. Could be off by ±10% on each.
- `scoreToWinProb` curve (0.48 → 0.67 from score 55 to 95+) is theoretical
  until calibration harness kicks in at 100+ trades.
- SMC signal point values (+6 for FVG, +10 for BOS, etc.) are industry
  heuristics, not empirically tuned for NSE microstructure.
- The 1.5R scale-out threshold is standard but not personalized. Your
  optimal may be 1.25R or 2R depending on your setup types.

These are the items on the audit as "need backtest validation."
Forward-calibration (the harness) closes #2 over time; #1, #3, #4 remain
theoretical until historical backtesting is possible.

---

## 16. IF YOU DISAGREE WITH A VERDICT

The consensus engine is transparent. To understand why STRONG_BUY was
shown instead of AVOID (or vice versa):

1. Open browser console
2. `window._atEngine.consensus.evaluate(trade, trade._raw)` returns the full
   points breakdown with reasons and warnings
3. Each signed point contribution is traceable to a specific module
   (regime, GEX, SMC, externals, Kelly)
4. You can also read `trade.factors` for the 6-factor breakdown

If the verdict still doesn't match your read, either:
- The market signal you're reading isn't captured by our factors (e.g.,
  specific news event not in external feeds)
- A factor is producing wrong output (report via console + screenshot)
- The signal is correct but weights need tuning for your market segment

Transparency is the point. Nothing here is a black box.
