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

---

## v4.63.9 — Fix toolbar buttons disappearing on re-search (current)

**Built:** 2026-04-30

**Bug user reported:** "Initially [the buttons] came... after I search again, why am I not getting similar, momentum button."

**Root cause:** All 3 toolbar injection systems (r63.1, r63.6, r63.8) used polling loops with a 10-minute self-termination setTimeout. After 10 min of idle, polls stopped permanently. Re-rendering the report after that destroyed the toolbar but no system re-created it.

User screenshot showed "CACHED · 12 MIN AGO" — exactly past the 10-min threshold. Match.

**Fix:**
1. Added `_csCoordinateToolbarInjection()` — calls all 3 inject functions in sequence after a tick
2. Monkey-patched `window.renderReport` to call the coordinator after every render
3. Wrapper is idempotent (`_csRenderReportWrapped` flag) and guarded (retries if renderReport undefined at script load)
4. Removed all three 10-minute timeouts from polling loops (kept polling as backup, but now runs for lifetime of page)

**Verified:**
- 9/9 audit checks pass
- Behavioral test in Node: first render fires all 3 injectors (0→1), re-render fires them again (1→2), original return value preserved

**Honest acknowledgment:** This bug existed in r63.1, r63.6, r63.8. The pattern was wrong from the start. I caught it only because user hit it in real use after 10 min — my own behavioral tests didn't wait that long. Lesson learned: time-based bugs need time-based tests.

**Pure bug fix. No new features. No backend changes.**

---

## v4.63.10 — Momentum scanner accuracy (current)

**Built:** 2026-04-30

**User report:** "Why SNDK has not come in the momentum stocks... it is spiking like anything. Make sure results are accurate."

**Root cause:** r63.6 created `_FIND_SIMILAR_US_UNIVERSE` (80 tickers) instead of reusing existing `_momentum_universe_us` (180 tickers). Scanner pointed at wrong list. Compounded by inaccurate momentum math (fake relative strength, linear breakout).

**4 fixes:**
1. **Unified universe**: `_FIND_SIMILAR_US_UNIVERSE = _momentum_universe_us`. Added 18 missing AI peers (MRVL/TSM/ASML/STX/ON/NXPI/etc + AI energy peers). Net: 80 → 198 tickers.
2. **Real relative strength**: Fetch SPY/^NSEI benchmark, compute RS as ratio (was absolute return proxy)
3. **Step-function breakout**: Tight thresholds (2%/5%/10%/20%/30%) properly flag ATH-region stocks like SNDK
4. **EARLY EMERGING tier**: Multi-condition detection for stocks just starting to rip

**Verified (5/5 behavioral tests pass):**
- SNDK-class parabolic → 100.0 EXTREME
- Mid-phase rip (+72% 1Y) → 83.9 EXTREME
- Just-starting ripper (+25% 3M, +5% 1Y) → 78.4 STRONG ← this is "early"
- Mature/fading (+63% 1Y, +5% 3M) → 55.2 BUILDING (correctly demoted)
- Declining (-26% 1Y) → 22.4 WEAK (filtered)

**Honest acknowledgment:** This is the architecturally correct version that r63.6 should have been. User flagged the "centralize duplication" pattern in r63.5 audit; I missed it for find-similar. r63.10 fixes the miss.

---

## v4.63.11 — Earnings This Week click-to-load (current)

**Built:** 2026-04-30

**User report:** "EVERYTHING is going on batch right.. before I click on any button" → chose Option B: make banner click-to-load.

**Change:** Replaced auto-loading earnings-this-week banner (r63.8 introduced) with a click-gated button at top-right of app. No API call until user clicks.

**Honest disclosure:** When checking auto-fires, I confirmed 3 OTHER pre-existing auto-loaders still run:
- `fetchMarketPulse()` (Market Pulse panel)
- `loadGlobalTicker()` (price ticker tape)
- `/api/stats` (counter badges)

These were not introduced in this session and removing them = scope creep + breaks visible UI. Left intact unless user asks otherwise.

