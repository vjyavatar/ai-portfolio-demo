# Quick Trade → Active Trading Feature Parity Audit

**Total features in Quick Trade:** 33 render functions across 21 feature areas.
**Goal:** Decide what actually needs porting before writing any code.

## Priority legend

- 🔴 **Critical** — User cannot trade confidently without this. Must port.
- 🟠 **High** — Meaningfully improves decisions. Port after Critical.
- 🟡 **Useful** — Nice to have. Port if time permits.
- ⚪ **Skip** — Superseded, redundant, or low-value.
- ✅ **Already in AT** — No port needed.

---

## Feature inventory

| # | Feature | Function | In AT? | Priority | Reason / Notes |
|---|---|---|---|---|---|
| 1 | Candlestick chart + VWAP overlay | `_renderCandlestick` | ❌ | 🔴 Critical | Trader needs visual confirmation of structure. AT has numbers only. |
| 2 | Greeks (Δ/Γ/Θ/Vega) display | `_renderGreeks` | ❌ | 🔴 Critical | Can't trade options without knowing theta bleed + gamma exposure. |
| 3 | IV vs HV ratio | `_renderIVvsHV` | ❌ | 🔴 Critical | Tells trader if options are overpriced/underpriced. |
| 4 | Payoff diagram at expiry | `_renderPayoff` | ❌ | 🟠 High | Visualizes max loss / breakeven / profit cone. |
| 5 | Strike selector (ITM/ATM/OTM) | `_renderStrikeSelector` | ❌ | 🟠 High | AT auto-picks ATM only. User may want to override. |
| 6 | GEX heatmap (Call/Put walls) | `_renderGEXHeatmap` | ❌ | 🟠 High | Institutional — shows where dealers are forced to hedge. |
| 7 | Backtest simulation | `_renderBacktestSim` | ❌ | 🟡 Useful | We have tools/backtest harness. Duplicate inline? |
| 8 | BP (Buying Power) calibration | `_renderPerformanceDashboard` | ❌ | 🟡 Useful | Historical calibration of signals. |
| 9 | IV term structure | `_renderIVTermStructure` | ❌ | 🟡 Useful | Shows expiry-by-expiry IV curve. Helps pick expiry. |
| 10 | Order flow / liquidity analytics | `_renderOrderFlow` | ❌ | 🟠 High | Shows bid/ask depth — critical for slippage estimation. |
| 11 | Swing trading card (days/weeks) | `_renderSwingCard` | ❌ | ⚪ Skip | Different timeframe, different engine. Keep in QT for now. |
| 12 | Trade scanner (ribbon view) | `_renderScanRibbon` | ✅ | — | AT has Top Trades + Secondary Scanner. |
| 13 | Buy Now card | `_renderBuyNowCard` | ✅ | — | AT's trade cards serve this purpose. |
| 14 | Buy Now mini | `_renderBuyNowMini` | ✅ | — | Same. |
| 15 | Sentiment bar | `_renderSentimentBar` | ❌ | 🟡 Useful | Fear/Greed composite. AT could show as header chip. |
| 16 | Smart insights | `_renderSmartInsights` | ❌ | 🟡 Useful | Mixed bag — some valuable, some noisy. |
| 17 | Trend compass (long vs short) | `_renderTrendCompass` | ❌ | 🟠 High | Shows if signal aligns with daily/weekly trend. |
| 18 | GIFT NIFTY pre-market | `_renderGiftNiftyTicker` | ❌ | 🟠 High | India-specific pre-market indicator. |
| 19 | US pre-market ticker | `_renderUSPremarketTicker` | ❌ | 🟠 High | US-specific pre-market. |
| 20 | Alerts panel | `_renderAlerts` | ❌ | 🟡 Useful | Custom price/score alerts. AT has voice triggers. |
| 21 | Auto panel (auto-scan) | `_renderAutoPanel` | ✅ | — | AT has auto-scan timer. |
| 22 | Coaching tips | `_renderCoaching` | ❌ | ⚪ Skip | Nice-to-have, not trading-critical. |
| 23 | Count (position counter) | `_renderCount` | ⚠️ Partial | 🟡 Useful | AT has Paper chip — could show contract count too. |
| 24 | Gamification | `_renderGamification` | ❌ | ⚪ Skip | Streaks/badges. Distraction, not alpha. |
| 25 | Live tracker | `_renderLiveTracker` | ⚠️ Partial | 🟡 Useful | AT has header with live stats. QT version may have more. |
| 26 | Performance dashboard | `_renderPerformanceDashboard` | ❌ | 🟡 Useful | Shows historical hit rate by band. AT has alpha decay — similar. |
| 27 | Scan card | `_renderScanCard` | ✅ | — | AT trade cards. |
| 28 | Trade monitor | `_renderTradeMonitor` | ⚠️ Partial | 🟠 High | Tracks open trades live. AT has paperPortfolio but no UI panel. |
| 29 | User guide | `_renderUserGuide` | ❌ | ⚪ Skip | Documentation, not trading feature. |
| 30 | Bottom nav (auto-scan) | `_renderBottomNav` | ✅ | — | AT scanner IS this. |
| 31 | Options nav (mode switcher) | `_renderOptionsNav` | N/A | — | N/A — AT is the mode, not a switcher. |
| 32 | Backtest (results display) | `_renderBacktest` | ❌ | 🟡 Useful | View results from backtest runs. |
| 33 | Price Action Monitor | (inline) | ❌ | 🟠 High | Real-time candle-by-candle alert system. |

