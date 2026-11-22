# Celesys Live Market Data — Implementation Baseline

Status: foundation contract added on `feat/live-market-data-foundation`.
This is not a live-feed activation or a production deployment.

## Scope and decisions

- Initial usage: personal, read-only market intelligence.
- United States: Alpaca Trading API market data; full SIP equities and OPRA options require the appropriate Algo Trader Plus entitlement. Confirm current plan entitlements in the Alpaca account before enabling.
- India: Angel One SmartAPI, with a managed login/session lifecycle and SmartAPI WebSocket 2.0.
- No order placement, broker execution, or public redistribution in this phase.
- Existing Celesys endpoints and signal engines remain compatibility surfaces until parity tests pass.

## Current-code constraints discovered

- `start.py` imports the existing API, trading desk, discovery routes, access control, and `private_options`; avoid replacing this entry point.
- `trading_site.py` currently describes Yahoo Finance chart data as lacking guaranteed live latency and uses a 5-minute cadence.
- `private_options.py` currently routes US option snapshots through Tradier and India through Angel One or Dhan. US provider selection must be made explicit for Alpaca; do not silently fall back to Tradier.
- `angel_options.py` is a read-only snapshot adapter. Login can be a static JWT or `loginByPassword`. The public board and the legacy NIFTY/BANKNIFTY chain use it when the session is configured. The chain is a bounded near-spot window, not the full India index universe. NSE quotes use the market quote API in OHLC mode (LTP plus previous close).
- `option_chain.py` contains the existing normalized option-row contract consumed by the UI. Preserve its field names during migration.
- Existing signal logic must not receive synthetic timestamps, prices, Greeks, OI, or volume.

## Target architecture

```
Provider WebSockets / REST backfill
       |                         |
  Alpaca adapter            Angel One adapter
       |                         |
       +------ Provider session / stream manager ------+
                              |
                    Canonical data contracts
                              |
             UTC normalization + exchange calendars
                              |
                 Quote validation / freshness
                              |
                 1m bars -> closed 5m bars
                              |
                  bounded cache / history
                              |
       Existing API compatibility adapters / v2 API
                              |
              MDO / CDS / options / portfolio
```

## Canonical contract rules

- All timestamps are timezone-aware UTC; retain exchange-local session context separately.
- Missing fields remain null. Required missing inputs produce `INSUFFICIENT_DATA`.
- Distinguish `LIVE`, `DELAYED`, `STALE`, `DISCONNECTED`, and `INVALID`.
- A quote is not actionable merely because it was received recently: bid/ask source timestamps and market validity are required.
- Reject crossed markets, negative/non-finite values, duplicate contract identities, malformed timestamps, and out-of-order bar boundaries.
- A bar becomes signal-eligible only after its interval closes and the provider has supplied/confirmed its final update.
- The trading decision layer remains fail-closed on disconnect, stale feed, or missing mandatory features.

## Provider implementation sequence

1. Add provider-neutral contracts and tests (this commit).
2. Implement Alpaca auth, SIP stock stream, OPRA options stream, MessagePack handling, bounded subscriptions, reconnect/backoff, and REST historical backfill.
3. Implement Angel One auth/session renewal, instrument-master refresh, WebSocket 2.0 modes, subscription limits, reconnect/backoff, and historical candle adapter.
4. Add a stream supervisor, health state, UTC normalization, exchange calendars, deduplication, and 1m-to-5m aggregation.
5. Add provider selection by explicit configuration; no implicit fallback between credential sets.
6. Adapt existing endpoints to normalized records while preserving response schemas; add a versioned API only where compatibility cannot be maintained.
7. Integrate MDO/CDS/options after contract parity and regression tests. Preserve score weights, signal locks, and NO TRADE gates.

## Required configuration (names only; values belong in Render secrets)

Alpaca:
- `APCA_API_KEY_ID`
- `APCA_API_SECRET_KEY`
- `CELESYS_ALPACA_STOCK_FEED=sip`
- `CELESYS_ALPACA_OPTIONS_FEED=opra`

Angel One:
- `CELESYS_ANGEL_API_KEY`
- Secure client identity and login factors through the approved secret store.
- JWT and feed token should be refreshed by the session manager; do not treat a manually copied JWT as a durable session strategy.

Common:
- `CELESYS_MARKET_DATA_MODE=shadow` initially.
- `CELESYS_MARKET_DATA_FAIL_CLOSED=true`.
- Provider entitlement and data-display permission must be independently verified.

## Test gates before enabling signals

- Unit: contract validation, UTC conversion, quote freshness, crossed markets, duplicate/out-of-order messages, incomplete bars, 5m boundary handling.
- Provider contract: authentication failures, token expiry, rate limits, malformed payloads, disconnect/reconnect, subscription caps, empty responses.
- Regression: all current trading/options tests, API response compatibility, signal score stability and lock behavior.
- Shadow: compare Alpaca/Angel feeds against current sources without changing decisions; log timestamp skew and field-level differences.
- Cutover: only after shadow parity, enable one market at a time with rollback switch.

## Operational and licensing safeguards

- Start with the existing Render service only for a single-instance personal workflow; process-local streams/cache are not durable across restarts.
- If multiple app instances or independent workers are introduced, move stream ownership and shared state to a dedicated worker plus Redis-compatible shared cache.
- Keep secrets in Render environment settings; never commit them or place them in chat.
- Personal market-data entitlements must not be assumed to permit public redistribution. Reassess exchange/provider licensing before exposing feeds to Celesys customers.
- No live-data claim until a real authenticated connection, fresh quote, and health check have succeeded.
