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

---

## v4.62.4 — /api/version diagnostic fix (current)

**Built:** 2026-04-29 18:25 UTC

**The mistake:** v4.61.11 claimed `/api/version` would expose disk cache stats. The patcher silently skipped that change. User correctly noticed when their `/api/version` response lacked the documented fields.

**The fix:** Restored the diagnostic fields in `/api/version`:
- `dd_disk_cache` (exists, size_bytes, n_entries, age_sec)
- `memory_cache_size`
- `dd_cached_tickers` (sorted list, capped 50)
- `dd_cached_count`

**Pure diagnostic deploy.** Nothing user-facing changed. No new features. Lowest possible risk.

**Why this matters:** Without these fields visible we can't diagnose whether Yahoo blocking is permanent or transient. With them visible, the next /api/version output tells us exactly what to do next (add Stooq fallback, expand pre-seed list, or wait it out).

---

## v4.63.0 — Finnhub Integration (current)

**Built:** 2026-04-29 19:02 UTC

**Why:** Yahoo blocks Render's datacenter IP. Every US DD request was failing. Multi-factor Bottom Line, Hunter, Intraday Setups all couldn't get fundamentals data.

**What:** Wired Finnhub free tier API as primary US data source. yfinance becomes fallback. India chain unchanged (NSE direct still works).

**Architecture:**
- New `finnhub_handlers.py` module (~290 lines, clean isolated)
- Registered in `data_sources.py` `_HANDLERS` dict
- `_CAPABILITIES` updated: `["finnhub", "yfinance", "google_finance"]` for US
- DD endpoint in api.py: tries Finnhub first, merges with yfinance gaps, falls back gracefully
- `/api/version` exposes Finnhub diagnostics (enabled, has_key, calls_total, calls_success, last_error)

**Adapter:** Synthesizes yfinance-compatible `info` dict from 3 Finnhub endpoints (`/quote`, `/stock/profile2`, `/stock/metric`). 37 of yfinance's ~80 fields populated. Percentage-to-decimal conversion. Market cap millions-to-raw-dollars. Volume thousands-to-raw.

**Free tier coverage:** Quote + OHLC + market cap + sector + P/E + margins + ROE + growth + 50/200d MA + 52w high/low + earnings surprises. ~80% of what Deep DD needs.

**Free tier gaps:** Insider transactions, 13F institutional holders, short % of float, analyst targets, detailed financial statements. These DD sections render "data unavailable" gracefully when Yahoo blocked. To upgrade, switch to Finnhub Personal/Fundamentals tier (~$50/mo) — env-var swap, no code.

**Kill switch:** `FINNHUB_DISABLED=1` env var → instantly falls back to yfinance + GF + NSE (pre-r63.0 behavior).

**Rate limit:** 1.2s pacing internal (free tier is 60/min). Hunter/Intraday scans first-run ~108s for 90 tickers, cached afterward.

**Tested:** Kill switch, IN region skip, stats shape, 37-field adapter output with correct decimal/millions conversions. NOT tested against live Finnhub key (deploy is the real test).

---

## v4.63.1 — PDF Export for Deep DD (current)

**Built:** 2026-04-29 19:08 UTC

**What:** Floating toolbar appears top-right of every Deep DD report with 3 icon buttons:
1. 📄 PDF — generates branded multi-page PDF and triggers download
2. 🖨 Print — opens browser's native print dialog
3. 🔗 Copy URL — copies shareable link to clipboard

**Each button has a hover tooltip** explaining what it does, plus aria-labels for accessibility, focus rings for keyboard users, smooth hover transitions to navy theme color.

**PDF structure:**
- Page 1: Navy header with CELESYS brand, large ticker, subtitle, section list, amber disclaimer block, footer
- Pages 2-N: The on-screen report captured at 1.5× resolution, sliced into A4 pages with footers
- Filename format: `Celesys_DD_{TICKER}_{YYYY-MM-DD}.pdf`

**Architecture:** Client-side via jsPDF + html2canvas (CDN-loaded, cached). Zero server impact. Uses report already on screen — no refetching.

**Verified:**
- 15/15 audit checks pass
- Runtime simulation: function evaluates + runs to completion with mock libs, generates correct filename
- 7/8 toolbar UI checks (PDF/Print/Copy buttons all wired with tooltips + aria-labels + SVG icons)
- Caught + fixed dead-code typo in PDF cover (var dlY = pdf - 36 → removed)
- Sample preview PDF rendered to verify cover page layout

