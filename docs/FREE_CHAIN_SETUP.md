# Account-backed options chains: Angel One India + Tradier US

The original Decide → Trader page now includes **View option chain**. This is a read-only, verified-account feature. It uses the same private chain endpoint for both markets and does not send orders or turn chain snapshots into buy recommendations.

## Provider choice

India defaults to Angel One SmartAPI when no Dhan token is configured. An existing Dhan installation stays on Dhan unless explicitly changed. Set `CELESYS_INDIA_OPTIONS_PROVIDER=angelone` to select SmartAPI, or `dhan` to retain the optional paid data adapter. Unsupported provider names fail closed; there is no silent cross-provider fallback.

US chains retain the existing Tradier production adapter. SmartAPI advertises no API fee and Tradier does not charge brokerage account holders for API access. Brokerage eligibility, account charges, data entitlements, token renewal and permitted display audience remain account-specific. Neither configuration flags nor a private website alone establish redistribution rights. Dhan's Data API is not presented as free.

## Render environment setup

Set these as server-side environment values, never in browser code or git:

| Market | Variable | Purpose |
|---|---|---|
| India | `CELESYS_INDIA_OPTIONS_PROVIDER=angelone` | Explicit provider choice |
| India | `CELESYS_ANGEL_API_KEY` | SmartAPI application key |
| India | `CELESYS_ANGEL_JWT_TOKEN` | Authorized current account session JWT |
| India | `CELESYS_ANGEL_CLIENT_LOCAL_IP` | Actual client environment header required by SmartAPI |
| India | `CELESYS_ANGEL_CLIENT_PUBLIC_IP` | Actual client public IP header |
| India | `CELESYS_ANGEL_MAC_ADDRESS` | Actual client MAC header required by the documented SDK |
| India | `CELESYS_LICENSED_OPTIONS_IN=true` | Enable only after verifying account entitlements and permitted audience |
| US | `CELESYS_OPTIONS_DATA_TOKEN` | Tradier production market-data token |
| US | `CELESYS_LICENSED_OPTIONS_US=true` | Enable only for the permitted audience |

The existing verified-email sign-in service must also be configured. The private endpoint requires a verified full-access server session; typing an allowlisted email in the legacy form is insufficient. Refer to `LIVE_TRADING_READINESS.md` and `secure_access.py` for existing email-service configuration. No new broker account is created, no payment activated, and no login/TOTP/order call is implemented here. Renew expired provider credentials securely through the provider's supported account flow.

`CELESYS_OPTIONS_DATA_ENABLED` separately controls the existing SPY/QQQ buy-candidate selector; enabling chain viewing does not enable that selector.

## Coverage and source interpretation

- Angel One: NIFTY/BANKNIFTY NFO option contracts resolved from the official instrument master, including expiry, strike scaling and lot size. A source index snapshot selects up to 25 complete nearby call/put strike pairs (50 tokens) in one option batch. This is a **partial near-spot chain**, not all strikes or all Indian stocks.
- Tradier: matching standard 100-share US option contracts from the selected provider-listed expiry. Unsupported or adjusted contracts are excluded. A provider snapshot does not establish an executable fill.
- SmartAPI FULL exchange-feed times are recorded separately as `feed_time`. The adapter does not invent separate bid/ask timestamps or missing Greeks/IV. The UI displays the feed time and explicitly marks side-specific quote timing unknown.
- Provider expiry lists drive selection. No hardcoded weekday/lot-size inference is used for SmartAPI contracts. Missing, crossed, stale or mismatched data stays unavailable or clearly marked unverified.

## Request controls and validation

The SmartAPI adapter has a bounded instrument-master download, a six-hour master cache, 60-second snapshot reuse, one in-flight request, paced quote batches, timeouts, fixed provider URLs, rejected redirects and provider failure cooldowns. The browser loads only on explicit action or expiry selection, reuses recent snapshots, respects cooldowns and drops obsolete responses. These controls reduce quota pressure; they do not make a free API unlimited.

Synthetic tests validate identity, normalization, timestamps, cache/cooldown behaviour, access denial and browser rendering. Actual account authentication, provider entitlements and a successful live quote response still require a credentialed activation check. A successful deployment or `configured=true` is not a verified live connection.

## Official references

- https://smartapi.angelone.in/faq
- https://smartapi.angelone.in/docs
- https://github.com/angel-one/smartapi-python
- https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json
- https://docs.tradier.com/docs/faq
- https://docs.tradier.com/docs/market-data

Reviewed 13 October 2026 (India time). Some SmartAPI documentation opens are access-restricted; the adapter also uses official indexed documentation and SDK source. Do not interpret successful fixture tests as provider certification.
