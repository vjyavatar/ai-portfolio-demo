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


## Rate-limit resilience and symbol notifications — 12 October 2026

- Disabled speculative 36-ticker/two-minute cache warming by default. Operators can explicitly opt in with `CELESYS_YAHOO_PREFETCH=true`; even then cache hits skip fetching and requests use bounded, thread-safe pacing.
- Main legacy SafeTicker history/info/fundamentals/options calls share a bounded per-process cache and single-flight work. Original source timestamps are retained. Repeated provider failures are briefly cached, and detected 429 exceptions pause this adapter for five minutes. This does not intercept every raw yfinance import or direct HTTP request elsewhere in the large legacy engine.
- Trading Desk retains at most 15 minutes of previously validated history during an outage. It labels the snapshot, removes scenarios, blocks candidates and never restamps old quotes as live. All responses provide next-refresh guidance; cooldowns remain provider-wide within the Trading Desk process.
- Market notifications show symbol, region, observation time and quote time. Meaningful readiness changes, outages and recovery are deduplicated. Sound is opt-in, with a Test sound control. Voice remains independently opt-in. These foreground notifications do not run with a closed/hidden browser tab; physical speaker playback requires user verification.
- Existing scheduled QA retains failure evidence between runs. Added regressions cover cache concurrency, stale snapshot trade suppression, prefetch opt-in, notifications and audio consent. This is regression memory, not self-trained trading profitability or unattended strategy rewriting.
- Remaining live-data dependency: authorized Dhan/Tradier credentials, instrument mapping and display entitlement, plus verified-email authentication. Polling public Yahoo cannot guarantee real-time delivery or eliminate provider/IP quotas. A production authenticated streaming feed is the intended next step; none is claimed connected by these changes.

Official references: https://docs.tradier.com/docs/rate-limiting , https://docs.tradier.com/docs/streaming-data , https://dhanhq.co/docs/v2/live-market-feed/ , https://dhanhq.co/docs/v2/market-quote/ .
