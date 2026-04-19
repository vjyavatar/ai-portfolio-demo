# PRE-SHIP CHECKLIST — Active Trading

Before I tell Vijay "v{N} is ready, deploy the zip," I run through this list.
Every item. No skipping. If anything fails, I fix it or I say "not ready yet"
instead of shipping.

The test suite catches logic regressions. This checklist catches the things
tests don't: user experience, visual redundancy, fake-data fallbacks,
multi-trade flow, and config values that silently defeat features.

---

## 1. WALK THROUGH A REAL SESSION

For each round, I mentally simulate Vijay opening the app and doing 5-10
actions. I stop at every step and ask: "is the screen still making sense?
is the voice still helpful? is anything redundant or missing?"

Specific scenarios I MUST walk before shipping:

- [ ] **Fresh session, one trade**
  - Select trade → middle shows verdict, right shows chart
  - Click EXECUTE → card turns orange (pending) or green (live)
  - PORTFOLIO TODAY shows `OPEN 1/3`
  - Voice says something useful and plain English

- [ ] **Multi-trade stack (THE hard case)**
  - Click EXECUTE on 3 top trades in 30 seconds
  - ALL 3 must open — not blocked by cooldown/ratelimit/gate
  - Middle monitor shows 3 positions with lifecycle tags
  - PORTFOLIO TODAY shows `OPEN 3/3`
  - 4th trade EXECUTE must show RISK BLOCKED with clear reason

- [ ] **Trade rotation with open positions**
  - Have 2 open positions
  - Next refresh picks different top-3 (neither of my held trades)
  - Do my held positions still appear on the left? (MY POSITIONS section)
  - Does the lifecycle engine still have fresh data for them? (priceLookup)
  - Does the voice for new top trade respect my open count?

- [ ] **Position closes**
  - Target hits → voice, card turns WON badge, RECENTLY CLOSED banner
  - SL hits → voice, LOST badge, banner
  - Auto-EXIT from lifecycle → same, with close reason
  - After 3rd close → session summary voice fires
  - After 2nd loss → streak warning voice
  - After 3rd loss → stop-trading voice

- [ ] **Risk edge cases**
  - Portfolio risk says no → button shows RISK BLOCKED with tooltip
  - Daily loss cap hit → all new-trade EXECUTE show blocked
  - Lunch hour → new trade voice says CAUTION about lower win rate
  - Market closing → SKIP with reason

## 2. VISUAL REDUNDANCY AUDIT

For each information item, I ask: "where does this appear?" If more than
one place, that's suspect. Allowed duplication:
- Selected trade header + inline in middle (scannability vs detail)
- Position in top-3 card + position in middle monitor (separate purposes:
  top card = "should I take more?", middle = "what's this one doing?")

Forbidden duplication that I should have caught:
- [ ] Consensus pros/caveats — middle full + right full (FIXED v35)
- [ ] Macro chips — header + middle + right (FIXED v35)
- [ ] GIFT NIFTY gap + VIX — middle macro + right externals (FIXED v35)

Before ship, I grep for "renderConsensusPanel|renderExternalsPanel|
renderLivePositionsPanel" to make sure they're only called ONCE from
the main panel (not duplicated across middle and right columns).

## 3. FAKE-DATA FALLBACK AUDIT

Vijay's core principle is "no fake data." I scan for patterns that
silently substitute plausible-looking defaults:

- [ ] `|| 50` (score fallback)
- [ ] `|| 1` (beta default)
- [ ] `|| 14` (RSI neutral)
- [ ] `[confidence, confidence, confidence]` or similar repeated fallbacks
- [ ] `Math.max(x, 1)` where x could legitimately be 0
- [ ] `|| spot` (sma fallback)
- [ ] Any ternary like `hasData ? realValue : plausibleDefault`

If any exist, they must be either:
  (a) genuinely absent → `0` or `null` with `status: 'no_data'` flag
  (b) flagged in the UI so user knows it's synthesized
  (c) documented why the fallback is safe

This is how I missed the scanner trend. `[c, c, c]` is a repeated-value
fallback that produces flat gray ■. I should have asked: "what does
this look like when history.length < 2?"

## 4. CONFIG-VS-FEATURE CONSISTENCY CHECK

Every time I touch a new feature, I check: does any existing config
value silently defeat this feature?

- [ ] `cooldownSeconds: 60` — defeats "execute 3 top trades" flow
- [ ] `maxConcurrent: 3` — aligned with top-3 ✓
- [ ] `maxDailyLossPct: 3` — reasonable
- [ ] Server cache TTL vs 5m scan interval — must be consistent

I should have caught the 60s cooldown when I shipped the 3-col layout
that shows 3 executable trades simultaneously. The feature said
"here are 3 trades to take" and the config said "only one per minute."

## 5. VOICE COVERAGE ACTUALLY HELPFUL

For every voice line fired, I read it out loud (mentally) and ask:
- Would a user understand this without knowing options jargon?
- Does it include the context they need (symbol, P&L %, action)?
- Is it shorter than 2 sentences? (longer = voice queue backs up)
- Does it follow Quick Trade's plain-English style?

Bad: "GEX regime flipped negative" (jargon, no action)
Good: "FINNIFTY has lost institutional support. Consider closing the position."

## 6. ACROSS-ROUNDS REGRESSION CHECK

Before cache bump, I re-run all N test suites. If any regressed, I
investigate WHY — maybe the previous test was wrong (fine to update),
maybe the new change broke something (fix the code, not the test).

I document which tests were deliberately updated in the ship message
("test-round2 cooldown assertion updated to match new 5s config").

## 7. SCREENSHOT SANITY CHECK

For UI changes, I describe what the screen will look like in the ship
message BEFORE the user sees it. If my description sounds redundant,
cluttered, or confusing, it probably is.

"The left column now shows MY POSITIONS (2) with two cards, then a
dashed separator 'TOP 3 NEW OPPORTUNITIES', then three more cards."

If that's 5 cards stacked in a narrow 28% column with 104px each =
520px of cards. Does that fit? Does it scroll? Does the user have to
scroll past held positions to see new ones? These are questions I
should be asking myself.

## 8. EXPLICIT PASS/FAIL BEFORE SHIP

My ship message now includes:

```
PRE-SHIP CHECKLIST (v{N}):
  [x] Multi-trade stack walked — all 3 execute, 4th blocks
  [x] Held-trades rotation walked — off-scan shows in MY POSITIONS
  [x] Position close walked — badges + banner + voice fire
  [x] Visual redundancy grep clean — no panel called twice
  [x] Fake-data fallback grep clean — no `|| 50` `[x, x, x]` etc.
  [x] Config consistency — cooldown < click-cadence
  [x] Voice lines read plain English — no jargon
  [x] All {N} test suites exit=0
  [x] Regression root-caused — test-round2 cooldown assertion updated
```

If any item is unchecked, I say "not ready" instead of sending the zip.

---

## WHY THIS EXISTS

Vijay called out three rounds in a row where I shipped code that tested
green but broke the UX:

- v35 — redundant consensus panel in right column
- v37 — 60s cooldown blocked taking all 3 top trades
- v38 — scanner trend showed flat 95→95→95 on every row

Each was a question he should not have had to ask. The test suite didn't
catch any of them because tests assert logic, not UX. This checklist is
the gap-filler.

I commit to running it before every ship, and to including the checklist
output in the ship message so Vijay can see what I checked.
