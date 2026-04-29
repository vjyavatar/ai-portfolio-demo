# Celesys v4 — Changelog

Most recent at top. Sub-versions cumulative — each one builds on the previous.

---

## v4.61.10 — Production cumulative (current)

**Built:** 2026-04-29 · Single-zip cumulative of all r61.x work

**Stamped in 7 places:**
- `/api/version` endpoint returns `{"version": "v4.61.10", ...}`
- `APP_VERSION` constant in `api.py`
- `window.CELESYS_VERSION` in JavaScript
- DevTools Console banner on page load
- `<meta name="celesys-version">` in `index.html`
- Visible footer stamp (bottom-right corner)
- Cache-bust hash on all JS/CSS

**To verify deployed version after push:**
```bash
curl https://celesys.ai/api/version
```
Or look at the bottom-right corner of the page, or open DevTools console.

---

## r61.10 — Version stamping (this deploy)
- Single canonical version: **v4.61.10**
- 7-way stamping (endpoint + constant + window + console + meta + footer + cache-bust)
- CHANGELOG.md added
- No functional changes — just identification

## r61.9 — Deep DD report Aladdin shell (BUILT, DISABLED)
- Sidebar nav with 17 sections + scroll-spy
- Compact verdict strip (~80px instead of ~250px)
- 5-cell quick stats strip
- **DEFAULTS TO OFF** — enable in DevTools: `window._csDdShellEnabled = true`
- Reason for disabling: anchor-injection logic not validated against real data yet

## r61.8 — Aladdin DD entry page + stale-cache fallback
- Rebuilt the ticker-input screen (no more purple "What you get" box)
- 7-day stale cache: returns last-known-good data when Yahoo rate-limits
- Inline error states (RETRY button next to input)
- Recent-tickers tracking via localStorage

## r61.7 — Multi-factor Bottom Line + complete layman coverage
- Bottom Line composite score across 10 weighted factors (was 4)
- Factor breakdown table (Quality, Value, Sector momentum, Earnings execution, Risk-adj returns, Drawdown risk, Insider signal, Inst confidence, Peer leader, 1Y momentum)
- Layman blocks added to 4 missing sections (Thesis, Financial Health, Sector Context, SWOT)
- Earnings Move Intelligence layman block (BUY_PREMIUM / SELL_PREMIUM / NEUTRAL explanation)
- MU now scores 37/100 HOLD instead of 100/100 STRONG BUY (honest synthesis)

## r61.6 — Combined Institutional Summary card
- Re-introduced gestalt narrative as a "🏛 INSTITUTIONAL SUMMARY" card
- Renders BEFORE the 5 individual sub-cards (insider/holders/risk-adj/peers/chart)
- Navy-bordered to distinguish from sub-cards
- Each sub-card keeps its own focused layman

## r61.5 — Earnings Intel friendly messages
- "Missing 4 key fields: earnings_history, next_earnings_date, post_earnings_moves, implied_move_inputs" → "No upcoming earnings catalyst on the calendar..."
- Context-aware messages based on what's missing
- Technical field list still preserved in `_missing_technical` for debugging

## r61.4 — Split institutional layman + enriched all laymen
- Separate sub-laymen: insider_activity, institutional_holders, risk_adjusted, peer_table, price_chart
- Each sub-card describes only its own data (no cross-bleed)
- Enriched with specific numbers: Sharpe 1.46, 82% inst ownership, -$3.50M net flow

## r61.3 — Three critical bug fixes
- **Insider $ values**: parse from transactions even when summary path provides counts (no more fake $0.00M)
- **Bottom Line score field**: read `thesis["investability_score"]` not `thesis["score"]` (fixes 0/100 AVOID vs 100/100 STRONG BUY mismatch)
- **30-min DD cache** + 7-day stale cache infrastructure

## r61.2 — Insider Activity NEUTRAL 0/0 fix
- Two-strategy fetch: `insider_purchases` summary + `insider_transactions` fallback
- Robust column detection (Shares vs Shares Traded, Position vs Relation, etc.)
- Honest INCOMPLETE state instead of fake NEUTRAL with all zeros

## r61.1 — Layman blocks + Bottom Line synthesis
- Backend layman generation for all sections (PLAIN + NOTE)
- Bottom Line synthesis card at top: verdict, headline, watch, concerns, ideal_for
- Frontend hooks for 6 sections initially (extended to 16 in r61.7)

