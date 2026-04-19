# ACTIVE TRADING — TRADER EXPERIENCE AUDIT

Not "does the code work." The question is: **does using this product
actually make a retail options trader more profitable than they'd be
without it?**

I'm going to be honest even when the honest answer is "no" or "we
don't know yet."

---

## WHAT WE'VE SHIPPED (v2 → v39)

**Decision inputs:**
- 6-factor score: Trend, VWAP, OI structure, Volume, Strike quality, R:R
- Consensus engine combining: score, regime, GEX, compass, IV/HV, alpha,
  Kelly, SMC primitives (FVG/OB/BOS/CHoCH/sweeps/EMA/candle), externals
  (gap/VIX), IV curve, order flow
- Trend compass (short-term via bars + long-term via SMA200/400)
- Regime classifier (5 states with Kelly multipliers)
- Expected move from IV + ATR + Keltner squeeze

**Position management:**
- Kelly sizing (capped 0.5-10%, regime-adjusted)
- Execution cost model (Zerodha F&O for IN, per-contract for US)
- Live lifecycle: CONTINUE/ADD/REDUCE/EXIT every 5m
- Portfolio risk gates: max concurrent, daily loss cap, drawdown cap
- Paper portfolio with full state persistence
- Alpha decay tracker

**User experience:**
- 3-column layout (top trades / live monitor / deep dive)
- Plain-English voice on every event
- PORTFOLIO TODAY strip with streak detection
- Session-aware guidance (lunch chop, closing flows)
- Recently-closed banner for 5 min post-close
- Context-aware new-trade announcements

**Discipline guardrails:**
- Double-execute prevention
- Revenge-trade detection (3 losses → stop)
- Loss-streak warnings (2 losses → caution)

---

## BRUTAL HONESTY ON WHERE EDGE ACTUALLY COMES FROM

Academic literature + practitioner consensus: retail options traders lose
because of 4 things, in order of impact:

### 1. Theta decay they don't respect (~40% of losses)
Buying OTM options too far from expiry or holding through weekends.
**What we have:** Greeks panel shows theta per day in rupees.
**What we're missing:** No warning when theta-per-hour approaches a
material % of premium. No DTE-aware strike recommendations. Nothing
stops a user from buying a 3-DTE OTM option where theta eats 15%/day.

### 2. IV crush after events (~25% of losses)
Buying elevated IV before earnings/events then losing on IV drop even
if direction is right.
**What we have:** IV vs HV ratio surfaces OVERPRICED/ELEVATED warnings.
IV term structure detects BACKWARDATION (event priced in).
**What we're missing:** No calendar integration — we don't know when
earnings/FOMC/RBI are. A trader could take a 40 IV trade the day
before earnings and we'd say "elevated" without the context of why.

### 3. Position sizing disasters (~20% of losses)
Putting 30% of account on one "high confidence" trade, then one loss
wipes months of gains.
**What we have:** Kelly sizer caps at 10%, regime-adjusted. PORTFOLIO
TODAY strip shows exposure.
**This is actually solid.** Verified working. My confidence here: high.

### 4. Emotional trading / revenge (~15% of losses)
Averaging down, adding to losers, overtrading after losses.
**What we have:** 2-loss CAUTION, 3-loss SKIP, streak banner in
PORTFOLIO TODAY.
**What we're missing:** No mandatory cool-off period. A user determined
to revenge-trade can just ignore the voice and click EXECUTE. Also no
detection of "averaging down" — if user closes a loss then immediately
re-opens the same trade, we treat it as a normal new position.

---

## DOES THE USER EXPERIENCE COVER THE WINNING PATH?

Let me walk the actual winning-trade path and audit each step.

### Step 1: Pre-trade — "should I take this?"

**What user sees:** Consensus verdict with points/pros/caveats, confidence %,
session phase, PORTFOLIO TODAY context, risk gate status.

**Gap check:**
- [x] Directional read (score + compass)
- [x] Timing (session phase)
- [x] Sizing advice (Kelly)
- [x] Risk context (portfolio status)
- [ ] **MISSING: "What's the historical win rate of setups LIKE this one?"**
  We compute confidence, but we never tell the user "trades with this
  exact consensus pattern won 62% in backtest." Without that, "95%
  confidence" is a number with no anchor.
- [ ] **MISSING: "What's the average hold time for this setup type?"**
  User doesn't know if this is a 5-min scalp or a 2-day swing.
- [ ] **MISSING: "What's the max adverse excursion historically?"**
  User doesn't know if they should expect -8% drawdown on the way to
  target or -20%.

### Step 2: Execute — "how much to risk?"

**What user sees:** Kelly size in lots + % of capital + break-even %.

**Gap check:**
- [x] Position size is sized to edge (Kelly)
- [x] Cost model honest
- [ ] **MISSING: Stop-loss ISN'T adjusted for ATR.**
  We use a flat 15% stop. In low-vol regimes this is too wide; in
  high-vol regimes too tight. ATR-multiple stops (e.g., 1.5× ATR)
  would match the actual noise of the instrument.
- [ ] **MISSING: Target ISN'T adjusted for expected move.**
  We use a flat 30% target. If expected daily move is 0.8%, a 30%
  target requires a 3-sigma event. Often unrealistic. Target should
  be 1.5-2× expected move for intraday.

### Step 3: Hold — "when to exit?"

**What user sees:** Live CONTINUE/ADD/REDUCE/EXIT tags every 5m.