**Print mode:** CSS @media print hides the toolbar so print preview is clean.

**Auto-inject:** Polling every 800ms checks if DD content changed; injects toolbar after render. Stops after 10 min of inactivity.

**No backend changes. No new dependencies on Render. No new env vars.**

---

## v4.63.2 — Fix r63.0 regression (current)

**Built:** 2026-04-29 19:23 UTC

**The bug user reported:** Deep DD report on MU showed Finnhub-sourced verdict + financials correctly, but Risk Matrix body, SWOT, Porter scores, Insider Activity, Institutional Holders, and Earnings History sections were all empty/N/A.

**Root cause:** r63.0 made Finnhub primary but had two issues:
1. yfinance `tk` Ticker was only created when Finnhub failed → when Finnhub succeeded, `tk` was undefined
2. Downstream sections gated on `data_source == "yfinance" and tk:` — when Finnhub succeeded, this condition skipped entire institutional/insider block

**The fix (3 targeted changes):**
1. ALWAYS create yfinance Ticker for US tickers — gives downstream sections a real `tk` to call
2. Replace `data_source == "yfinance"` gates with `tk is not None and region == "US"` — sections try yfinance regardless of primary
3. Improved merge logic: Finnhub fields stay, yfinance fills gaps. Diagnostic logs distinguish "yfinance merged X fields" (Yahoo allowing) vs "yfinance .info empty (Yahoo blocked)" (graceful degradation)

