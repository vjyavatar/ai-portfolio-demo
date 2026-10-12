# India and US options feeds: verified alternatives

Research date: 12 October 2026. Scope: official provider material, no paid activation, credentials, order submission or scraping implementation. Upstox is excluded at the owner's request.

**Finding:** this review did not identify a documented, genuinely free, unauthenticated API supplying actual real-time option quotes for both India and the US with permission to display them publicly. This is a finding about the reviewed providers, not proof that no alternative exists. Free API access, brokerage-account access and public redistribution rights are different things.

| Provider | Coverage and price evidence | What it supplies | Requirement / limitation |
|---|---|---|---|
| Angel One SmartAPI | India. Official home and FAQ search listings advertise free APIs, including historical data. | Authenticated live market quotes; the indexed official documentation describes batches of up to 50 symbols and option Greeks. | Promising zero-additional-API-fee route for an eligible Angel One account. A complete option chain should be assembled from verified contract tokens and quotes; this review did not verify a dedicated full-chain endpoint. Public redistribution permission remains unverified. |
| DhanHQ | India. Official support lists Data API at ₹499 plus applicable taxes per month, renewed every 30 days. | Dedicated option-chain API with OI, Greeks, volume and bid/ask data. | Data subscription and account credentials required. Free trading APIs do not mean free Data APIs. Existing Celesys adapter can be retained, but must not be advertised as a free data solution. |
| Tradier | US. Official FAQ says brokerage account holders are not charged for API access. | Production equities/options quotes are real time; sandbox quotes are delayed 15 minutes. Greeks are hourly, not tick-live. | Brokerage account and token required. FAQ explicitly limits non-partner API use to personal use; public Celesys distribution needs an appropriate partner arrangement. |
| Alpaca | US. Free indicative option feed; OPRA feed available to subscribed users. | Indicative quotes are derived rather than actual OPRA quotes, and derived trades are delayed 15 minutes. Option-chain snapshots support selecting the feed. | Useful for labelled development/research, not a substitute for actual live executable option quotes. Authentication and applicable entitlement still required. |

## Recommended implementation path

1. For private India access, validate Angel One SmartAPI against a real authorized account before choosing it as a free alternative. Resolve contracts from the instrument master, including expiry, exchange, token, strike scaling and lot size; do not invent token mappings or expiry weekdays.
2. For private US access, keep the existing Tradier integration as the straightforward account-backed path. Preserve quote timestamps separately from Greeks timestamps.
3. For a public website, obtain provider confirmation of the permitted display audience. An environment flag cannot itself create a redistribution license. Keep credentials server-side and access scoped to verified identities.
4. Until an authenticated feed is verified, display unavailable/delayed/indicative states explicitly. Never relabel an indicative quote, imported CSV or successful HTTP response as live data.
5. Validate bid/ask, contract identity, source timestamps, stale behavior, market-session alignment and rate limits with read-only calls. No actual options entry should be inferred from an underlying-only quote.

## Official sources and retrieval limits

- [Angel One SmartAPI home](https://smartapi.angelone.in/) and [FAQ](https://smartapi.angelone.in/faq): official search listings retrieved on the research date advertise free access. Direct page opens returned an authorization wall; complete terms were not reviewed.
- [SmartAPI documentation](https://smartapi.angelone.in/docs): official indexed content supplies the market-data batch and Greeks information. Direct open was blocked. Recheck exact current rate limits and entitlement during authenticated setup.
- [Angel One product overview](https://www.angelone.in/news/product-updates/angel-one-smartapi-the-secret-to-easy-automated-algo-trading): accessible official overview of authentication and live market data; article updated February 2024, so not used alone for current pricing.
- [Dhan Data API subscription](https://dhan.co/support/platforms/dhanhq-api/how-does-the-dhanhq-data-api-subscription-work/): current published monthly price.
- [Dhan option-chain release information](https://dhanhq.co/docs/v2/releases/): documented chain fields.
- [Tradier market data](https://docs.tradier.com/docs/market-data): production/sandbox freshness and hourly Greeks.
- [Tradier FAQ](https://docs.tradier.com/docs/faq): free account API access and personal-use/partner restriction. Its index-delay description differs from the market-data page; do not promise index freshness without endpoint verification.
- [Alpaca option data](https://docs.alpaca.markets/us/docs/historical-option-data) and [option-chain API](https://docs.alpaca.markets/us/reference/optionchain): indicative/OPRA distinction.

No provider account was opened or connected during this research. Actual credentialed responses, contractual rights for Celesys, account eligibility and end-to-end live-feed operation remain unverified.