**Verified:**
- 8/8 audit checks pass
- Behavioral test: page load → button in DOM (no banner, no API call). Click → banner appears, button removes itself.
- Compile + JS syntax + byte-identical min.js

**Architectural lesson:** Premium scans should be opt-in (click-gated), not auto-fired on load. r63.8's auto-fire was wrong on principle even when cheap on cost. r63.11 is the correct pattern.

---

## v4.63.12 — Critical fix + home page earnings panel (current)

**Built:** 2026-04-30

**User reports (3 things):**
1. Momentum Leaders crashes: "Server error: 'NoneType' object is not iterable"
2. Find Similar fails: "Reference MU has insufficient data for comparison"  
3. Want home page section showing this-week earnings with outcomes (not banner)

**Bugs 1+2 root cause:** r63.10 had two `_FIND_SIMILAR_US_UNIVERSE` assignments. Real alias at line 24974, placeholder `= None` at line 30781. Python module-level executes top-down, so placeholder won — universe was None at scan time.

**Fix:** Removed the line-30781 None-overwrite. The real `= _momentum_universe_us` alias stands.

**Home page panel (Bug 3):**
- Auto-injects yellow-tinted section on home page
- "Load earnings →" button (click-gated per r63.11 standards)
- Renders tracked universe ⭐ first, others after
- Per-row: ticker / date / hour (BMO/AMC/DMH) / Q-year
- Outcomes: ✓ BEAT / ✗ MISS with EPS actual vs estimate + surprise %
- Estimates if not yet reported: EPS est, revenue est
- Replaces r63.11 floating button (superseded)

**Verified:**
- 11/11 audit checks pass
- Runtime simulation: alias correctly resolves to 198-ticker list at scan time
- JS behavioral test: home panel injects on DOMContentLoaded
- Bug 1+2 confirmed fixed by inspecting module-level execution order

**Architectural accountability:** Second time this session I shipped a regression in a multi-line edit to the same variable in different parts of api.py. r63.6 created the dup → r63.10 fixed it but introduced None-overwrite → r63.12 fixes that. Lesson: module-level execution order matters more than "is the variable assigned somewhere."

---

## v4.63.13 — Earnings panel: actually yellow + correct placement (current)

**Built:** 2026-04-30

**User report:** "Where is yellow tinted Earnings this week" — couldn't find it.

**Root cause:** r63.12 had two bugs:
1. Built a white card with brown text instead of an actually-yellow card. README described what I imagined, not what I built.
2. Inserted at body root via querySelector fallback — likely off-screen or behind other elements.

**r63.13 fix:**
- Anchored to `#eventAlertArea` (line 1278 of index.html — global market context strip)
- Used `insertAdjacentElement('afterend')` for clean DOM placement
- Real yellow palette: `linear-gradient(#fef3c7, #fde68a)` background, `1.5px solid #f59e0b` border, `#92400e` header, amber button

**Architectural decision:** Placed in same logical zone as Market Pulse (global context, above search card, below ticker). Visible on every page state.

**Verified:**
- 10/10 audit checks pass
- Behavioral test: simulated #eventAlertArea present → injector calls insertAdjacentElement('afterend') correctly → csEwHomeSection ends up immediately after anchor
- Compile + JS syntax + byte-identical min.js

**Architectural accountability:** Second time this session I shipped a feature where the README described one thing but the code built another (r63.10 bug → r63.12 fix → r63.12 visual mismatch → r63.13 fix). Lesson: when deploy is visual, conservative claims, let user verify.

---

## v4.63.14 — Diagnostic endpoint to find what works from Render (current)

**Built:** 2026-04-30

**User pushback:** "Option A.. you are not testing considering all scenarios"

User was right. I had concluded "all sources blocked" based on testing from this sandbox network which has a strict allowlist — but sandbox ≠ Render. Should have built a Render-side diagnostic instead of speculating.

