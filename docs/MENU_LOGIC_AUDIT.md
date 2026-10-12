# Celesys menu and logic audit

Reviewed working tree on 2026-10-12; base commit `8db0e8fe2f98cc0cef62d19e3ce643dfcef68dd1`. The inventory was generated with `node qa/menu-inventory.cjs`. It contains 48 unique original menu entries plus Active Trading and Today’s Setups: **50 total**. Uncommitted fixes are identified below.

## Evidence and limits

- Entry surface is the existing `/` workspace, with `/research` as its canonicalized alias. Most menus are client-side state, not separate server pages.
- **U**: `tests/workspace.test.mjs` creates `all-menu dispatcher: <group>/<tab>` cases for six permission profiles. These dispatch tests stub original renderers; they do not execute each engine.
- **B**: `qa/browser.spec.cjs` defines `menu <group>/<tab> respects basic access` and `menu <group>/<tab> opens for a full UI fixture`. APIs are mocked and the full fixture has full, premium and dream grants. The test requires visible original content, not correct financial output.
- **V**: additional original-chart test clicks Technical, waits for recreation, checks visible canvas geometry and plotted fixture values, and confirms hiding on Overview. This covers that chart workflow only.
- **S**: shell-only browser check; Active Trading checks generic Trading text, Today’s Setups checks iframe visibility. Neither establishes functional output.
- Test definitions and historical passing runs are not a passing result for the current working tree. Attach the current CI JSON/HTML artifact and commit SHA when making a release claim. This audit did not execute a browser or place orders.
- Every gap below is unverified unless explicitly marked fixed. No claim is made that every line, control, account combination, formula or live provider has been verified.

## Review ownership by surface

Use six bounded reviewer assignments, each reporting against the menu keys below, rather than spawning one agent for each button. These are audit responsibilities, not a claim that 50 independent agents ran.

| Reviewer surface | Responsibility | Acceptance evidence |
|---|---|---|
| Research and calculations | Summary, analysis, DCF, equity, comparison, finance | Independent expected calculations plus missing-data cases |
| Market evidence and charts | Dashboards, market pages, news, charts | Identity, timestamp, currency and rendering checks |
| Scanners and rankings | Decide scanners, Dream tools, movers, 360 | Filter behavior, universe coverage, score reconciliation |
| Trading and options | Legacy algo, Trading Desk, options, tickets, Active Trading | Closed-bar evidence, instrument identity, sizing, failure states; no broker orders |
| Identity and stored user data | Every gate, journals, PMS, Today | Tier transitions, verified sessions and cross-user isolation |
| QA coordinator | All inventory keys, CI artifacts and regression history | Stable gap IDs, reproducible fixtures, explicit unverified states |

## Per-menu register

All ordinary rows dispatch through `CelesysWorkspace.openTool → switchTabGroup → switchTab(tab)`. Handler names below identify the observed entry, not every nested function. Route `workspace` means `/` or its `/research` alias. Access abbreviations: **basic** = Overview/Tools public surface; **full** = full/admin group access; **premium** = original premium flag additionally required; **dream** = original dream flag additionally required. Trading-only users have a separate limited renderer. Server verification is a distinct requirement from these UI flags.

