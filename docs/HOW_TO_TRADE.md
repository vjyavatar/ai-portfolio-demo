# HOW TO TRADE — Celesys Active Trading

A practical guide for using the Active Trading module. Reading this once will
save you from misinterpreting what you see on screen.

---

## 1. WHAT THIS IS (AND WHAT IT IS NOT)

**What this is:** A paper-trading decision-support tool for Indian (NSE F&O)
and US options. It scans the market every 5 minutes, ranks setups, sizes
positions via Kelly math, guides you through the lifecycle of each open
position, and learns what works for YOU over time.

**What this is NOT:**
- Not a broker. EXECUTE opens a **paper** position. No real money moves.
- Not a guarantee. "95% confidence" is a score, not a probability of winning.
  Read Section 9 to understand what the number actually means.
- Not a tip service. Every decision shown is derived from market data in front
  of you. You can disagree and you should know WHY it said what it said.

---

## 2. THE SCREEN AT A GLANCE

When you open Active Trading, you see three columns plus a top header:

**Header strip (top):**
- Region toggle (IN / US)
- Index quick-switch (NIFTY / BANKNIFTY / SENSEX)
- Search bar — find any ticker in the scanned universe
- Three status chips: **Regime** (market mode), **Alpha** (engine health),
  **Risk** (how many concurrent trades you have)
- Paper portfolio count, voice toggle

**Left column — TOP TRADES:**
- Up to 3 cards ranked by confidence score
- If you have open positions that rotated off the top-3, they appear in
  a "MY POSITIONS" section above the new top-3 with a dashed separator.

**Middle column — LIVE MONITOR:**
- **PORTFOLIO TODAY** strip — your day P&L, W/L record, concurrent count
- **SELECTED** trade's consensus verdict (STRONG BUY, BUY, NEUTRAL, AVOID)
  with pros and caveats
- **OPEN POSITIONS** — each active trade with its live lifecycle tag
  (CONTINUE / ADD / REDUCE / EXIT / SCALE_OUT)
- **RECENTLY CLOSED** — last 3 closed trades in the past 5 minutes
- **YOUR EDGE** — over time, shows which setup types work best/worst for you
- **PRE-OPEN · GLOBAL CUES** — GIFT NIFTY gap, India VIX (or US equivalents)

**Right column — DEEP DIVE:**
- Selected trade's detailed breakdown: entry engine, candlestick chart,
  price action (Smart Money Concepts), volatility metrics, payoff diagram,
  GEX + trend compass, Greeks + IV/HV, sentiment bar, option chain, risk
  block, and voice log pinned at the bottom.

---

## 3. HOW A TRADE ACTUALLY HAPPENS — THE 7-STEP FLOW

### Step 1 — Wait for the 5m close
At every 5-minute candle close, the engine re-scans the market, re-ranks
every ticker, and updates the top 3. **Do not trust mid-bar scores** — they
haven't been confirmed by a candle close yet. The countdown at the top-right
of the deep-dive shows time until next evaluation.

### Step 2 — Select a trade to inspect
Click a top-trade card. Middle column populates with consensus verdict + pros
+ caveats. Right column populates with full deep-dive.

### Step 3 — Read the verdict
The middle column's big colored card says one of five things:
- **STRONG BUY** — full-size take, all signals aligned, +35 points or more
- **BUY** — three-quarter size, most signals aligned, +18 to +34 points
- **BUY SMALL** — half-size, mixed signals, +5 to +17 points
- **NEUTRAL** — wait for cleaner setup, -5 to +4 points
- **AVOID** — don't trade, points below -5 OR a hard blocker fires

Below the verdict, **PROS** (green ticks) show what's going right,
**CAVEATS** (orange warnings) show what's going wrong. Read them both.

### Step 4 — Check your context
Before clicking EXECUTE, scan PORTFOLIO TODAY:
- If OPEN is at 3/3, you're at capacity. No new trades.
- If NET is already negative, sessionGuide may auto-CAUTION or SKIP.
- If "2 losses in a row" or "3 losses today" banner is showing, the
  system is telling you to stop trading. Listen.

### Step 5 — EXECUTE
Click the green EXECUTE button on the top-trade card. Several things happen:
1. **Event calendar check** — if RBI/FOMC/earnings within 1 day on this
   ticker, the trade is BLOCKED with voice explanation.
2. **Portfolio risk check** — max concurrent, daily loss cap, drawdown cap,
   5-second cooldown. If blocked, voice says why.
3. **Kelly sizing** — computes lots based on your capital + the trade's edge,
   regime-adjusted. Voice confirms: "NIFTY 24500 CE opened. 2 lots, 4 percent
   capital, break-even 0.8 percent."
4. **Position goes PENDING** — waiting for price to cross the trigger level.
   Card turns orange with "● PENDING" pill.