## r61.0 — Design system foundation
- `static/celesys-ds.css` (568 lines) — Aladdin-style tokens, components, layout primitives
- `/ds-preview` route serving design system mockup
- Light theme + navy + medium density confirmed
- Zero production screen changes

---

## r60.x — Institutional sections + scoring fixes

### r60.4 — 6 NEW Deep DD institutional sections
- Earnings Move Intelligence (mirrored into DD from Active Trading)
- Insider Activity (US: yfinance Form 4; India: NSE promoter %)
- Institutional Ownership (US: top 10 13F; India: DII/FII split)
- Peer Comparison Table (subject vs peers, ★ on best metrics)
- 1-Year Price Chart (SVG sparkline + return %)
- Risk-Adjusted Returns (Sharpe + Max DD + Vol with grades)
- Active Trading Earnings panel moved from position 8 → position 2 in scroll

### r60.3 — Deep DD India fallback + 4 institutional sections
- NSE + Google Finance fallback wired into DD endpoint
- Catalysts (next earnings + analyst targets + short interest + dividend)
- Valuation Detail (DCF intrinsic value)
- Quarterly Earnings History (8-Q beat/miss)
- Risk Matrix v2 (passed checks)

### r60.2 — Earnings Move Intelligence + Universe Filter wired
- `earnings_intel.py` module (BUY_PREMIUM / SELL_PREMIUM / NEUTRAL / INCOMPLETE)
- `data_sources.py` (region-aware fallback layer)
- Universe filter wired into Active Trading scanner

### r60.1 — Universe Filter Bar UI
- Universe pills in Active Trading (ALL / LARGE / MID / SMALL / MICRO / ETF) with live counts

### r60.0 — Porter Five Forces fix + Universe Classifier
- Porter formula fixed: `max(0, min(50, round(50 - avg*5, 1)))` (was outputting 25-70 with "/50" display)
- `universe_classifier.py` with 755 tickers (IN: 366, US: 389)
- 3 routes: `/api/universe`, `/api/universe-classify`, `/api/universe-stats`

---

## How to verify which version is deployed

After every push, run any ONE of these:

```bash
# From terminal:
curl https://celesys.ai/api/version

# From browser DevTools console:
window.CELESYS_VERSION

# Look at bottom-right of any page:
# Tiny "v4.61.10" stamp visible
```

If you see the OLD version after deploying, your browser is caching the old JS. Hard-refresh: Ctrl+Shift+R (Windows/Linux) or Cmd+Shift+R (Mac).

---

## v4.61.11 — Disk-backed cache (current)

**Built:** 2026-04-29 03:29 UTC

**The fix:** `_smart_cache` is in-memory only — every Render redeploy wiped it, leaving fresh deploys with cold cache. Combined with Yahoo rate-limiting, that meant "Could not retrieve data" on the first request after every push.

**What's new:**
- Disk-backed cache layer at `/tmp/celesys_dd_cache.json`
- On DD success → write to memory AND disk
- On startup → hydrate memory cache from disk (cache survives redeploys)
- Pre-seed top tickers in background (NVDA, AAPL, MSFT, GOOGL, META, TSLA, AMZN, JPM + RELIANCE, TCS, INFY, HDFCBANK)
- `/api/version` now reports `dd_disk_cache` stats: `{exists, size_bytes, n_entries, age_sec}`
- 4 startup hooks (FastAPI 0.104.1 supports stacking): existing prefetch loop + hydrate + pre-seed + (your existing handlers)

**How to verify:**
```bash
curl https://celesys.ai/api/version
```
Should now return `dd_disk_cache: {exists: true, n_entries: ...}` after the first successful DD.

**Pre-seed pacing:** 8s between requests, 15s back-off on errors. Skips if disk already has ≥5 entries (avoids hammering Yahoo on every redeploy).

---

## v4.62.0 — Micro-Cap Hunter (current)

**Built:** 2026-04-29 04:01 UTC

**New feature:** Discovery scanner in Decide tab. Runs the existing 90 US + 60 India micro-cap universe (curated in r55) through a 7-factor light-weight screen. Returns ranked candidates with one-click handoff to Deep DD.

