# READ THIS FIRST — A Simple Guide to Active Trading

*For people who are not full-time traders. No jargon. No assumed knowledge.*

---

## Step 1 — What is this screen actually doing?

Every 5 minutes, the system scans the Indian stock market and picks the
**3 best options trades** it can find right now. It shows you:

- Which stock or index (NIFTY, BANKNIFTY, etc.)
- Which option to buy (like "24500 CE" means call option at 24500)
- How confident it is (like 95%)
- What price to pay, and when to enter

You don't have to find trades. The system finds them for you.

---

## Step 2 — What do I see on the screen?

Think of the screen as **three columns**, like a Bloomberg terminal.

**Left column — "TOP TRADES"**
Top 3 picks right now. Each card has a big green **TAKE TRADE** button.

**Middle column — "LIVE MONITOR"**
Shows what the system thinks about the trade you clicked. Like a second
opinion before you buy.

**Right column — "DEEP DIVE"**
All the technical analysis for the selected trade. Charts, math, everything.
Optional — only look here if you want details.

**Bottom — "SECONDARY SCANNER"**
Trades 4 through 10 that didn't make the top 3. Still good, just not the
best 3 right now.

---

## Step 3 — Traffic light system (what colors mean)

- **Green** — Good sign. Take this trade, or this is a positive factor.
- **Orange / Yellow** — Be careful. Not a blocker, just a warning.
- **Red** — Stop. Don't trade. Or loss. Or danger.
- **Blue** — Information. Neutral.

If you see lots of green + a green button → go ahead.
If you see orange warnings → read them, then decide.
If you see red → don't trade. The system is protecting you.

---

## Step 4 — The 3 confidence levels

Every trade shows a number like "95%". Next to it, tiny text:

- **"uncal"** — The system thinks it's 95%, but hasn't seen enough of YOUR
  past trades to prove it. Treat with caution.
- **"calibrated"** — Your past paper trades confirm the scoring is reliable.
- **"62% win · 24 trades"** — For trades like this one in the past, YOU
  won 62% of the time. This is the number to trust.

In the beginning, everything says "uncal". That's normal. After you use the
system for a few weeks, real numbers appear.

---

## Step 5 — How to actually take a trade

1. Look at the **top 3 cards** on the left.
2. Click any one to see more details in the middle + right column.
3. Read the big **verdict card** in the middle:
   - "STRONG BUY" → System loves this trade
   - "BUY" → Good trade, but not elite
   - "BUY SMALL" → Take a smaller position
   - "NEUTRAL" → Skip, wait for better
   - "AVOID" → Don't trade
4. Read the **green ticks** (things going right) and **orange warnings**
   (things to watch).
5. If you want to proceed, click the green **TAKE TRADE** button.
6. A box will pop up showing you **exactly** what will happen:
   - How many lots
   - How much rupees at risk
   - Stop loss and target
   - Any extra warnings
7. If you agree, click **CONFIRM TRADE**. If not, click CANCEL.

**That's it.** The system handles everything else — entry timing, stop loss,
target, when to exit.

---

## Step 6 — What happens after you click CONFIRM?

1. Position goes **PENDING**. That means: "waiting for price to cross the
   trigger". The system won't actually buy until price confirms the move.
2. Once price crosses the trigger → position goes **LIVE**. Voice will say
   "entry confirmed".
3. Every 5 minutes, the system checks if you should:
   - **HOLD** (continue) — signal is still good
   - **ADD** — signal got stronger, consider adding
   - **REDUCE** — signal weakening, cut half
   - **SCALE OUT** — you're up 1.5× the risk, automatically book 50% profit
   - **EXIT** — time to close the trade

You don't have to watch the screen. Just listen for the voice alerts. It
will tell you what to do.

---

## Step 7 — When to STOP trading for the day

The system will warn you at these points:

- **After 2 losses in a row** → "Slow down. Smaller size or take a break."
- **After 3 losses in a row** → "Step back from the screen."
- **Daily loss crosses 3%** → All new trades blocked for today.
- **Drawdown crosses 5%** → All new trades blocked for today.

**When the system says stop, STOP.** Revenge trading is the #1 way retail
traders lose money. The system exists partly to protect you from yourself.

---

## Step 8 — What does "Take the trade" actually do? (paper money)

**IMPORTANT:** Right now, this system uses **paper money**, not real money.
You're practicing. No actual rupees move.

This is by design. Use it to:
1. Learn how the system works
2. Build a track record of 50-100 trades
3. See your real win rate (the "62% win · 24 trades" label appears)
4. Decide if you trust the system before using real money