| Menu key / label | Route and handler | UI access | Coverage | Concrete remaining logic check |
|---|---|---|---|---|
| `overview/quick` — Summary | workspace; `displayReport / switchSubTab / createCharts` | basic | U + B + V | Independently reconcile ratios, chart inputs and missing/zero values; exercise every Summary subtab. |
| `research/analysis` — AI Analysis | workspace; `switchTab / switchAnalysisSubTab` | full | U + B | Verify generated-report citations, escaping, incomplete sections and every analysis subtab against approved fixtures. |
| `research/dcf` — DCF Valuation | workspace; `renderDCF` | full | U + B | Independent DCF oracle for discount rates, terminal growth, negative cash flow and scenario sensitivities. |
| `research/equity` — Research | workspace; `renderEquityResearch` | full | U + B | Reconcile peer currencies, periods and comparable metrics; test sparse or conflicting fundamentals. |
| `tools/compare` — Compare Stocks | workspace; `switchTab(compare)` | basic | U + B | Compare mismatched currencies, missing peers, duplicate symbols and stale responses. |
| `decide/decision` — Analyze Stock | workspace; `switchTab / decision controls` | full | U + B | Reconcile combined engine scores and scenario assumptions; verify all investor/trader mode switches. |
| `decide/tomorrowbrief` — Tomorrow's Open | workspace; `manual Generate Brief controls` | full | U + B | Generate action, market timezone boundaries, prior-session evidence and missing-calendar behavior. |
| `decide/fundadashboard` — Dashboard | workspace; `manual dashboard controls` | full | U + B | Submit symbols/regions; reconcile reported vs annualized numbers and concurrent dashboard requests. |
| `decide/engines` — Engines | workspace; `manual engine controls` | full | U + B | Exercise each engine input and reconcile its output; opening the container is insufficient. |
| `decide/toptrades` — Top Trades | workspace; `loadTopDecideTrades` | full | U + B | Check ranking with independent expected candidates; test refresh lifecycle for both market sessions. |
| `decide/topinvest` — Top Investments | workspace; `loadTopDecideInvest` | full | U + B | Check universe completeness, ranking stability and repeated visits after provider failure. |
| `decide/smv3` — Smart Money v3 | workspace; `loadSmartMoneyV3` | full | U + B | Reconcile batch scores and ownership periods; ensure old scans cannot overwrite a new universe. |
| `decide/smartmoney` — Smart Money | workspace; `loadSmartMoneyScanner` | full | U + B | Test market-cap/region filters, delayed ownership filings and missing volume/OI interpretation. |
| `decide/mchunter` — Micro-Cap Hunter | workspace; `loadMicroCapHunter` | full + dream | U + B | Dream gate now aligned; still test liquidity filters, full-without-dream UI and historical selection bias. |
| `decide/intraday` — Intraday Setups | workspace; `loadIntradaySetups` | full + dream | U + B | Dream gate now aligned; still test exchange sessions, slippage and unsupported instruments. |
| `decide/positioning` — Positioning | workspace; `loadPositioningScanner` | full | U + B | Check filing lags, min-filer filters, pagination and stale ownership snapshots. |
| `decide/diamond` — Diamond Hunter | workspace; `loadDiamondHunter` | full | U + B | Test crash threshold, universe exclusions and independent recovery/quality scoring. |
| `decide/analyst` — Analyst Coverage | workspace; `loadAnalystCoverage → deResult` | full | U + B | Filter date, sector, ticker and firm; verify target currency, duplicates and refresh outcomes. |
| `decide/proscan` — Pro Scan | workspace; `switchTab(proscan)` | full + premium | U + B | Validate factor weights, unavailable factors and multiple scenario simulations against an independent oracle. |
| `decide/etfscanner` — ETF Scanner | workspace; `loadEtfScanner` | full | U + B | Test region/refresh controls, fund currency, holdings dates and coverage gaps. |
| `decide/reports` — Reports | workspace; `loadRegionalReports` | full | U + B | Exercise refresh and every accordion; verify provider failures and source timestamp propagation. |
| `decide/pms` — PMS | workspace; `loadPMSHome` | full + premium | U + B | Test uploads, malformed portfolios, allocations, rounding, fees and isolated user state. |
| `dream/dreamportfolio` — Dream Portfolio | workspace; `switchTab(dreamportfolio)` | full + dream | U + B | Validate return assumptions and diversification; a target CAGR is not an expected outcome. |
| `dream/multibagger` — Multibagger Hunter | workspace; `switchTab(multibagger)` | full + dream | U + B | Test universe selection and survivorship bias; reconcile scores rather than success labels. |
| `dream/momentumradar` — Momentum Radar | workspace; `switchTab(momentumradar)` | full + dream | U + B | Validate momentum periods, split adjustments, sparse price history and session transitions. |
| `dream/highprob` — High-Prob Setups | workspace; `switchTab(highprob)` | full + dream | U + B | Check score semantics; no calibrated probability or performance evidence established by UI tests. |
| `dream/optionspulse` — Options Pulse | workspace; `switchTab(optionspulse)` | full + dream | U + B | Reconcile option expiry, contract identity, OI update time and unsupported-market states. |
| `dream/tradeticket` — Trade Ticket | workspace; `switchTab(tradeticket)` | full + dream | U + B | Exercise every ticket field, multiplier and max-loss check; no live order execution certified. |
| `dream/microcap` — Micro-Cap Challenge | workspace; `switchTab(microcap)` | full + dream | U + B | Test challenge inputs, liquidity limits, incomplete financials and persistence. |
| `trading/trades` — Algo Trades | workspace; `switchTab / loadTopTrades` | full / trading-only | U + B | Legacy /api/algo-signal is a separate strategy from the tested Trading Desk closed-bar engine. |
| `trading/smarttrades` — Smart Trades | workspace; `switchTab(smarttrades)` | full / trading-only + premium | U + B | Exercise refresh, idea ranking, source age and missing contract checks. |
| `trading/stockintel` — Stock Intel | workspace; `switchTab(stockintel)` | full / trading-only + premium | U + B | Reconcile each decision section and conflicting inputs; verify ticker-change races. |
| `trading/scanner` — Scanner | workspace; `switchTab(scanner)` | full / trading-only | U + B | Test heatmap/screener/options subcontrols, incomplete universe and refresh cancellation. |
| `trading/valreport` — Valuation | workspace; `loadValuation` | full / trading-only + premium | U + B | Independent valuation/geo-risk scenarios and negative-earnings edge cases. |
| `trading/backtest` — Backtest | workspace; `switchTab(backtest)` | full / trading-only + premium | U + B | Independent fills/costs, look-ahead prevention, adjusted history and out-of-sample benchmarks. |
| `trading/journal` — Journal | workspace; `loadJournal / loadJournalReview` | full / trading-only + premium | U + B | Verify create/edit/close/delete/export and server authorization for each separate journal implementation. |
| `trading/aiassist` — AI Assistant | workspace; `switchTab(aiassist)` | full / trading-only + premium | U + B | Test microphone permissions, transcription, prompt/source boundaries, response errors and accessibility. |
| `markets/indices` — Top Performers | workspace; `loadIdxYTD` | full | U + B | Check selection periods, index constituents, corporate actions and unavailable benchmark data. |
| `markets/daily` — Market Daily | workspace; `fetchMarketDaily` | full | U + B | Test session date boundaries, repeat refresh and empty source sections. |
| `markets/newsimpact` — News Impact | workspace; `loadBreakingNews` | full | U + B | Verify source provenance, duplicate stories, publish vs event time and unsafe content handling. |
| `markets/assets` — Global Assets | workspace; `switchTab(assets)` | full | U + B | Reconcile currencies, asset sessions, correlations and mismatched observation dates. |
| `movers/movers` — Top Movers | workspace; `switchTab(movers)` | full | U + B | Verify gain/loss calculations and period filters against adjusted historical prices. |
| `moat/moat` — Moat Analysis | workspace; `switchTab(moat)` | full | U + B | Validate factor evidence and missing-data behavior; test all score drilldowns. |
| `structural/structural` — Structural Change | workspace; `switchTab(structural)` | full | U + B | Check filing/event dates, ownership denominators and detected-change evidence. |
| `intradayopt/intradayopt` — Intraday Options | workspace; `switchTab(intradayopt)` | full / trading-only | U + B | Test expiries, lot sizes, sessions and every scan control using licensed-provider fixtures. |
| `scanner360/scanner360` — 360° Scanner | workspace; `switchTab(scanner360)` | full | U + B | Test each filter, score explanation, coverage ratio and empty/unavailable result path. |
| `tools/finance` — Finance Tools | workspace; `renderPersonalFinance` | basic | U + B | Independent calculator cases for contribution timing, tax assumptions, inflation and rounding. |
| `tools/education` — Education | workspace; `_showEduTab` | basic | U + B | Exercise lesson tabs, all links and keyboard navigation; review accuracy of financial explanations. |
| `decide/_active` — Active Trading | workspace; `switchDEMode('activetrading')` | full | U + S | Current browser assertion only finds Trading text; verify actual terminal/chart/journal/voice interactions. |
| `dream/_today` — Today’s Setups | /today; `iframe / today_page` | full + dream | U + S | Current browser assertion only sees iframe; verify gated page contents, regional scans and all controls. |