**7 scoring factors (max 100):** Profitability, Revenue Growth, Balance Sheet, Insider Ownership, Short Squeeze, Momentum, ROE.

**3 hard filters:** Price > $1 (no penny stocks), avg daily $vol > $500K (no illiquid), no distress (negative book + heavy debt).

**Backend:** `/api/microcap-hunter?region=US&min_score=40&limit=20` — 30-min cache + persists via v4.61.11 disk layer.

**Frontend:** New "🎯 Micro-Cap Hunter" sub-tab under Decide. Aladdin-grade list of candidates. Click any row → opens Deep DD for that ticker.

**Honest disclaimer baked in:** "Micro-caps are HIGH RISK. ~30% decline >50% in any 6-month window. Hunter score is a quick screen — always run Deep DD before any trade."

---

## v4.62.1 — Fix High-Prob Setups 62% bug (current)

**Built:** 2026-04-29 13:42 UTC

**The bug:** User reported all High-Prob Setups returning 62%. Investigation found 3 hardcoded confidence buckets in `_compute_high_prob_setup`:
- `criteria_met >= 4` → 75%
- `criteria_met >= 2` → 62%  ← almost everything landed here
- `criteria_met >= 1` → 50%

**The fix:** Replaced with continuous 0-100 score from 6 weighted components:
- Setup confluence (30 pts max)
- Setup quality / Minervini hierarchy (20 pts)
- Risk/reward favorability (15 pts)
- Trend alignment / above MAs (15 pts)
- Volume confirmation (10 pts)
- Action cleanness (10 pts)

**Validation:** Simulated 5 representative setups — produces scores 23, 49, 63, 64, 90 instead of all 62. Weak setups (<35) now filtered entirely.

**Also added:** `score_components` array in API response (frontend can render as breakdown later).

**Honest disclaimer revised:** No more "Historical win rate ~75-80%" — replaced with execution-discipline guidance per band.

---

## v4.62.2 — Intraday & Swing Setups (current)

**Built:** 2026-04-29 13:50 UTC

**New feature:** Decide → ⚡ Intraday Setups. 3 setups with PUBLISHED literature base rates (cited):

1. **Opening Range Breakout** (Crabel 1990, 53-58% base) — INTRADAY
2. **VWAP Reclaim After Open Drive** (Berkowitz/Raschke, 60-65% base) — INTRADAY
3. **Inside-Day Continuation** (Bulkowski, 55-60% base) — 2-DAY SWING

**Universe:** Liquid only — S&P 100 ex-financials (87 US tickers), Nifty 50 (50 IN). Liquidity gate >$1B mcap + >$10M daily $vol enforced for US.

**Honest framework:** Every response carries a disclaimer that literature base rates ≠ user's real win rate (typically 5-15% lower in live execution). Per-setup caveats explain when each base rate does/doesn't apply.

**6 runtime tests passed:** ORB detects long/short/rejects chop, Inside-day detects uptrend/rejects-non-inside/rejects-no-trend.

**Backend:** `/api/intraday-setups?region=US&timeframe=all|intraday|swing` — 5-min cache for intraday, 30-min for swing-only.

**No backtests, no fake win rates, no micro-caps in this scanner.**

---

## v4.62.3 — Production loading states (UX fix, current)

**Built:** 2026-04-29

**The bug:** User reported loading screen sat with static text "Pulling 5-min bars..." with no spinner, no timer, no abort. Below production standard.

**The fix:** Reusable `_csLoader()` helper + `_csFetchWithTimeout()` helper. Applied to both Intraday Setups (r62.2) and Micro-Cap Hunter (r62.0) — the two loaders I shipped without proper UX.

**`_csLoader()` provides:** spinner (CSS animation), title+subtitle, mutable status line, indeterminate progress bar, live elapsed time counter (color-escalates if slow), estimated typical time, CANCEL button.

**`_csFetchWithTimeout()` provides:** 2-minute hard timeout via AbortController, proper cleanup, AbortError → actionable retry message.

**Verified:** 8/8 loader components present, helper code eval-tested, both loaders use new pattern.

**Honest note:** This pattern was already established in your codebase (lines 6005, 6917, 10074). I didn't follow it when shipping r62.0/r62.2. That's on me — fixed now.
