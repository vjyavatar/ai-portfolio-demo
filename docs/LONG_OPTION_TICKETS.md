# Call / put buy tickets in the original Decide page

This feature keeps the original Decide charts and strategy calculations. The new ticket above the report is a separate read-only contract-evidence check. It sends no orders and does not certify the original strategy's profitability.

## Current coverage and setup

- US SPY and QQQ, standard 100-share contracts, nearest provider-listed non-0DTE expiry within 1–14 calendar days. This is not an exhaustive market or expiry scan.
- India and other symbols remain unavailable in this selector until their contract identity, bid/ask source times and market session can be verified. Do not infer an expiry or premium from the underlying price.
- `/api/trading-desk/options` now requires a verified full-access server session, even when legacy authentication enforcement is disabled. A client email header or client role alone cannot unlock it.
- Verified-email service configuration and authorized options data access are required. `CELESYS_OPTIONS_DATA_ENABLED=true` and `CELESYS_OPTIONS_DATA_TOKEN` enable the existing Tradier adapter only after appropriate account/data permissions are established. Do not paste credentials into source code.
- Scanning is explicit, paced by server caches/cooldowns and the returned retry time. The ticket does not introduce an automatic market-wide scan.

## Selection and displayed values

The existing closed-bar underlying research must qualify a bullish or bearish scenario. The selector checks session boundaries, quote/bar ordering, contract identity, requested expiry, bid/ask freshness, spreads, sizes, volume, open interest and time-stamped hourly Greeks. Among contracts that pass, it ranks by relative spread, then absolute delta proximity to 0.55. This is an execution-quality heuristic, not a ranking by expected profit.

The ticket displays BUY CALL or BUY PUT, strike, expiry, bid/ask entry range, ask-based limit cap, premium exposure for one contract, underlying invalidation and target, source times and confidence evidence. A quote range does not guarantee a fill.

Premium stop/target levels are an optional **illustrative 25% stop / 50% target policy** based on the ask cap. They are not forecasts, independently optimized parameters or guaranteed exits. Recalculate from the actual fill and verify permitted ticks. The entire option premium plus costs remains at risk; exercise can create separate underlying exposure. Underlying prices must never be confused with option-premium exit prices.

Confidence is `UNCALIBRATED`, with no invented success percentage. Establishing a probability requires independent out-of-sample results with historical option bid/ask data, spreads, fees, slippage, liquidity constraints, event risk and multiple market regimes. No strongest or highest-profit algorithm claim is made.

## Failure and review behaviour

No current candidate is displayed for missing credentials, unauthenticated access, stale or mismatched evidence, invalid source timing or unsupported coverage. Expired ticket values are cleared; old requests cannot overwrite a remounted ticket. Voice is manual and requires both ticket and workspace opt-in. Legacy modelled contract estimates are labelled separately, and assumed-budget position-size suggestions are suppressed.

Targeted backend, UI lifecycle and browser fixtures use synthetic provider responses. Their success does not verify an actual provider connection or physical audio playback.

## Reference material

- https://docs.tradier.com/docs/market-data — production/sandbox data and hourly Greeks.
- https://docs.tradier.com/reference/brokerage-api-markets-get-options-chains — contract chain fields.
- https://www.optionseducation.org/strategies/all-strategies/long-call — long-call premium risk, time decay and exercise considerations.

The numerical filters and exit policy are Celesys rules, not an endorsement or performance claim by these sources.