## Confirmed gaps and fixes

| ID | Finding | Evidence and next action |
|---|---|---|
| MENU-001 — fixed in working tree | Intraday Setups and Micro-Cap Hunter appeared unlocked for full accounts without dream access | `workspace-core.js: canOpen` now requires dream for `intraday` and `mchunter`, matching the existing `switchTab` checks. No access broadened. A regression tests public/trading/full-without-dream denial and dream-granted full/admin access; six-profile dispatcher expectations updated. |
| MENU-002 — open | Full browser fixture masks intermediate-tier behavior | All-full browser fixtures set premium and dream. Add real renderer tests for full without premium, full without dream, trading-only, logout and expired session. Dispatcher stubs alone cannot catch renderer mismatches. |
| MENU-003 — open | Active Trading and Today checks are weaker than other menus | Replace generic body text / iframe visibility with specific rendered controls, deterministic response fixtures and output assertions. |
| MENU-004 — open | Shared `deResult` makes menu text a weak identity check | Several Decide and Dream tools share one container. Analyst now checks its own result area; add equivalent per-tool output selectors and failed/empty response cases. |
| MENU-005 — open | Multiple trading systems have different logic | Existing `/api/algo-signal`, `/api/algo-backtest`, `active-trading.js`, `trading_research.py` and browser-local paper engines must each have identified tests; passing the new closed-bar engine does not certify the legacy engines. |
| MENU-006 — open | Personal-data mutations are outside read-only fixture coverage | Source includes distinct journal APIs and portfolio workflows. Use isolated authorized fixtures for writes/deletes, then test cross-user denial. Never exercise real user records during broad crawling. |