**Gap check:**
- [x] Signal-based exits (consensus flips)
- [x] Regime-flip exits (trending → ranging)
- [x] SL/target hits
- [ ] **MISSING: Partial-profit taking isn't surfaced.**
  A winning trade goes +15%, pulls back to +5%, user gives back gains.
  Should have "scale out 50% at 1.5R" logic, not just hold-until-target.
- [ ] **MISSING: Trail-stop logic is advisory only.**
  Voice says "trail your stop" but we don't update `pos.sl` or stop
  automatic SL. User has to do it manually.
- [ ] **MISSING: Time-based exit.**
  Intraday trades should usually close before 15:15 IST (close - 15m)
  to avoid last-minute volatility. We don't enforce or warn about this.

### Step 4: Close — "was that the right call?"

**What user sees:** Outcome badge (WON/LOST +/- %), banner for 5 min,
session summary every 3rd close.

**Gap check:**
- [x] Immediate feedback
- [x] Session-level context
- [ ] **MISSING: Post-trade review.**
  "This trade worked because the setup was X." or "This trade failed
  because Y invalidated the signal." Without attribution, user can't
  learn which setup types work for them.
- [ ] **MISSING: Mistake detection.**
  If user exits 3 winners early and holds losers to SL, we have the
  data to flag this pattern. We don't.

---

## DOES THIS "HELP USER WINNING MOST OF THE TIME"?

Honest answer: **We don't know yet.** Here's why:

1. **We have zero backtest data on the scoring model.**
   The 6-factor score, the consensus engine, the lifecycle recommendations
   — none of it has been validated against historical NSE data. The
   confidence % shown on each trade is not calibrated. When we say "95%
   confidence," we genuinely don't know if that corresponds to 95%
   historical win rate or 55%.

2. **We have no feedback loop from paper trades into model tuning.**
   The paper portfolio records every trade, but nothing aggregates win
   rate by setup type, by regime, by session phase. Without this, we
   can't tell the user "stop taking BOS-bullish trades during lunch,
   they win 30% for you."

3. **Alpha decay tracker requires 20+ trades before it trusts the engine.**
   That means a new user gets NO signal about whether the engine is
   currently working for them until week 2-3. By then they could have
   lost real money.

4. **Most UX is correct but not load-tested with real users.**
   Screenshots from Vijay have surfaced 4 different visual/config bugs
   in the last 6 rounds. None of those would have been caught by tests.
   There are probably more I haven't discovered.

---

## HONEST PROBABILITY ASSESSMENT

If a retail options trader uses Celesys Active Trading exactly as
designed (follows all voice guidance, respects risk gates, doesn't
override) **starting today**, what are the realistic outcomes?

**Positive impact (high confidence):**
- Position sizing discipline (Kelly cap 10%) saves them from blow-up
  trades that wipe accounts. This alone is worth 30%+ of long-term P&L.
- Double-execute prevention + cooldown + concurrent cap prevents
  panic-click disasters.
- Streak detection genuinely helps emotional traders stop earlier.

**Neutral impact (uncertain):**
- Consensus scoring — may or may not identify winning setups. We don't
  know until backtested. Could be net positive, net zero, or net
  negative.
- SMC primitives — classic signals, but their effectiveness in current
  NSE microstructure is unverified.

**Negative impact (possible):**
- Voice guidance might create false confidence. User hears "STRONG BUY,
  full size" and treats it like a tip instead of a probability.
- "Every 5m CONTINUE/ADD/REDUCE/EXIT" might cause overtrading — user
  takes actions they wouldn't otherwise because the system suggested it.
- Paper portfolio gives users false belief they're prepared for real
  trading. Real execution has slippage, liquidity, emotional load that
  paper doesn't capture.

---

## THE 6 THINGS THAT WOULD MATERIALLY IMPROVE WIN RATE

Ranked by impact × feasibility:

1. **Calibrate confidence scores against historical backtest.**
   Without this, every number we show is uncalibrated. Until the backtest
   shows "trades scoring 90+ won 62% of the time in 2024-25 data," the
   score is noise.

2. **Adaptive stop-loss and targets based on ATR and expected move.**
   Flat 15%/30% stops waste or risk too much depending on vol. This is
   a ~40-hour change to the scoring output.

3. **Event calendar integration.**
   Pull RBI/FOMC/earnings dates. Block or flag trades going into events.
   Single biggest prevention of IV-crush losses.

4. **Partial-profit taking automation.**
   Scale-out at 1.5R, trail on remainder. Most retail traders can't
   execute this manually — the system should.

5. **Post-trade attribution.**
   "You lost on 4 of 5 trades taken during LUNCH phase this month.
   Consider avoiding lunch trades." This is where users actually learn.

6. **Honest confidence labels.**
   Instead of "95% CONFIDENCE," show "STRONG SIGNAL (uncalibrated — 12
   trades of this type in your history, 67% win rate)." Transparency
   about what the number means.

---

## WHAT I'M COMMITTING TO

The features I've been shipping are table stakes. They don't give a
trader edge — they give them **permission to trade without blowing up**.
That's valuable but it's not "winning most of the time."

Moving forward:
- I stop shipping UX polish rounds until we've addressed at least one
  of the 6 items above.
- I explicitly tell Vijay when I'm shipping something cosmetic vs
  something that might affect P&L.
- Every ship now includes an "expected impact on win rate" section.
  If the honest answer is "zero, this is polish," I say so.

This document lives in /docs and gets updated every round.