When you're ready for real trading, open a separate broker account and
execute the same trades manually there. The system doesn't place real
orders yet (that's coming in a future version).

---

## Step 9 — Things that might confuse you

**"My trade says PENDING for a long time"**
→ Normal. Price hasn't crossed the trigger yet. The trigger is usually
entry price + 2% for a call, meaning the price must CONFIRM going up
before you buy. This prevents you from buying tops.

**"I clicked TAKE TRADE but nothing happened"**
→ Check the red "BLOCKED" box in the confirm modal. Something is
preventing the trade. Common reasons:
- Already 3 positions open (max limit)
- RBI or FOMC event tomorrow (IV crush risk)
- You're too close to daily loss limit
- Stock strongly correlates with a position you already have

**"Scores keep saying 'uncal'"**
→ You need 100+ closed trades before the system calibrates to YOUR win
rate. Be patient.

**"BUY verdict but caveats say OVERPRICED"**
→ Read the caveats carefully. Overall verdict can still be BUY even with
1-2 caveats, but more caveats = more risk. Use smaller size.

**"The voice is annoying"**
→ Click the mic icon in the header to turn it off. But know that you'll
miss entry/exit alerts if you do.

**"The CLOSED label is showing when market is open"**
→ That was a bug in older versions. If you see it now, hard-refresh your
browser (Ctrl+Shift+R / Cmd+Shift+R).

---

## Step 10 — The golden rules

1. **Never size bigger than the system recommends.** The Kelly math is
   calibrated. Overriding it is how retail traders blow up.

2. **Don't skip the confirm modal** when you're just starting. Read it.
   Understand what 2 lots and ₹4,200 risk means for your capital.

3. **Don't close winning trades early.** Let the 5m system guide you.
   It's smarter about exits than your emotions.

4. **Don't add to losing trades.** If the system says REDUCE or EXIT,
   do it.

5. **Don't trade during lunch (12:00-13:30 IST) if you can avoid it.**
   The system already reduces signal strength during this window because
   win rates historically drop.

6. **Don't take a trade you don't understand.** Click the `?` icon in
   the header for detailed docs, or read the PROS/CAVEATS carefully.

7. **Don't ignore the streak warnings.** After 2 losses, the system is
   telling you to slow down. After 3, stop. Listen to it.

8. **Keep a trading journal.** Screenshot your confirm modal before every
   trade. Review mistakes weekly. The "YOUR EDGE" section in the middle
   column will show you patterns over time.

---

## Step 11 — Where do I click for more help?

- **The `?` icon** in the header (top right) — opens detailed docs with
  how-to, scoring math, and known limits.
- **Hover over any score/warning/badge** — tooltip explains it.
- **Click "BLOCKED" button** — tells you why a trade is blocked.

---

## One-page cheat sheet (print this and keep it near your screen)

```
┌─────────────────────────────────────────────────────┐
│  CELESYS ACTIVE TRADING — QUICK RULES               │
├─────────────────────────────────────────────────────┤
│  1. Wait for 5m candle close → system picks top 3   │
│  2. Click a card → read verdict in middle column    │
│  3. Click TAKE TRADE → review confirm modal         │
│  4. Click CONFIRM → trade goes PENDING              │
│  5. When price crosses trigger → trade goes LIVE    │
│  6. Voice guides you through holds, adds, exits     │
│                                                     │
│  STOP TRADING IF:                                   │
│  • 2 losses in a row (voice warns you)              │
│  • 3 losses in a row (system blocks)                │
│  • Day P&L below -3% (system blocks)                │
│                                                     │
│  CONFIDENCE LABELS:                                 │
│  • "uncal" — score is theoretical, trust with care  │
│  • "calibrated" — score matches your past trades    │
│  • "62% win · 24 trades" — real win rate (trust)    │
│                                                     │
│  COLORS:                                            │
│  • Green = good / positive                          │
│  • Orange = warning (not a blocker)                 │
│  • Red = blocker / loss / don't trade               │
│                                                     │
│  THIS IS PAPER MONEY. No real rupees move.          │
│  Build a track record before switching to real.     │
└─────────────────────────────────────────────────────┘
```

---

## Still confused?

Click the `?` icon in the header. The detailed guide has the full math.
Or just practice for a week — most of this becomes obvious once you've
done 20-30 trades and watched how the system behaves.

**Paper trading is risk-free.** Experiment. Try different setups. The
goal right now is not to make money — it's to learn how the system
thinks so that when real money is in play, you trust it.