## Observed API paths for targeted fixtures

These are source-observed examples, not an exhaustive API graph and not additional site URLs for users. The menu table records every entry; tracing every nested call remains work.

| Surface | Paths found in `static/app.js` |
|---|---|
| Stock dashboard | `/api/stock-dashboard`, `/api/stock-dashboard-bullbear` |
| Next session | `/api/tomorrow-open-brief` |
| Positioning / smart money | `/api/positioning-scan`, `/api/smart-money-scanner`, `/api/dd-positioning-intelligence` |
| ETF / Diamond | `/api/etf-scanner`, `/api/diamond-hunter` |
| Legacy trading | `/api/algo-signal`, `/api/algo-backtest`, `/api/intraday-options`, `/api/directional-options-scanner` |
| Journal variants | `/api/journal`, `/api/journal-review`, `/api/journal/save`, `/api/journal/list`, `/api/journal/delete`, `/api/momentum-coc/journal` |
| Reports | `/api/regional-reports`, `/api/engine-report`, `/api/engine-report-progress` |

## Legacy validation tests: what they establish

`tests/trading-legacy-validation.test.mjs` currently tests five bounded renderer properties: the legacy backtest panel does not invent a numerical performance claim; EPS/growth alone cannot fabricate quarterly history; actual negative/zero EPS values and period order are preserved; missing/duplicated/invalid EPS history is rejected; a single stock cannot fabricate sector rankings. These are useful regression checks, not strategy validation.

Remaining concrete cases:

1. Reconcile real legacy backtest fills, commissions, spreads, corporate actions and look-ahead handling against an independent fixture. The existing `_renderBacktest` test checks disclosure text, not an executed backtest.
2. Trace actual provider earnings-history payloads through backend normalization into the renderer. Test currency, fiscal-period labels, amended actuals and source metadata; a source string alone is not provenance verification.
3. Verify source values do not become advice/probability claims elsewhere in legacy cards. The guarded renderer tests do not scan or validate every strategy card.
4. Exercise the rendered EPS/sector cards on desktop and mobile with absent and negative data; current tests execute isolated functions in a VM.
5. Maintain explicit boundaries: `test_trading_research.py` validates the separate closed-bar engine (identity, stale/future quotes, missing/incomplete bars, quote reversal and sessions); `test_trading_site.py` validates cache/failure behavior; paper/options tests cover their named engines. None establishes live fills, a profitable strategy or an audited win rate.

## Local verification for this review

- 80 workspace unit tests passed after the access-gate correction.
- All 5 legacy validation renderer tests passed.
- Every one of the 50 generated menu keys appears exactly once in the per-menu register.
- No new browser execution, live financial reconciliation or broker operation was performed by this audit.

## Reproducible next checks

```sh
node qa/menu-inventory.cjs
node --test tests/workspace.test.mjs tests/trading-legacy-validation.test.mjs
python qa/audit.py --previous <previous-report.json> --output qa-output/menu-review
```

Run the browser workflow in its supported CI environment and retain artifacts. Associate each newly confirmed failure with its menu key, input fixture, source time, expected result and regression test. Resolve a gap only after that check passes; preserve untested conditions as unverified.