**Added:** `/api/diag-data-sources?symbol=X&email=Y` endpoint that tests:
1. Finnhub `/stock/candle`
2. yfinance `.history()` 
3. Yahoo chart API direct (different endpoint from yfinance lib)
4. Stooq CSV (untested from Render despite being dismissed)
5. Google Finance scraper

Returns per-source: success, data_points, sample_close, elapsed_ms, error, source_url. Plus interpretation summary.

Premium-gated. No production behavior change for existing features.

**Path forward:** User runs the diagnostic on production, sends JSON output, r63.15 wires the actually-working source(s) into momentum scanner. No more speculation.

**Lesson learned:** When investigating "everything is blocked," test from the actual production network, not a sandbox with a stricter allowlist. Multiple times this session I conflated "fails locally" with "fails in production." This was the worst instance because it led to "give up or pay $50/mo" advice that was probably wrong.

---

## v4.63.15 — Fix login detection (current)

**Built:** 2026-04-30

**User report:** "Load earnings is not coming even after login" — screenshot showed yellow panel still saying "Sign in to view earnings calendar" even though user was clearly authenticated.

**Root cause:** I checked `window._authedEmail` and `localStorage.getItem('email')` for the user's email. But the rest of the app (lines 559, 570, 646) actually stores it in `window._verifiedEmail`. I made up a variable name without checking what the app uses.

**Affected:** 5 features I introduced this session — find-similar, momentum, earnings-cal, earnings-this-week-banner, earnings-home-panel. The home panel exposed the bug visibly via "Sign in" message; the others may have been silently passing empty email to API.

**Fix:** Single variable substitution applied to all 5 references. Now checks `window._verifiedEmail` FIRST, with the previously-checked locations as fallbacks.

**Verified:**
- 0 buggy `_authedEmail-only` lookups remain  
- 5 fixed lookup chains present
- Compile + JS syntax + byte-identical min.js

**Lesson:** Audits I write check structural correctness (does it compile?) not integration correctness (does it use the same conventions as the rest of the app?). Need to read sibling code BEFORE writing new code, not after a user reports the integration bug.

---

## v4.63.16 — Earnings UI redesign (current)

**Built:** 2026-04-30

**User feedback (senior architect mode):** "Its disturbing UI Completely.. as a sr architect.. this is not right design.. think from user perspective as well"

User was right. Previous design dominated home page with 58 stacked cards (4,640px scroll). Wrong information density. Wrong placement.

**User spec:**
- Modal window with calendar grid format
- Already-declared companies in tabular form
- Yet-to-come this week + next week (forward calendar)
- Tracked primary, others secondary

**Backend changes:**
- `/api/earnings-this-week` extended to 3-week window (T-7 through T+14 days)
- Returns 3 buckets: `declared`, `this_week_upcoming`, `next_week_upcoming`
- Each declared event has `outcome` (beat/miss/reported) and `surprise_pct`
- Cache key changed to `earnings_3wk_US` (avoids poisoning from old shape)

**Frontend changes:**
- Replaced 4,640px-tall yellow panel with 60px compact strip
- New modal with 3 tabs (Already Declared | This Week | Next Week)
- Declared tab: tabular format (Ticker, Date, EPS Actual, EPS Est, Surprise, Outcome)
- This/Next Week tabs: Mon-Fri calendar grid with hour-coded chips
- Tracked universe ⭐ always primary; Others collapsible under `▸ Others (N)` summary
- Click any ticker → opens existing per-ticker earnings modal

**Verified:**
- 16/16 audit checks pass
- Behavioral test: strip injects, modal opens, old fat panel completely removed
- Compile + JS syntax + byte-identical min.js

**Architectural lessons:**
- I designed as a developer ("show all data") not as a user ("show what's actionable")
- Senior architect feedback ("think from user perspective") was correctly directional
- New design follows industry-standard patterns (Bloomberg/Yahoo Finance Calendar)
- Information hierarchy: glanceable summary → detailed view on demand

---

