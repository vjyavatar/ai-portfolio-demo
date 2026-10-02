# Celesys Trading Desk v1

## Why

The existing site exposes many overlapping research panels and a homepage claim of knowing exactly when to trade. The new `/trading/` workspace provides a focused path from evidence to a risk scenario and local paper journal, while preserving legacy stock research (Saathi/RuralOS is now retired). The homepage links to it and uses more accurate research language.

## What is implemented

- Responsive dark workspace, US/India switch, focus list, ticker input, five-minute chart, source timestamps and research verdict.
- Read-only `/api/trading-desk/research` adapter to the Yahoo chart source already used elsewhere in this application. No secrets or new package dependencies.
- Modular rule-based stages: data validation, provider session guard, trend/volume/setup analysis, risk critic, independent review and coordinator.
- Entire regular-session bars required; minimum 21 closed five-minute bars. Incomplete candles, missing intervals, malformed OHLC and future/stale quotes cannot produce a candidate.
- EMA9/20, session typical-price VWAP, relative volume against prior 20 bars, simple 14-bar average true range and prior-three-bar breakout checks.
- Explicit latency, missing options and missing event-calendar limitations. There are no fabricated win probabilities or option prices.
- Long stock/ETF paper positions, fees, slippage, cash/risk sizing, realized-loss guard, manual exits and optional observed stop/target exits when the selected symbol is rescanned.
- Separate market/sample and USD/INR browser-local accounts; journal JSON export.
- Explicit synthetic sample available without waiting for markets or a provider.

## Limits

This is deterministic agent orchestration, not a trained model, autonomous LLM, licensed advisory system or a validated profitable strategy. No Robinhood, Angel One, order routing, account login, email or background execution is included. The existing ChatGPT scheduled alerts are separate.

The quote timestamp must be no more than five minutes old and the latest closed bar no more than ten minutes old. This is a research freshness gate, not proof of a real-time feed. The source's regular-session boundaries are used; this is not an independently verified exchange calendar. Raw indices can lack volume and remain blocked. `SPX`/`NDX`/Indian index labels are references, not tradable shares.

A qualifying bearish result is a watch entry, not a short trade or put recommendation. The independent review always notes that event risk and options execution data remain unchecked. Targets/stops are underlying-price scenarios only.

Paper fills are observed quotes with 5bps adverse slippage and a fee of 1 currency unit per side. Stops are observed only on later scans, can gap and do not cap total loss. No partial fills, intrabar paths, taxes, dividends, financing or exchange-specific fees are modeled. Three positions maximum, one per symbol; entries stop after realized losses reach 1% of initial paper balance in a UTC day. This guard does not include unrealized losses. The UI's percentage budget is modeled stop risk, not the amount that can be lost on the full share purchase.

The default paper balances ($2,000 / INR 100,000) and 0.5% risk budget are illustrative and editable, not recommendations to fund a broker. Five-minute refresh requires an open visible page; automatic paper exits only check the scanned symbol. Browser storage is local and is not backed up or shared between devices.

## Integration and operations

The deployed `start:app` wrapper attaches the isolated module after existing endpoints are registered. Direct `api:app` launches retain legacy endpoints only. Attachment errors are logged without breaking existing routes. Existing trading engines and broker integrations are unchanged. Saathi/RuralOS was retired at the owner’s request; its source, assets, tests and build steps were removed. NextStep is preserved.

Provider fetches have a ten-second timeout, a 2MB response limit, at most two concurrent requests per process, a bounded 100-entry cache and a 60-second TTL. Cached data is re-evaluated against current time. This is per-process backpressure, not a distributed authenticated rate limiter. Consider provider licensing and a dedicated data adapter before broader adoption.

## Validation

```sh
python -m unittest discover -s tests -p 'test_trading*.py' -v
node --test tests/trading-paper.test.mjs
python -m py_compile trading_research.py trading_site.py api.py
node --check trading/desk.js
```

Route tests require FastAPI plus httpx compatible with the repository's FastAPI/Starlette version (validated using httpx 0.27.2). Python/JS tests cover freshness, missing and invalid data, forming bars, holidays/closed-session state as reported by provider, cash constraints, gap losses, duplicate positions, wrong-symbol exits and mount/security behavior.

## Deploy / rollback

Deploy the reviewed branch through the existing Render service, after confirming the correct workspace and service. There is no migration or environment variable change. Verify `/api/trading-desk/status`, `/trading/`, the homepage link, sample exercise, live failure behavior, and the HTTP 410 response for retired `/ruralos/`. Full browser visual QA and production regression checks remain deployment gates; the cloud browser could not reach the local development server in this session.

Revert the feature commit to remove the route and homepage link. Local paper accounts remain in the user's browser under `celesys.desk.v1`; clearing browser storage removes them. Export first if retention is desired.

## Notification center and Saathi retirement

The new inbox is local to each browser, capped at 100 entries, and deduplicates symbol/region/direction/provider session. Clearing the inbox also clears deduplication history. Source quotes expire after five minutes or at session end, whichever comes first. Samples, blocked checks and closed sessions cannot notify. Browser permission and sound require user gestures; sound must be enabled again after reload. Browser/OS settings can suppress delivery. The selected instrument is scanned only while the page is visible and auto-refresh is enabled. This is not background market-wide monitoring.

Evidence export includes the current report, source times, stages and a sample flag. Email is a separate scheduled workflow; the desk does not claim SMTP readiness or delivery.

Saathi retirement removes 278 tracked files. The startup wrapper serves HTTP 410 for old routes and a minimal service-worker retirement script, which unregisters itself and clears only caches starting with saathi-ruralos-. Existing installations receive cleanup when their browser next checks the worker. Repository history retains earlier files for rollback. The shared Render service remains in place, with its existing plan; file deletion alone does not reduce plan charges.

Validation for this revision: 19 research/API tests, 11 paper/notification tests, one retirement-route test, plus a DOM integration exercise for sample research, paper entry, notification suppression and inbox clearing. Native browser sound, OS notification delivery and visual QA remain deployment checks.

## v1.1 readiness corrections

The readiness strip separates data transport, scan coverage and strategy validation. HTTP errors, provider access denial, rate limiting, invalid responses and connectivity failures have distinct non-sensitive codes. Failed provider requests have a 60-second per-symbol cooldown. A successful response is not proof of fresh data.

Currency and five-minute interval metadata must match the selected market. The current quote must still support the breakout and stay within 0.75 ATR beyond the signal close. These conservative policy thresholds are not statistically optimized or proven profitable. The existing 21-closed-bar warmup means candidates cannot appear in the first 105 minutes of a regular session with this current-session-only design.

New scans that fail or no longer confirm a setup invalidate its local notification. Invalidation does not resend the same directional/session alert. The freshness label and verdict expire as time passes; background coverage is never implied.

The legacy options engine's hard-coded Backtest Preview was replaced with explicit unverified validation status. No fabricated historical win rates, returns or drawdown are displayed by that panel. Other legacy panels remain only partially audited; rule-based confidence labels elsewhere should not be interpreted as calibrated probabilities.