### Step 6 — Trigger hits, trade goes LIVE
When price crosses the trigger, the position becomes **ACTIVE**. Card turns
green with "● LIVE" pill. Voice confirms: "entry confirmed. Confidence 92
percent. You can enter the trade now."

### Step 7 — Let the system guide the exit
Every 5 minutes from now until close, the engine re-evaluates this position:
- **CONTINUE** — signal still intact, hold
- **ADD** — signal strengthening + already profitable, consider adding 25-50%
- **REDUCE** — signal weakening, cut to half size
- **SCALE_OUT** (automatic) — at 1.5× risk profit, closes 50% and trails
  remainder with break-even stop
- **EXIT** — signal flipped, close immediately (system auto-closes on AVOID)

Voice speaks EXIT/ADD/REDUCE/SCALE_OUT immediately. CONTINUE only speaks
when your P&L bucket changes (e.g. crosses 10%).

---

## 4. THE 3-POSITION RULE

You can have maximum 3 concurrent paper positions. This is non-negotiable:

- If you try to open a 4th, button shows **RISK BLOCKED**.
- This is a hard institutional discipline. Options decay fast; tracking more
  than 3 positions reliably is hard.
- If a 4th trade appears in top-3 that's clearly better than your worst
  current position, the right answer is to manually close the worst (right
  column → Live Positions → Close Now), then open the new one.

---

## 5. STREAK DETECTION — WHEN TO STOP

If you lose 2 trades in a row today:
- Voice: "Two losses in a row today. Slow down. Consider smaller size or a
  break before the next trade."
- PORTFOLIO TODAY shows orange warning banner.
- shouldTakeNew returns CAUTION on any new top trade.

If you lose 3 trades in a row:
- Voice: "Three losses today. Step back from the screen."
- Red "STOP trading today" banner in PORTFOLIO TODAY.
- shouldTakeNew returns SKIP — new-trade voice says "Not recommended."

**You can still click EXECUTE after 3 losses.** The system will NOT hard-block
you based on streak alone. But it will tell you loudly that you're about to
revenge-trade. Listen.

---

## 6. EVENT CALENDAR

The engine knows about:
- RBI MPC dates (bi-monthly)
- FOMC dates (8 per year)
- India Budget (Feb 1)

**If an event is within 1 day** and marked HIGH IV crush risk: EXECUTE is
**blocked**. Wait until after the event.

**If event is within 2 days** or MEDIUM risk: WARN — trade still opens but
voice notes the risk.

**For per-ticker earnings** (like RELIANCE earnings day), you need to add
them manually via console: `window._atEngine.events.add({date: '2026-07-15',
name: 'RELIANCE Q1', region: 'IN', tickers: ['RELIANCE'], ivCrushRisk: 'HIGH'})`

---

## 7. PARTIAL PROFIT (AUTO-SCALE AT 1.5R)

The single most underused discipline in retail options trading.

When any active position reaches 1.5× the risk distance in profit:
- System auto-closes 50% of your lots at current price
- Raises SL on the remaining 50% to break-even (your entry price)
- Voice: "NIFTY 24500 CE hit one and half R. Booked fifty percent at plus
  twenty percent. Remainder trails with break-even stop."
- This locks in positive expectancy even if remainder stops at break-even.

**Why this matters:** If the target at 2R hits on the remainder, your total
trade P&L is (1.5R × 0.5) + (2R × 0.5) = 1.75R. If the remainder stops at
break-even, you still booked 0.75R. You cannot lose on this trade.

---

## 8. THE LIFECYCLE TAGS IN DETAIL

Each 5m bar, every active position gets one of these tags in the middle
monitor:

| Tag | Color | What it means | What you do |
|-----|-------|---------------|-------------|
| CONTINUE | Blue | Signal still intact | Hold |
| ADD | Green | Signal strengthening + in profit + high-score entry | Consider adding 25-50% more |
| REDUCE | Orange | Compass conflict / regime flip / consensus weakened | Cut to half size, tighten stop |
| SCALE_OUT | Green | Hit 1.5R — auto-books 50%, trails rest | (Automatic — no action needed) |
| EXIT | Red | Target/SL hit OR consensus flipped to AVOID | (Auto-closes for paper) |

The text below each tag explains why. Read it. If the system says "Market
regime has changed from trending up to ranging" that's the real reason to
reduce, not a hunch.

---

## 9. WHAT THE CONFIDENCE % ACTUALLY MEANS

Every top-trade card shows a big number like "95%" — next to it a small
sub-label tells you what the number is worth:

- **"95% · uncal"** — Score based on theoretical multi-factor math. No
  empirical validation yet. Treat with skepticism until enough trades
  accumulate.
- **"95% · calibrated"** — Your paper-trade history has been fed into the
  engine. The internal win-probability curve is now based on YOUR outcomes.
- **"95% · 62% win · 24 trades"** — For this exact setup type (current
  session phase + market regime + side + gamma mode), your historical win
  rate is 62% over 24 past trades. **This is the number to trust.**