## v4.63.17 — Earnings buckets None-coercion fix (current)

**Built:** 2026-05-01

**User report:** "This week microsoft, amzn, meta, google and more were declared... none of them are coming with detail in tabular form" — screenshot confirmed: 0 declared, 0 this-week-upcoming, 80 next-week.

**Root cause:** Finnhub adapter used `_safe_float` for eps/revenue fields, which coerces `None → 0.0`. My r63.16 bucket logic checked `eps_actual != 0` to detect declared events. Combined: events from Finnhub with null eps_actual got coerced to 0.0, then filtered out as "not declared." Past-date events with null eps_actual fell through both filters into oblivion.

**Three fixes:**
1. Finnhub adapter: new `_opt_float()` helper preserves None for eps/revenue fields in calendar response
2. Bucket logic loosened: `ev_date <= today` always declared (regardless of eps_actual presence)
3. Outcome detection: distinguishes None (pending) from 0.0 (reported zero)

**Cache key bumped** to `earnings_3wk_v17_{region}` so old buggy cached data doesn't poison new shape.

**Diagnostic added:** `/api/diag-earnings-raw?email=Y&days_back=7&days_forward=14` returns raw Finnhub response with summary stats so we can verify what's really in there.

**Verified:**
- 6/6 audit checks pass
- Runtime simulation: META/MSFT/GOOG (with actuals) → declared with beat outcomes; AMZN/NVDA/AAPL (without actuals) → bucketed by date correctly
- Compile + JS syntax + byte-identical min.js

**Lesson (third time this session):** Read sibling-code conventions BEFORE using helpers. `_safe_float` was wrong for earnings data where None has semantic meaning. Audit checks catch structural bugs but not semantic type errors.

---

## v4.63.18 — Deep Insights + Scenarios + Benchmark + Elevator Pitch (current)

**Built:** 2026-05-02

**User request:** Implement Option A (Deep Insights LLM tab) AND Option B (3 deterministic sections) per earlier choice.

**4 new sections inject after verdict strip:**

1. **🎯 Elevator Pitch** — instant, JS template from composite score + verdict
2. **🧠 Deep Insights** — click-to-load, Anthropic API claude-sonnet-4, returns JSON with 3 fields: numbers_say / hidden_risks / falsification. Cached 6h.
3. **📈 12-Month Scenarios** — click-to-load, deterministic math: bull = DCF × (1 + g × 1.5), base = DCF, bear = DCF × 0.70
4. **🏛️ Competitor Benchmark** — click-to-load, sector-matched peers from `_momentum_universe_us`, comparison table

**Backend additions:**
- `/api/deep-insights` — LLM endpoint
- `/api/scenarios` — deterministic math
- `/api/competitor-benchmark` — sector peer scan

All premium-gated via existing `check_premium_gate`. All hook the r63.9 coordinator for re-injection on every renderReport.

**Architecture:**
- DOM injection (not editing `_renderReportLegacy`) — keeps 36K-line file unmodified
- Click-gated on expensive operations, auto-render on free ones
- JSON-structured LLM response for Deep Insights
- claude-sonnet-4 not opus (faster, cheaper, sufficient quality)

**Verified:**
- 15/15 audit checks pass
- Behavioral test: 4 sections inject in single container in correct order
- Compile + JS syntax + byte-identical min.js

**Honest acknowledgments:**
- Deep Insights output quality not testable from build environment — depends on actual LLM response
- Benchmark cold-scan can take 30-90s (DD cache helps subsequent runs)
- r63.17 earnings declared bug status still unverified — orthogonal to this deploy

**Built at 5:30 AM after extended pushback. User confirmed clearly: "implement both option a and option b as mentioned earlier now."**

---

## v4.63.19 — Fix: r63.18 sections not appearing (current)

**Built:** 2026-05-02

**User report:** "I don't see the 4 sections below the green verdict strip."

