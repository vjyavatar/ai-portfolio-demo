# MCP and options analytics reuse — version 1

This release adds read-only options infrastructure and descriptive chain analytics to the existing Decide → Trader page. It does **not** replace or retune the existing Decide strategy. PCR and max-pain calculations do not become CALL BUY/PUT BUY recommendations, confidence scores, order-flow measurements or voice trade alerts.

## What was audited and reused

| Component | Source and pinned revision | Decision |
|---|---|---|
| Indian-Option-MCP analytics | [devag7/Indian-Option-MCP](https://github.com/devag7/Indian-Option-MCP/tree/a00d3eacc181c8994335127fc294133cf3681d7b), commit `a00d3eacc181c8994335127fc294133cf3681d7b` | Adapt the small MIT-licensed PCR aggregation and max-pain calculations into a bounded local module. Preserve copyright and license in `docs/vendor/Indian-Option-MCP-LICENSE.txt`. Do not install or execute the repository's server. |
| India data | [Angel One official SDK](https://github.com/angel-one/smartapi-python), [official instrument catalogue](https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json) | Retain the existing authenticated SmartAPI adapter and catalogue-resolved expiries, strikes and lot sizes. Do not adopt an NSE website scraper or hardcoded expiry weekdays/lot sizes from the community project. |
| US data | [Tradier MCP documentation](https://docs.tradier.com/docs/tradier-mcp), [market data](https://docs.tradier.com/docs/market-data), [API FAQ](https://docs.tradier.com/docs/faq) | Retain Tradier as the account-backed US data source. MCP is a transport interface, not a new data entitlement or a trading strategy. |

The local analytics module is `static/options-analytics.js`, with versioned provenance in its source. It calculates put/call ratios only when each returned strike has valid paired inputs. Zero is valid data; a missing value is not zero. Zero call totals produce an unavailable ratio. The max-pain calculation requires complete paired open interest, multiple strikes, positive total OI and consistent contract sizing. Tied minima remain tied rather than arbitrarily selecting one strike.

Every result is scoped to **returned strikes only**. India's near-spot response covers at most 25 strike pairs; its PCR and payout minimum must not be interpreted as the whole market. Partially supplied or mixed contract sizing prevents the payout calculation; the existing US normalizer admits only standard 100-share contracts. These are snapshot statistics, not price forecasts or evidence of institutional positioning.

## How to use the existing page

1. Open `https://celesys.ai` and complete verified-email sign-in with an account authorized for full trading access. A typed email or a visible menu alone is not server authentication.
2. Open **Decide → Trader** and select the market and underlying symbol.
3. For India, select **NIFTY** or **BANKNIFTY**. For the US, select an underlying supported by your Tradier account, such as **SPY** or **QQQ**.
4. Choose **View option chain**. The page requests a private, read-only snapshot. It does not submit an order or automatically trigger a buy suggestion.
5. Select an expiry from the provider-returned list. Read strike, call/put bid and ask, volume, open interest and quote timing. A fetch time is not a quote time. Unknown or stale source times remain explicitly marked.
6. Read the descriptive analytics alongside the chain. Check the returned-strike coverage and missing-data labels before interpreting a ratio. The analytics never override the existing strategy's WAIT state.
7. Continue using the existing Decide strategy and its separate candidate/voice controls. Loading a chain or its analytics does not enable voice or change a trade decision. Browser audio playback still requires device verification.

No broker-price input is requested from the user. If provider credentials, verified login or valid source data are missing, the page reports that limitation; it does not synthesize live quotes.

## Optional official Tradier MCP transport

The default remains the existing REST adapter. To opt into the new read-only transport, set `CELESYS_TRADIER_TRANSPORT=mcp` in the Render server environment and redeploy. It reuses `CELESYS_OPTIONS_DATA_TOKEN`; the verified-user and `CELESYS_LICENSED_OPTIONS_US` gates still apply. Set the variable to `rest` or remove it and redeploy to roll back the transport without changing strategy code. Invalid transport values fail closed.

`tradier_mcp.py` connects only to `https://mcp.tradier.com/mcp`, with production mode and a server-side API header. It negotiates protocol `2025-03-26`, validates the advertised input schema and calls only `get_options_chain` with symbol, expiration and Greeks arguments. It contains no order/account tool dispatch. Expiry discovery remains on REST because the inspected MCP tool list has no expiry-list tool. Redirects are rejected, payload size and request time are bounded, and upstream failure details are not exposed to the browser. MCP failure does not silently switch transports.

The public initialization/tool-list handshake was inspected on 12 October 2026 UTC and reported server version `0.0.1`. This hosted service has no immutable source commit to pin; runtime schema/protocol checks gate use instead. No authenticated quote response has yet been validated. The adapter accepts only the expected Tradier `options.option` data envelope and otherwise returns unavailable. Do not call this MCP route live-verified until that credentialed check succeeds.

## Activation and limitations

Follow [FREE_CHAIN_SETUP.md](FREE_CHAIN_SETUP.md) for the existing server-side Angel One and Tradier credentials, provider selection, display-entitlement flags and email-login configuration. Do not paste tokens into browser fields, source code or chat. The official provider documentation is authoritative for account eligibility, token renewal, quotas and data display rights.

Account-backed no-additional-API-fee access does not mean unlimited requests, anonymous live data, free brokerage or permission to redistribute data publicly. Caching, pacing and cooldowns reduce duplicate requests; they cannot eliminate provider limits. Neither fixture tests nor `configured=true` demonstrate a live authenticated connection. Actual live activation requires a successful credentialed response with appropriate market-session timestamps and an authorized audience.

## Versioning and rollback

- Existing Decide decision logic is preserved in this release. New analytics are a separate module with no trade-execution methods and no strategy-learning side effects.
- The pre-reuse baseline is commit `81c5abc` (merge of PR #15). This baseline already contains the private Angel One/Tradier chain viewer.
- To undo this release, revert its merge commit in a new reviewed GitHub change, run the existing audit/browser workflow, and deploy that revert to the same Render service. Avoid force-pushing or resetting unrelated later work.
- For an emergency deployment rollback, select the previous known-good deployment in Render, then follow with the Git revert so future deploys remain consistent.
- Retain the existing strategy until a separately versioned replacement has meaningful historical and forward validation, including costs and adverse regimes. No “most successful algorithm” or proven profit probability is claimed here.

## Verification boundary

Automated tests use synthetic fixtures for data normalization, access rejection, missing/zero inputs, stale/context-switched browser responses and non-promotion of analytics into trade tickets. No fixture is live market evidence. Verify both a permitted and denied account and inspect a real broker response after operator configuration; never remove access checks to make a test pass.