## Non-rendering features (but still Quick Trade capabilities)

| # | Feature | Notes | In AT? | Priority |
|---|---|---|---|---|
| A | Black-Scholes pricing engine | `_erf` + internal | ❌ | 🔴 Critical | Needed for Greeks, fair value, IV calc. |
| B | Signal reversal voice | Inline block | ⚠️ Partial | 🟡 Useful | AT has exit voice but not "reverse and flip" logic. |
| C | Ultra-simple mode | `_renderUltraSimple` | ❌ | ⚪ Skip | Beginner mode. AT is already its own simplicity. |
| D | Unified scoring function | `_unifiedScore` | ⚠️ AT has own | ⚪ Skip | AT has `_unifiedScore` equivalent built in. |
| E | Session Profile (Asia/EU/NY) | Enhancement 1 | ❌ | 🟡 Useful | Session-aware scoring. |
| F | VWAP enhancements (bands) | Enhancement 2 | ⚠️ Partial | 🟠 High | AT has VWAP alignment factor, no bands. |
| G | Intraday Vol (ATR, Keltner) | Enhancement 4 | ⚠️ Partial | 🟠 High | Expected move + squeeze detection. |
| H | Portfolio Risk Controls | Enhancement 5 | ❌ | 🔴 Critical | Daily loss caps, max concurrent positions, drawdown circuit breaker. |
| I | Strategy Performance (Sortino) | Enhancement 6 | ⚠️ Partial | 🟡 Useful | AT has alpha decay which is related. |
| J | India VIX term structure + FII/DII | Enhancement 7 | ❌ | 🟠 High | India-institutional specifics. |
| K | Sector rotation awareness | Inline | ❌ | 🟡 Useful | Penalizes signals against sector trend. |

---

## Consolidated porting plan

### Round 2 (next) — 🔴 CRITICAL BLOCK

These 4 are table-stakes for trading options. Cannot retire QT without them.

1. **Black-Scholes + Greeks** — Δ, Γ, Θ, Vega, ρ for selected contract
2. **IV vs HV panel** — is this option overpriced relative to 10d realized?
3. **Portfolio Risk Controls** — daily loss cap, max concurrent, DD circuit breaker
4. **Candlestick chart with VWAP** — visual structure confirmation

### Round 3 — 🟠 HIGH-VALUE BLOCK

5. **GEX Heatmap** — Call/Put walls, gamma flip point
6. **Strike Selector** — let user override ATM choice (ITM/OTM)
7. **Trade Monitor** — live P&L panel for open paper positions
8. **Trend Compass** — intraday signal vs daily/weekly trend alignment

### Round 4 — 🟠 INDIA/US SPECIFIC

9. **GIFT NIFTY pre-market ticker** (India)
10. **US pre-market ticker** (US)
11. **India VIX term structure + FII/DII**
12. **Order flow / liquidity analytics**

### Round 5 — 🟡 NICE-TO-HAVE

13. **Payoff diagram**
14. **IV term structure**
15. **Sentiment bar**
16. **Session profile (Asia/EU/NY)**
17. **ATR + expected move + Keltner squeeze**

### Round 6 — VERIFY + RETIRE QUICK TRADE

18. Cross-check feature parity session by session
19. Remove Quick Trade button from Decide tab
20. Archive `options-engine.js` (don't delete — keep as reference)

### SKIP (don't port)

- Swing trading card — different timeframe, needs separate engine
- Gamification — distraction
- Ultra-simple mode — AT is already simple
- User guide — docs, not engine
- Coaching tips — nice but not alpha

---

## What I propose for THIS round

Rather than start porting immediately, I should:

1. **Get your buy-in on this plan.** If you disagree with any priorities (e.g., you want Payoff diagram sooner, or you care about Gamification), correct me now.

2. **Start Round 2 with the absolute highest-leverage feature: Black-Scholes + Greeks.**
   - It's the single biggest trading-UX gap
   - It unblocks IV vs HV, Payoff, and GEX (all depend on pricing math)
   - I can port it cleanly (~300 lines), add tests, ship, in one round
   - Then you've got Delta/Theta/Vega on every AT trade card within hours

## Why this approach vs "just port everything"

If I try to port everything at once:
- You get 12,000 lines of hastily-copied code with bugs I won't catch
- Tests break, dark theme breaks, voice breaks
- Quick Trade features embedded in a codebase not designed for them will feel awkward
- You'll give up trusting the zip files

If I port 1-2 features per round with tests:
- Each feature ships verified and usable immediately
- Active Trading stays < 8k lines and maintainable
- You can use each port in production before the next one lands
- In 5 rounds, we actually replace Quick Trade for real

## One more honest thing

The reason Quick Trade is 11.7k lines isn't that you asked for all of it in one go. It grew over months, one feature at a time. Active Trading can grow the same way — the right way is **feature-by-feature**, not all-at-once.