**Verified:**
- 8/8 audit checks pass
- 4-scenario simulation passes:
  - Finnhub HIT + Yahoo OK → full report
  - Finnhub HIT + Yahoo BLOCKED (user's case) → Finnhub data + N/A markers
  - Finnhub MISS + Yahoo OK → pure yfinance path preserved
  - Both fail → graceful, no crash

**Result:** Either user gets full report (if Yahoo allows yfinance for these specific endpoints — common surgical IP blocking) OR gets degraded report with honest "data unavailable" markers (if Yahoo blocks everything). Either way, no more silent empty sections.

---

## v4.63.3 — Fix Earnings Move tzinfo crash (current)

**Built:** 2026-04-29 19:38 UTC

**The bug user reported:** Screenshot showing "Earnings Move Intelligence: Fetch failed: 'str' object has no attribute 'tzinfo'"

**Root cause:** Schema mismatch between data sources:
- yfinance returns earnings dates as datetime objects (have .tzinfo)
- Finnhub returns earnings dates as strings ("2024-10-23")
- earnings_intel.py:_next_session_move() calls .tzinfo on the date
- After r63.0 made Finnhub primary for earnings, this crashed every time

**Fix:**
1. `finnhub_handlers.py:get_earnings_history` converts dates to datetime before returning + adds `beat` field for yfinance schema compatibility
2. `earnings_intel.py:_next_session_move` defensively coerces strings→datetime as belt-and-suspenders (handles future schema variations safely)
3. `earnings_intel.py` line 193 d_aware also defensive

**Verified:**
- 5/5 audit checks pass
- 6 runtime tests pass: string ("2024-10-23") → 10.36%, datetime → 10.36%, tz-aware → 10.36%, None → None safely, invalid → None safely, ISO with time → 10.36% (correct slicing)

**Honest acknowledgment of what's NOT fixed:** Insider Activity and Institutional Ownership sections still show "data not available" — that's Yahoo blocking those specific endpoints from Render IP. Free-tier Finnhub doesn't have these. Real fixes: wait for Yahoo to recover, upgrade Finnhub (~$50/mo), or build SEC EDGAR fallback (free but more work).

---

## v4.63.4 — Email replacement + tier centralization (current)

**Built:** 2026-04-30 14:42 UTC

**User request:** Replace `bbk@asl.com` → `yrk@eml.com` everywhere AND apply solution-architect best practices to centralize duplicated email lists.

**Email change:** Pure replace. Zero remaining occurrences of `bbk@asl.com` in api.py, app.js, or app.min.js. `yrk@eml.com` granted exact same tier access bbk had. Other emails (`vj@vnky.com`, `tmp@cls.com`) untouched.

**Architectural refactor:**
- Backend: 2 hardcoded lists (`TRADES_ALLOWED_EMAILS`, `DREAM_ALLOWED_EMAILS`) replaced with single `PREMIUM_TIERS` dict + `has_tier()` helper. Backwards-compat aliases preserve all 15+ existing call sites.
- Frontend: 4 hardcoded `const X_EMAILS=[...]` lists replaced with single `window.CELESYS_TIERS` object + `window.hasTier()` helper. Backwards-compat aliases preserve existing callers.
- 2 inline literals (`app.js:23900`, `app.js:24046`) refactored to use centralized definitions.
- Pre-computed lowercased frozenset lookup (was list comprehension on every request — 15+ hot paths).

**Tested:**
- 19 audit checks pass
- 13 backend access control tests pass (incl. case-insensitive, whitespace-stripped, defensive None handling)
- 18 frontend hasTier tests pass
- 8 backwards-compat alias tests pass

**Honest note on drift:** Pre-existing drift between backend/frontend trades tier (frontend has `tmp@cls.com`, backend doesn't) preserved as-is. Refactor doesn't change behavior — just makes drift visible in one place per language for future audit.

**To grant access to new user (going forward):** Add email to `PREMIUM_TIERS` (api.py) AND `window.CELESYS_TIERS` (app.js). Two places instead of 6+.

---

## v4.63.5 — DRY refactor: premium-gate centralization (current)

**Built:** 2026-04-30

**Audit-driven scope:** User asked to proactively identify repeated code. I scanned codebase, found ~5 candidate patterns, rejected 4 as poor ROI (inline CSS, response shapes, intentional helpers), refactored 1 high-value target.

**The fix:**
- 10× duplicated 7-line premium-gate boilerplate → single `check_premium_gate(email, tier)` helper
- 5× frontend `TRADES_EMAILS.includes(email)` → `hasTier(email, 'trades')` for consistency

**Verified:**
- 9-scenario behavior parity test passed (new helper = identical results to old code)
- 3-attempt iteration on regex (caught my own mismatches in audit, didn't ship broken)
- Line count: 36330 → 36327 (helper +25 lines, gate replacements -28 lines)
- Maintainability: 10 places → 1 place

**Honest scope discipline applied:**
- Inline CSS (22×): NOT refactored — UI rewrite, high regression risk
- Currency formatting (31×): NOT refactored — too short, negative ROI
- Response builders (266×): NOT refactored — that's how FastAPI endpoints work
- Yahoo rate-wait (82×): NOT refactored — already a helper, intentional calls
- Safe-coerce (49×): NOT refactored — the helper itself

**Going forward:** Adding a premium tier = 2 places (PREMIUM_TIERS + CELESYS_TIERS) + use helpers.

---

## v4.63.6 — Find Similar Stocks scanner (current)

**Built:** 2026-04-30

**User request:** "Based on MU in deep dd, list shares which meet same criteria... like penny shares, less than 50, less than 100 etc."

**What:** New `/api/find-similar-stocks` endpoint + frontend modal. Click "🔍 SIMILAR" button on Deep DD toolbar → scans universe → returns stocks bucketed by price tier with similarity scores.

**Architecture:**
- 3-component similarity: 40% verdict proximity + 35% fundamental distance + 25% risk/momentum distance
- 5 price tier buckets per region in native currency (US: penny <$10 → $250+; IN: penny <₹100 → ₹3000+)
- Reuses existing DD endpoint logic + _smart_cache (30 min TTL)
- Parallel batch scanning (8 concurrent) — ~2-4 min cold, instant warm
- Top 5 per bucket, sorted by similarity desc

**Universe:** ~80 US tickers (curated mega+large+midcap) + ~110 India tickers (Nifty 50/Next 50 + Midcap)

**Frontend:** Auto-injects 🔍 SIMILAR button into DD toolbar (alongside PDF/Print/Copy from r63.1). Modal shows reference profile + 5 buckets + similarity breakdowns + matching factors. HTML-escaped to prevent XSS.

**Premium gating:** Uses `check_premium_gate()` helper from r63.5 (Dream tier required).

**Verified:**
- 11/11 audit checks pass
- 5/5 synthetic similarity math tests pass (perfect clone=100, same-sector peer=90, different-sector-same-verdict=76, opposite=28, high-verdict-different-fundamentals=77)
- Compile + JS syntax + byte-identical min.js
- Caught + fixed f-string newline bug before shipping

**Honest tradeoffs:**
- Penny bucket often empty (universe is mostly large/mid caps — honest reflection, not bug)
- Cold scans take minutes (Finnhub free tier rate limit — modal shows timer)
- No nightly precompute (Phase 2, requires Render workers)
- No cross-region USD normalization (per-region buckets cleaner)
- Universe hardcoded (no custom selection yet)

---

## v4.63.7 — Batch size 20 + monetization removed (current)

**Built:** 2026-04-30

**User request:** "Take batch wise stocks instead of stock by stock... remove payment information from home page."

**Changes:**

1. **Batch size 8 → 20** in find-similar scanner (env-tunable via FIND_SIMILAR_BATCH_SIZE). Honest note: free Finnhub rate limit (60/min) means internal `_pace()` serializes regardless of concurrency — wall-clock time roughly unchanged but apparent concurrency higher.

2. **Removed all monetization from index.html:**
   - 88-line pricing tiers section (Free $0, Pro $29, Institutional $79)
   - "Start Pro / Start Institutional" CTA buttons
   - "7-day free trial · Cancel anytime" subtitles
   - "Contact Enterprise Sales" CTA
   - Footer "Pricing" link
   - "10,000+ traders" claim, trust badges
   - All `_showPremiumCheckout()` references (the function never existed in app.js anyway)

**Preserved (intentional):**
   - Backend PREMIUM_TIERS access control (yrk@eml.com still has Dream tier access)
   - "Why Celesys AI?" paragraph mentioning Bloomberg cost (free-pro messaging, not CTA)
   - Frontend hasTier() / CELESYS_TIERS (still gates Dream features)

**Verified:**
- 15/15 audit checks pass
- 9/9 monetization sweep patterns clean
- Compile + JS syntax + byte-identical min.js
- Backend tier system fully functional

**Flagged honestly:**
- index.html was ALREADY truncated before this session (line 2296 cuts mid-statement: `_deferredPrompt.u`)
- Pristine backup confirms: pre-existing damage from prior deploy
- Did NOT attempt to fix — guessing damaged HTML is high-risk
- Browsers auto-close unclosed tags so it still renders, just PWA install prompt broken
- Separate r63.8 if user wants to restore from a clean backup

**Architecture:** Decoupled "what's premium" (backend tier code, kept) from "how we sell it" (frontend pricing UI, removed). When monetization returns, re-add pricing UI without touching access control.

---

## v4.63.8 — Momentum Leaders + Earnings Calendar + This-Week Alerts (current)

**Built:** 2026-04-30

**User request:** "Identify momentum stocks like SNDK, MU... weekly basis list company quarterly results... alert for this week companies which have quarterly results."

**3 new endpoints:**
- `/api/momentum-leaders?region=US|IN` — 5-component momentum score, top 20 bucketed by tier
- `/api/earnings-calendar?symbol=X&region=Y` — past quarters (Finnhub history) + upcoming (Finnhub calendar, US only on free tier)
- `/api/earnings-this-week?region=US` — next 7 days from Finnhub /calendar/earnings, sorted with tracked-universe tickers first

**Frontend:**
- 🔥 MOMENTUM button auto-injects into DD toolbar
- 📅 EARNINGS button auto-injects into DD toolbar
- Yellow EARNINGS THIS WEEK banner auto-loads at app top, "View All" opens full modal

**Momentum scoring (5 components):**
- 35% recent return blend (30/40/30 across 1M/3M/6M, sustained > short-term spike)
- 30% acceleration (3M annualized vs 1Y trend)
- 25% relative strength (6M absolute return)
- 10% breakout proximity (% from 52-week high)
- (Volume surge default-neutral; weight redistributed when no vol data)

**Hard filters:** US <$5 / IN <₹50 (penny), score <40 (downtrending)

**Verified:**
- 15/15 audit checks pass
- Momentum math: 4/4 behavioral tests pass — explosive rippers tier STRONG (65-80), real-MU pattern correctly STRONG (65.6), declining tickers correctly filtered (<40)
- All Python compiles, JS syntax OK, app.min.js byte-identical

**Caught + fixed during build:**
- Insertion-point regex (3 blank lines vs 1) — fixed
- Initial scoring too conservative (explosive ripper only 64.3, below STRONG threshold) — tuned blend weights to favor 3-6 month sustained returns, redistributed unused vol weight to active components

**Honest limits:**
- India: Finnhub free /calendar/earnings doesn't cover NSE/BSE. India tickers show "No upcoming reports" (past quarters via yfinance fallback work). Upgrade path: Finnhub Personal ~$50/mo, env-var swap.
- Forward dates: capped at 90 days
- Volume surge: neutral (no per-ticker vol data integration); weight redistributed
- Cold scan: 3-5 min for 80 US tickers (Finnhub free tier rate-limit serializes)

**Deploy 8 of 8 in single session. Rest after this.**