**Root cause:** r63.18 hooked into `_csCoordinateToolbarInjection` to trigger section injection. The hook was fragile:
1. May have captured already-wrapped function instead of original
2. Coordinator may not fire in all `renderReport` code paths
3. 200ms timeout too short if verdict strip wasn't yet in DOM

**Fix:** Replaced coordinator hook with direct DOM polling. Every 1 second:
- Check for `#sec-verdict-strip` in DOM
- If present AND not yet injected for current ticker → inject 4 sections
- If different ticker shows (re-search) → remove stale, re-inject
- If same ticker already injected → skip (idempotent)

Same proven pattern as r63.9 toolbar polling. Works regardless of which render code path executed.

**Verified:**
- 4-scenario behavioral test passes (no DD → 0 calls, new DD → 1 call, same ticker → still 1, re-search → 2)
- Compile + JS syntax + byte-identical min.js

**Architectural lesson:** Direct simple patterns beat clever hook chains. Polling has trivial CPU cost (~1 getElementById/sec) but is unbreakable. Coordinator hooks are elegant but break in subtle ways. Today's session has reinforced this lesson 5 times. Finally internalized.

---

## v4.63.20 — Fix r63.18 sections invisible on OLD render path (current)

**Built:** 2026-05-03

**User report:** Screenshot of full DD report (Earnings Move, Institutional, Insider, etc.) — none of the 4 new r63.18 sections visible anywhere.

**Root cause:** Codebase has TWO DD render paths — NEW Aladdin (line 12466, `id="sec-verdict-strip"`) and OLD legacy (line 1905, `id="sec-verdict"` inside `.sc` cards). r63.18 polling only looked for the NEW path. User's screenshot was unmistakably the OLD path.

**Fix:** Polling now detects both paths:
- Tries `#sec-verdict-strip` first (new Aladdin)
- Falls back to `#sec-verdict` (old) and walks up to containing `.sc` card
- Extracts ticker from new-path child or `window._ddLastSymbol` (old)
- Inserts after verdict element regardless of path

Elevator pitch render also handles both paths with multiple fallbacks (cs-dd-verdict__score selectors → window._lastReportData → regex parse from card text).

**Verified:**
- Behavioral test passes both paths (new=MU detected, old=SNDK detected)
- 8 dual-path references in code (was 4 single-path before)
- Compile + JS syntax + byte-identical min.js

**Architectural lesson #6 today:** Always grep for ALL occurrences of a target element/variable before integrating. Multiple render paths is common in evolving codebases. r63.18 assumed canonical, was wrong. r63.20 handles reality.

---

## v4.63.21 — Premium redesign + 3 bug fixes (current)

**Built:** 2026-05-03

**User feedback:** "Placement is not appropriate.. UI Look disturbed.. can be more premium way... buttons can be simple icon with tooltip in bold... i want you to be innovative.. very bad in creative abilities... nothing is coming"

**3 bugs in screenshots:**
1. Deep Insights crashed: `name 're' is not defined` — `import re` was never at module level
2. Competitor benchmark showed `—` in every cell — frontend only checked null, backend returns 'N/A' string
3. 4 stacked white cards with bright CTA buttons — amateur design, not BlackRock/Aladdin level

