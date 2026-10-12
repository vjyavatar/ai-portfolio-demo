# Live trading readiness — 12 October 2026

The existing site is a research and manual-planning platform. It sends no brokerage orders and does not have a validated profit probability.

## Data to voice workflow

1. Select India or United States and one to six symbols in the existing watchlist.
2. A visible browser tab requests research on five-minute boundaries. Requests are paced; a batch is not a simultaneous market snapshot.
3. The backend checks exact provider symbol, currency, five-minute interval, complete session bars and source timestamps. It requires 21 closed bars for EMA/VWAP/volume analysis.
4. A quote must be no older than five minutes and must follow the signal candle close. Missing candles, market closure, missing volume, reversal or an extended price prevent a candidate.
5. Voice is opt-in. It announces research-condition changes, and withdraws expired candidates. Microphone/audio quality still requires device verification.
6. An underlying candidate is not an option order: inspect option expiry, bid/ask, spread, source time, liquidity and risk separately.

## Current connection boundaries

- Underlying source: existing Yahoo chart adapter; real-time latency is not guaranteed.
- India index data can lack traded volume. VWAP-dependent signals then remain WAIT; volume is never fabricated.
- Public US/India options snapshots are separate from credentialed feeds. An unavailable feed is not a zero-valued chain.
- New connection status distinguishes configured credentials from a verified live connection.
- Five-minute monitoring stops when the tab is hidden; it is not an unattended server trading worker.

## Secure operator setup still required

Set secrets in the existing Render service environment, not browser code or a chat message. Do not buy subscriptions without reviewing provider entitlements and display rights.

India options: CELESYS_DHAN_ACCESS_TOKEN, CELESYS_DHAN_CLIENT_ID, CELESYS_DHAN_INSTRUMENTS_JSON with current verified instrument IDs and segments, plus CELESYS_LICENSED_OPTIONS_IN=true only when authorized to display the data.

US private options: CELESYS_OPTIONS_DATA_TOKEN for the Tradier production account, plus CELESYS_LICENSED_OPTIONS_US=true when display is authorized. The separate SPY/QQQ contract research adapter also needs CELESYS_OPTIONS_DATA_ENABLED=true. Sandbox data must not be described as real-time.

Verified email: CELESYS_AUTH_SECRET (random, at least 32 characters), CELESYS_SMTP_HOST, CELESYS_SMTP_USER, CELESYS_SMTP_PASSWORD and CELESYS_SMTP_FROM. Validate delivery and an authorized login, then set CELESYS_AUTH_ENFORCE=true. Current compatibility mode is not proof of identity.

After setup: verify provider timestamps during a market session, test a permitted and denied account, and test voice on desktop and iPhone before relying on alerts.

## Search and regression checks

Canonical sitemap URLs are consistent; private Today’s Setups responses use noindex and no-store. Search Console verification/submission and actual ranking are separate from code changes.

The nightly full QA workflow runs at 03:17 UTC (08:47 IST). Separate read-only production checks run on weekdays at 06:20 UTC (11:50 IST) for India and 16:20 UTC (11:20 EST / 12:20 EDT) for the US. GitHub may delay scheduled jobs. Live results and failure history are stored separately from fixtures, by market and scope. Missing or stale feeds remain UNVERIFIED; a closed-session WAIT is not certification of live freshness.

Browser fixture execution must be confirmed from CI artifacts; device audio, provider entitlements and financial correctness remain separate verification tasks. The review loop retains failures and tests reviewed fixes; it does not silently rewrite strategies or repeatedly deploy without a verified code change.

References: https://dhanhq.co/docs/v2/option-chain/ ; https://docs.tradier.com/docs/market-data ; https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls

## Single-symbol market panel (2026-10-12)

The trading brief now has a separate auto-updating market panel built on the existing protected watchlist research endpoint. It requests a source snapshot at a paced interval and respects provider cooldowns; it does not establish a streaming-data entitlement. The old engine brief remains explicitly timestamp-unverified and is not relabelled with the new quote's timestamp. The panel uses actual completed five-minute bars, source quote time, session bounds and data-quality gates. It stops on navigation or hidden tabs; manual pause is retained. Voice is opt-in and limited to meaningful state changes.

Legacy counterarguments no longer repeat imperative stop instructions or claim a maximum loss. Modelled stop/target ordering is checked as evidence quality, without changing the existing strategy. A valid sequence is still unverified for execution.

Authenticated options feeds, verified email delivery/enforcement, economic-event validation, calibrated probabilities, audited walk-forward performance and device audio remain separate unfinished requirements. This change does not certify an institutional trading strategy.