Attribution surfaces after you've traded ~5 setups of the same type.
Calibration kicks in at 100 total closed trades.

---

## 10. DAILY RISK LIMITS

The system enforces:

| Limit | Default | What happens at limit |
|-------|---------|----------------------|
| Max concurrent | 3 | New EXECUTE blocked |
| Max daily loss | -3% | New EXECUTE blocked all day |
| Max drawdown from peak | -5% | New EXECUTE blocked all day |
| Cooldown between opens | 5 seconds | Prevents accidental double-clicks |

You can tune these via localStorage `at_risk_config`, but the defaults match
institutional paper-trading discipline.

---

## 11. QUICK CHECKLIST — BEFORE EVERY TRADE

Before clicking EXECUTE, ask yourself:

1. Is the consensus verdict BUY or better?
2. Are there zero BLOCKERS in the middle monitor?
3. Is PORTFOLIO TODAY showing open capacity (< 3 concurrent)?
4. Is day P&L not already near -3% cap?
5. Are you not on a 2+ loss streak today?
6. Does the deep-dive (right column) confirm the trend compass is ALIGNED?
7. Is IV not OVERPRICED (> 2.5× HV)?
8. Is there no RBI/FOMC/earnings in the next 1-2 days?

If all 8 are yes → execute. If even one is questionable → skip or reduce.

---

## 12. POST-TRADE — LEARNING FROM OUTCOMES

After a position closes:
1. **RECENTLY CLOSED** banner in middle monitor shows WON/LOST + %.
2. Session summary fires every 3rd close: "Today: 3 trades, 2 won, 1 lost,
   net plus 1.5 percent. Win rate 67 percent."
3. **YOUR EDGE** section updates. Over time, buckets like
   `MORNING · TRENDING UP · CE · 8W/2L · 80% win` emerge.
4. Calibration harness records the score-vs-outcome for this trade.

**Your job:** periodically scan YOUR EDGE. If "LUNCH · RANGING · CE" shows
consistently bad, avoid those setups. Market teaches you what YOU do well.

---

## 13. WHAT THE VOICE SAYS (AND WHY)

Voice fires on:
- Entry trigger — "NIFTY 24500 CE entry triggered at 150.00. Trade is live."
- Entry confirmed — "Entry confirmed. Confidence 92 percent."
- Target hit — "Trade closed with profit of X percent. Well played."
- SL hit — "Trade closed with loss of X percent. Protect your capital."
- Scale-out — "Hit one and half R. Booked fifty percent."
- Lifecycle ADD/REDUCE/EXIT — always spoken
- CONTINUE — only when P&L crosses 10% bucket (prevents spam)
- New top trade appears — context-aware: "You have 1 position open, room
  for more" OR "Caution — near daily cap"
- After 2 losses — "Slow down, consider smaller size or a break"
- After 3 losses — "Step back from the screen"
- Every 3rd close — session summary

You can toggle voice off via the bell icon in the header. But voice is the
primary channel for real-time lifecycle guidance — if off, you must watch
the middle monitor manually.

---

## 14. COMMON MISTAKES TO AVOID

1. **Ignoring REDUCE / EXIT** — if the system says the setup has invalidated,
   it has. Don't argue with the regime classifier.
2. **Overriding RISK BLOCKED** — if you close a position just to reopen
   a different one, you're probably about to revenge-trade.
3. **Treating "95%" as a win probability** — it's a score. Read the sub-label.
4. **Clicking EXECUTE without reading PROS/CAVEATS** — the caveats are often
   the difference between a 60% and 40% winner.
5. **Trading through lunch (11:30–13:30 IST)** — signalMultiplier drops to
   0.75 during this window because win rate is historically lower. Don't
   force setups.
6. **Trading in the last 15 minutes** — sessionGuide may SKIP new trades
   near close to avoid end-of-day whipsaw.

---

## 15. WHEN TO TURN THIS OFF

Stop using Active Trading when:
- You've hit 3 losses today — the streak banner is telling you.
- The regime chip shows VOLATILE and you're not comfortable with whipsaw.
- The Alpha chip shows DECAYED — the engine has lost its edge on recent
  trades. Take a day off, let the scoring reset.
- You're trading emotionally — the system enforces discipline but can't
  enforce it if you close tabs and open real broker app.

Paper-trading is for learning. If you've been consistently profitable on
paper for 100+ trades with a calibrated win rate > 55%, you're ready to
consider real execution. Not before.

---

## 16. WHERE TO GO DEEPER

For the actual math behind every score, verdict, and lifecycle action:
see `/docs/SCORING_LOGIC.md`.

For internal product notes:
- `/docs/TRADER_EXPERIENCE_AUDIT.md` — honest assessment of what helps vs
  what might hurt
- `/docs/PRE_SHIP_CHECKLIST.md` — the audit we run before every deploy