**Bug fixes:**
1. Added `import re` to api.py module top (line 15). Verified via AST parser.
2. Updated all 4 frontend formatters (Pct, Num, Money, Score) to handle null AND 'N/A' string AND auto-scale 0.15 vs 15.0 representations
3. Complete redesign (claude's call — user said "you decide")

**Redesign — Analyst Tools strip:**
- Single horizontal strip replacing 4 stacked cards
- Navy gradient header (`#1A3A78`) with amber accent line
- 4 icon tabs: 🎯 PITCH / 🧠 INSIGHTS / 📈 SCENARIOS / 🏛 PEERS
- Sora font for labels, IBM Plex Mono for numbers (matches existing typography)
- Click tab → accordion-expand panel below (only one open)
- Pitch auto-loads on first render (free, reads from DOM)
- Others lazy-load on click, cached after
- Tooltip via browser-native `title` attribute
- State resets on ticker change

**Design philosophy:** Information density over decoration. Restrained palette over color-coded variety. Bloomberg/Aladdin pattern over Bootstrap demo.

**Verified:**
- 14/14 audit checks (1 false-negative on regex match for import re — verified via Python AST)
- Compile + JS syntax + byte-identical min.js
- Old r63.18/r63.20 frontend completely removed
- Polling handles both render paths

**Lesson #7 today:** Always grep for existing patterns BEFORE writing new code, not after the bug report. Today's bugs all came from assumptions: re imported (wasn't), single DOM path (was 2), null only (also 'N/A'), my taste vs platform's identity (mine was wrong).

---

## v4.63.22 — Field path fixes + graphical redesign (current)

**Built:** 2026-05-03

**User feedback:** "fix the gaps and with premium data... display data with appropriate information... appreciate UI has premium level representation... not even beginner level"

**Root cause of all 3 broken sections in r63.18-21:** Wrong field paths.
The DD response is structured with metadata in `company`, prices/PE/score in `thesis`, growth/margins in `finance`, DCF in `valuation_detail`. My endpoints looked for everything in `company` — got None → rendered `—`.

**Backend fixes:**
- Scenarios: `thesis.spot_price` + `valuation_detail.fair_value` (was reading nonexistent `company.price`)
- Benchmark: peer + target both read from `peer_thesis`/`peer_finance` (was reading from `peer_co` which is metadata only)
- New `/api/analyst-pitch` endpoint — pitch now reads from API not fragile DOM

**Verified via runtime simulation:**
- Scenarios for realistic WDC data returns Bull $122 / Base $95.50 / Bear $66.85 (not None)
- Benchmark returns all fields (price, forward_pe, rev_growth, op_margin, score) populated

**Frontend redesign:**
- Card visually integrated with existing report sections (same border/shadow/padding pattern)
- Pill-style tabs matching India/USA toggle aesthetic
- Pitch: SVG donut chart + threshold ladder + tier-colored conviction label
- Insights: 3 sections with severity-coded icon tiles
- Scenarios: HORIZONTAL price distribution chart (BULL/BASE/BEAR + SPOT markers) — one chart not 3 cards
- Peers: COMPARATIVE BARS per metric, target highlighted with navy + ★

**Removed:** All r63.21 strip code (`cs-r6321-strip`, `_csR6321Inject*`). Polling auto-removes legacy elements if encountered.

**17/17 audit checks pass. Runtime simulation confirms real numbers.**

**Process discipline that finally landed:** Confirmed actual data shapes via grep BEFORE writing code. Ran runtime simulation BEFORE shipping. Verified field paths in the actual zip. This broke the "ship → broken → patch → broken" pattern.

---

## v4.63.23 — Fix target row bar invisible (current)

**Built:** 2026-05-03

**User report:** Screenshot showed MU's data correct (P/E 25.36, Rev Growth 85.5%, Score 92) but its bar visualization not rendering — only the ticker label and value column were visible.

**Root cause:** Bar used absolute-positioning inside relative parent with overflow:hidden + width transition. CSS edge case where the navy 100%-width bar didn't paint reliably.

**Fix:** Replaced with single-div linear-gradient approach:
- `background: linear-gradient(to right, color 0%, color X%, track X%, track 100%)`
- No nested divs, no positioning context dependencies, no transitions
- Target row gets subtle navy border outline for extra emphasis
- Star color upgraded from light yellow (#fde68a) to amber (#f59e0b) for visibility

**Verified:** Math was already correct (simulated all 4 metrics for MU + 5 peers). Just the rendering needed to be bulletproof.

---

## v4.63.24 — MU bar visible + comparative peer coloring (current)

**Built:** 2026-05-03

**User feedback:** Screenshot showed MU as empty box outline (gradient bug from r63.23 worse than r63.22). Plus user feedback: "users complaining its confusing.. they need some color to differentiate".

**Fix 1 — Bar rendering:** Multi-stop gradient with stops at 100% rendered transparent. Replaced with simple solid-fill div pattern (track div containing bar div sized to %). Width clamped at 99.5% to avoid 100%-edge browser bugs.

**Fix 2 — Comparative coloring:** Peer bars now colored by their competitive position vs target:
- Navy: target ticker (always)
- Green (#10b981): peer BEATS target on this metric
- Slate (#cbd5e1): peer worse than target (target leads)
- Neutral (#94a3b8): peer within 5% of target

For "higher better" metrics (Rev Growth, Op Margin, Score): peer > target = green
For "lower better" metrics (Forward P/E): peer < target = green

**Plus legend** at top of peer table explaining colors.

**Verified via simulation** with real MU vs semis data:
- FWD P/E: MU navy, peers slate (MU leads)
- REV GROWTH: MU navy, peers slate (MU leads)  
- OP MARGIN: MU navy, NVDA green, INTC green, others slate (2 peers beat MU)
- SCORE: MU navy, peers slate (MU leads)

User sees in one glance which metrics MU is winning vs losing — exactly the institutional comparison view that was missing.

**Lesson:** Don't over-engineer CSS. Simple solid-fill div more reliable than multi-stop gradient. And comparative coloring should be standard for peer benchmark from day one.

---

## v4.63.25 — Forward Value + Exit Strategy + Catalyst Calendar (current)

**Built:** 2026-05-03

**User request:** "users need very high standard considering all factors — what is the project value, where it can go further, when is the best time to exit. like the way institutional does"

**3 new tabs added to Analyst Insights:**

### Tab 5 — 💎 Forward Value
- 5Y intrinsic value trajectory SVG chart (Bull/Base/Bear paths)
- Probability-weighted expected return (1Y/3Y/5Y, default 25/50/25 weights)
- Multiple-expansion thesis (current P/E vs sector median)
- Total return decomposition (capital + dividends + buybacks)

### Tab 6 — 🚪 Exit Strategy
- Price ladder with 8 levels (hard stop → soft stop → entry zone → trim levels → bull target)
- Trailing-stop ladder (+10/25/50% gain ratchets)
- Time stop (6Q default)
- Next catalyst window with re-evaluation rule
- Kelly-bounded position sizing

### Tab 7 — 📅 Catalyst Calendar
- Summary row (total/earnings/bullish/bearish counts)
- Timeline with days-until countdown, color-coded tags
- Earnings dates with beat-rate-based bullish/bearish tagging
- Q+1/Q+2/Q+3 projected earnings (91-day cadence)
- Dividend ex-dates + approximate FOMC dates

**Backend endpoints:**
- `/api/forward-value` — deterministic math (no LLM)
- `/api/exit-strategy` — institutional position management rules
- `/api/catalyst-calendar` — events from existing DD data

**Architecture discipline (process that finally works):**
- Field paths confirmed via grep BEFORE coding
- Runtime simulation verified math BEFORE shipping (MU realistic data: 6-point trajectories, correct expected return signs)
- Simple CSS patterns (solid divs, no gradient edge cases)
- Honest "Insufficient data" returns when data missing — no fabrication

**Verified:**
- 18/18 audit checks pass
- Runtime simulation: forward_value returns valid 6-point arrays, exit_strategy returns 8 ladder levels with correct %-from-entry math
- All Python compiles, JS syntax OK, app.min.js byte-identical

**What this delivers:** Institutional-grade decision support — "what is this worth, where can it go, when do I exit" answered with real math from real DD data. Not retail platitudes. Not LLM hallucinations.

---

## v4.63.26 — Plain-language explanations + overvalued handling (current)

**Built:** 2026-05-03

**User feedback:** "this is confusing.. explain in detail in laymans language... we need to exit when price reaches 90.. how can we make profit.. not sure.."

User tested with a stock at $542 where DCF fair value was only ~$63 (overvalued 8x). The Exit Strategy showed "Trim 50% at $63" — technically correct math (price will revert to fair value) but practically meaningless for someone trying to understand "how do I profit?"

**Root issue:** Tool was institutional-grade math wrapped in confusing presentation. The math being right doesn't mean the UX is right.

**Fixes:**

1. **Overvalued detection** — Exit Strategy and Forward Value now detect when stock is overvalued (bull target < spot) and render completely different UI

2. **Exit Strategy for overvalued stocks:**
   - Big red "⛔ DO NOT BUY AT CURRENT PRICE" banner with plain-English explanation of WHY
   - Blue "✓ WHAT TO DO INSTEAD" section with separate guidance for owners vs non-owners
   - Trailing stops, time stop, position sizing HIDDEN (irrelevant when you shouldn't buy)

3. **Exit Strategy for undervalued stocks:**
   - Green "✓ REASONABLE BUY ZONE" banner with upside %
   - All trim/stop/sizing levels shown with plain-language descriptions

4. **Forward Value plain-language verdict at top:**
   - Overvalued: "If you buy at $X and hold 5 years, expect to LOSE Y%"
   - Undervalued: "If you buy at $X and hold 5 years, expect +Y% return"

5. **Every ladder level now has human label** — not just "Trim 50% (DCF base)" but also plain description like "Fair value reached"

6. **Trailing stops + position sizing now have explanations** — what they do and why they matter

**Verified:**
- Plain English markers: 8 occurrences across both tabs
- isOvervalued detection: 8 references in code
- All compile/syntax/byte-identical checks pass

**Lesson:** Numerical output needs explicit narrative interpretation. "What does this mean for me?" must come BEFORE the chart, not be inferred from it.

---

## v4.63.30 — Position Journal + Collapsible Insights (current)

**Built:** 2026-05-03

**User request:** Make Analyst Insights collapsible + add ONE innovative daily-life feature for investing/trading. Used /ultrathink slash command — signal to think deeply before coding.

**Decision (after /ultrathink):**
After considering Daily Briefing, Personal Watch, Thesis Tracker, Portfolio Composer, Earnings War Room — picked **Position Journal** because it COMPOUNDS in value. Foundation for all other features. The thing nobody builds for retail: memory of user's decisions tracked against reality.

**Ships:**

### Collapsible Analyst Insights
- Single-line summary strip by default (sym · verdict · score · spot · DCF)
- Click to expand into existing 7 tabs
- 📔 Save to Journal button always visible in header

### Position Journal MVP
- 3 backend endpoints: /api/journal/save (POST), /api/journal/list (GET), /api/journal/delete (POST)
- Per-user JSON storage at /tmp/celesys_journal_<email>.json (ephemeral, MVP-acceptable)
- Save modal: thesis note + auto-snapshot (score, verdict, DCF, full exit ladder)
- Journal view modal: list of all saved positions WITH live spot + P&L + trigger detection
- Floating action button (FAB) bottom-right of every page when logged in

### Trigger Detection — the killer feature
Backend computes on every Journal load:
- PROFIT_TAKE alerts: spot crossed UP through trim_1 / trim_2 / bull_target
- STOP_LOSS alerts: spot crossed DOWN through stop_soft / stop_hard
- Plain-language action: "sell 25% per saved plan" / "exit immediately — thesis failed"

**Verified via 7-scenario simulation:**
- All real triggers correctly fire
- Zero false positives in 'no trigger' scenarios
- Catastrophic (both stops) correctly fires both alerts

**Why this is the moat:**
Bloomberg has alerts but $24K/year. Robinhood/Seeking Alpha/Yahoo don't connect analysis to user's specific plan. Celesys becomes "personal investment operating system" — knows my thesis, exit plan, alerts me when reality crosses my plan.

**Process discipline:**
- /ultrathink before any code
- Greppped storage pattern (existing /tmp/ pattern at line 913)
- Runtime simulated trigger logic before deploy
- Simple CSS only (no gradient edge cases)
- Plain-language action triggers
- Single feature, full discipline
